/**
 * Remove JSON fences and echoed prompt keys from strings used as headlines / ledes in the UI.
 */
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
        if (typeof v === 'string' && v.trim()) return v.trim();
      }
    } catch {
      /* keep s */
    }
  }

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
  s = s.replace(/\s*[\}\]]+\s*$/g, '').trim();
  if (!s.includes('\n')) s = s.replace(/\s+/g, ' ').trim();
  return s;
}
