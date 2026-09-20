/**
 * Remove JSON fences, echoed prompt keys, and LLM preambles from strings used as headlines / ledes.
 */
const PREAMBLE_RE =
  /^here(?:'s|\s+is)\s+a\s+(?:professional,?\s*)?(?:journalistic\s+)?summary\s+of\s+the(?:\s+news)?\s+article:?\s*/i;

const META_HEADERS = new Set([
  'article summary',
  'news summary',
  'summary',
  'article',
  'news article',
  'professional summary',
  'journalistic summary',
]);

function unwrapBold(line: string): string | null {
  const m = line.trim().match(/^\*\*(.+?)\*\*$/);
  return m ? m[1].trim() : null;
}

function isMetaHeader(text: string): boolean {
  const t = text.replace(/^\*+|\*+$/g, '').trim().toLowerCase().replace(/:$/, '');
  return META_HEADERS.has(t) || /^(?:article|news)\s+summary$/.test(t);
}

function stripLlmProsePreamble(text: string): string {
  let s = text.replace(PREAMBLE_RE, '').trim();
  const kept: string[] = [];
  let boldHeadline: string | null = null;

  for (const line of s.split('\n')) {
    const t = line.trim();
    if (!t || PREAMBLE_RE.test(t) || isMetaHeader(t)) continue;
    const bold = unwrapBold(t);
    if (bold) {
      if (isMetaHeader(bold)) continue;
      boldHeadline = bold;
      kept.push(bold);
      continue;
    }
    kept.push(t);
  }

  if (boldHeadline) return boldHeadline;
  if (kept.length) return kept[0];
  return s;
}

export function sanitizeLeadText(raw: string | null | undefined): string {
  if (raw == null || typeof raw !== 'string') return '';
  let s = raw.trim();
  if (!s) return '';

  if (s.startsWith('```')) {
    const rest = s.split('\n').slice(1).join('\n');
    s = rest.includes('```') ? rest.split('```')[0].trim() : rest.trim();
  }

  if (s.startsWith('{') && s.endsWith('}')) {
    try {
      const obj = JSON.parse(s) as Record<string, unknown>;
      for (const k of ['lede', 'headline', 'summary', 'title', 'text', 'content']) {
        const v = obj[k];
        if (typeof v === 'string' && v.trim()) return sanitizeLeadText(v.trim());
      }
    } catch {
      /* keep s */
    }
  }

  s = stripLlmProsePreamble(s);

  const lines = s
    .split('\n')
    .filter(line => {
      const t = line.trim();
      if (!t) return true;
      if (t === '{' || t === '}' || t === '[' || t === ']') return false;
      if (/^["']?(lede|headline|summary|title|who|what|when|where)["']?\s*:/i.test(t))
        return false;
      return true;
    });
  s = lines.join('\n').trim();
  if (s.includes('\n\n')) s = s.split('\n\n', 1)[0].trim();
  else if (s.includes('\n')) s = s.split('\n', 1)[0].trim();
  s = s.replace(/\s*[\}\]]+\s*$/g, '').trim();
  if (!s.includes('\n')) s = s.replace(/\s+/g, ' ').trim();
  return stripLlmProsePreamble(s);
}

/** Mega / 5W1H placeholder titles that must never show in UI. */
const PLACEHOLDER_STORYLINE_TITLE_RE =
  /^Ongoing:\s*(WHAT|WHO|WHEN|WHERE|WHY)$/i;

/** Entity-derived year keys leaked into titles (e.g. "Year_2026: …"). */
const YEAR_ENTITY_TITLE_PREFIX_RE = /^Year_20\d{2}\s*:\s*/i;

export type StorylineTitleSource = {
  title?: string | null;
  description?: string | null;
  article_count?: number | null;
  articles?: unknown[];
} | null;

/**
 * Strip leaked JSON braces, prompt keys, and Year_20xx: prefixes from a raw title.
 */
export function cleanStorylineTitleRaw(raw: string | null | undefined): string {
  if (raw == null || typeof raw !== 'string') return '';
  let s = raw.trim();
  if (!s) return '';

  s = s.replace(YEAR_ENTITY_TITLE_PREFIX_RE, '').trim();

  if (/^[\{\[]/.test(s)) {
    s = s.replace(/^[\{\[\s"']+/, '').replace(/^:\s*/, '').trim();
    s = s.replace(
      /^(lede|headline|summary|title|who|what|when|where|why|how)\s*:\s*/i,
      ''
    ).trim();
  }

  s = sanitizeLeadText(s);
  return s.trim();
}

/**
 * Safe storyline title for list/detail chrome. Never returns Ongoing: WHAT,
 * bare "{:", or Year_20xx: prefixes. Soft-ellipsizes mid-word truncations.
 */
export function displayStorylineTitle(
  storyline: StorylineTitleSource,
  fallbackId?: string | number
): string {
  const raw = (storyline?.title || '').trim();
  const cleaned = cleanStorylineTitleRaw(raw);
  const placeholder =
    PLACEHOLDER_STORYLINE_TITLE_RE.test(raw) ||
    PLACEHOLDER_STORYLINE_TITLE_RE.test(cleaned);
  const usable =
    Boolean(cleaned) &&
    !placeholder &&
    cleaned.length >= 3 &&
    cleaned !== '{' &&
    cleaned !== ':' &&
    !/^[\{\[]/.test(cleaned);

  if (usable) return softEllipsizeMidWordTruncation(cleaned);

  const count =
    storyline?.article_count ??
    (Array.isArray(storyline?.articles) ? storyline.articles.length : undefined);
  const desc = (storyline?.description || '').trim();
  if (desc && /^Mega-storyline/i.test(desc) && count != null) {
    return `Mega-storyline (${count} articles)`;
  }
  if (desc) {
    const cleanedDesc = sanitizeLeadText(desc) || desc;
    return cleanedDesc.length > 80
      ? `${cleanedDesc.slice(0, 77)}…`
      : cleanedDesc;
  }
  return fallbackId != null ? `Storyline #${fallbackId}` : 'Untitled Storyline';
}

/** If a title was cut mid-token (e.g. ends with "ove"), trim to last full word + …. */
function softEllipsizeMidWordTruncation(title: string): string {
  const t = title.trim();
  if (t.length < 24) return t;
  if (/[.!?…)"'\]]$/.test(t)) return t;
  const m = t.match(/^(.*\s)([A-Za-z]{1,3})$/);
  if (!m) return t;
  const head = m[1].trimEnd();
  if (head.length < 20) return t;
  return `${head}…`;
}
