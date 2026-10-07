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
