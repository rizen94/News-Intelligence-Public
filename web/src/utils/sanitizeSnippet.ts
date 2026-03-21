export function stripHtml(input: string): string {
  return input.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

export function sanitizeSnippet(input: unknown, fallback = ''): string {
  if (typeof input !== 'string') return fallback;
  const raw = input.trim();
  if (!raw) return fallback;
  return /<[a-z][\s\S]*?>/i.test(raw) ? stripHtml(raw) : raw;
}
