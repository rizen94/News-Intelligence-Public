/** Strip tags while keeping rough paragraph breaks for reader briefs. */
export function stripHtml(input: string): string {
  return input
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<\s*br\s*\/?\s*>/gi, '\n')
    .replace(/<\/\s*(?:p|div|h[1-6]|li|tr|blockquote)\s*>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

export function sanitizeSnippet(input: unknown, fallback = ''): string {
  if (typeof input !== 'string') return fallback;
  const raw = input.trim();
  if (!raw) return fallback;
  return /<[a-z][\s\S]*?>/i.test(raw) ? stripHtml(raw) : raw;
}

/** Strip leftover markdown markers for plain-text reader surfaces (hub / vault excerpts). */
const ARTICLE_BOILERPLATE =
  /^(?:already an? .+ subscriber\??|login|get audio access with any .+ subscription\.?|- get audio access)/i;

/** Prep article summary/content for the v2 article reader (RSS markdown junk). */
export function prepareArticleReaderText(
  raw: string,
  title?: string
): string {
  let s = stripReaderMdMarkers(sanitizeSnippet(raw, '')).trim();
  if (!s) return '';
  s = s
    .split('\n')
    .filter(line => !ARTICLE_BOILERPLATE.test(line.trim()))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  if (title) {
    const t = title.trim().toLowerCase();
    const lines = s.split('\n');
    while (lines.length) {
      const head = lines[0].replace(/^\s*#{1,6}\s+/, '').trim().toLowerCase();
      if (!head || head === t || t.startsWith(head) || head.startsWith(t.slice(0, 48))) {
        lines.shift();
        continue;
      }
      break;
    }
    s = lines.join('\n').trim();
  }
  return s;
}

export function articleSummaryIsRedundant(
  summary: string,
  body: string,
  title: string
): boolean {
  const a = summary.trim().toLowerCase();
  const b = body.trim().toLowerCase();
  const t = title.trim().toLowerCase();
  if (!a) return true;
  if (a === t || t.startsWith(a) || a.startsWith(t.slice(0, 60))) return true;
  if (b && (b.startsWith(a) || a.startsWith(b.slice(0, Math.min(200, b.length))))) {
    return true;
  }
  return false;
}

export function stripReaderMdMarkers(raw: string): string {
  return String(raw || '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*\n]+)\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/_([^_\n]+)_/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/^\s*#{1,6}\s+/gm, '')
    .replace(
      /^\s*(?:Lede|Why this is in play|Timeline of Events|Main Narrative Thread|Storyline Analysis|What happened|Why it matters|Context|Key developments?)\s*:?\s*$/gim,
      ''
    )
    .replace(/^\s*[-*•]\s+/gm, '• ')
    .replace(/^\s*(?:Summary|CURRENT BRIEF)\s*:\s*/gim, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
