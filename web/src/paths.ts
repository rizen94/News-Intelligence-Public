/**
 * Canonical product URL helpers.
 * Live surface: News + Finance + Admin on https://news-intelligence-ag.duckdns.org
 * News home is `/` (same content as former /v2?domain=politics). Code under web/src/v2/.
 */
export const PUBLIC_ORIGIN = (
  typeof import.meta !== 'undefined' && import.meta.env?.VITE_PUBLIC_ORIGIN
    ? String(import.meta.env.VITE_PUBLIC_ORIGIN)
    : 'https://news-intelligence-ag.duckdns.org'
).replace(/\/$/, '');

export const NEWS_HOME = '/';
export const ADMIN_HOME = '/admin';
export const FINANCE_HOME = '/finance';

/** Default News home with politics filter (former /v2?domain=politics). */
export function newsHomePath(domain?: string | null): string {
  const d = (domain && domain.trim()) || 'politics';
  if (d === 'all') return `${NEWS_HOME}?domain=all`;
  return `${NEWS_HOME}?domain=${encodeURIComponent(d)}`;
}

export function newsStorylinePath(domain: string, id: string | number): string {
  return `/storylines/${encodeURIComponent(domain)}/${encodeURIComponent(String(id))}`;
}

export function newsEntityPath(id: string | number, domain?: string | null): string {
  const base = `/entities/${encodeURIComponent(String(id))}`;
  if (domain) {
    return `${base}?domain=${encodeURIComponent(domain)}`;
  }
  return base;
}

export function newsResearchPath(domain?: string | null): string {
  return domain ? `/research?domain=${encodeURIComponent(domain)}` : '/research';
}

/** Absolute URL on the public site (for shares / external docs). */
export function publicUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${PUBLIC_ORIGIN}${p}`;
}

/** Strip legacy /v2 prefix; map /v2/admin → /admin. */
export function stripLegacyV2Path(pathname: string): string {
  if (pathname === '/v2' || pathname === '/v2/') {
    return NEWS_HOME;
  }
  if (pathname.startsWith('/v2/admin')) {
    const rest = pathname.slice('/v2'.length);
    return rest || ADMIN_HOME;
  }
  if (pathname.startsWith('/v2/')) {
    const rest = pathname.slice('/v2'.length);
    return rest || NEWS_HOME;
  }
  return pathname;
}
