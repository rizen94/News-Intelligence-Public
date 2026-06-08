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
