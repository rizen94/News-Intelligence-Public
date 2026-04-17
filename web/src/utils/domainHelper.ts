/**
 * Domain Helper Utility
 * Provides domain context and helper functions for v5.0 multi-domain architecture.
 *
 * Active domains load from GET /api/system_monitoring/registry_domains (see AGENTS.md).
 * FALLBACK_DOMAINS is used until the first successful fetch or when the API is down.
 *
 * Registry URL must match apiConfig (VITE_API_URL + localStorage news_intelligence_api_url),
 * same as apiConnectionManager health checks — otherwise fetch fails and the UI stays on fallback.
 */

import { getApiOrigin, getCurrentApiUrl } from '../config/apiConfig';

export type DomainKey = string;

export interface Domain {
  key: DomainKey;
  name: string;
  schema: string;
}

/** Used when the API is unreachable or returned no domains (SSR, offline, boot). Template silos — not legacy keys. */
const FALLBACK_DOMAINS: Domain[] = [
  { key: 'politics', name: 'Politics', schema: 'politics_2' },
  { key: 'finance', name: 'Finance', schema: 'finance_2' },
  { key: 'artificial-intelligence', name: 'Artificial Intelligence', schema: 'artificial_intelligence' },
  { key: 'medicine', name: 'Medicine', schema: 'medicine' },
  { key: 'legal', name: 'Legal', schema: 'legal' },
];

let _cachedDomains: Domain[] | null = null;

/** Path segments that are domain keys (for API client: /api/{segment}/...). */
let _domainKeySet: Set<string> = new Set(FALLBACK_DOMAINS.map(d => d.key));

function domainsList(): Domain[] {
  return _cachedDomains && _cachedDomains.length > 0
    ? _cachedDomains
    : FALLBACK_DOMAINS;
}

/** Nav / forms — reactive callers should re-read after registry fetch (e.g. DomainContext). */
export function getAvailableDomains(): Domain[] {
  return domainsList();
}

/** @deprecated Prefer getAvailableDomains() — kept for minimal churn in imports. */
export const AVAILABLE_DOMAINS: Domain[] = FALLBACK_DOMAINS;

/**
 * Apply domains from API (sorted by display_order). Updates routing set for apiConnectionManager.
 */
export function applyRegistryDomains(apiDomains: Domain[]): void {
  if (!apiDomains.length) {
    return;
  }
  _cachedDomains = apiDomains;
  _domainKeySet = new Set(apiDomains.map(d => d.key));
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('registryDomainsUpdated'));
  }
}

/** True if this first path segment after /api/ is a domain key (flat /api/{domain}/...). */
export function isRegistryDomainPathSegment(segment: string): boolean {
  return _domainKeySet.has(segment);
}

export function getDomainRouteAlternation(): string {
  return domainsList()
    .map(d => d.key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');
}

/** Keys in nav/API order — use for forms and filters that list all domains. */
export function getDomainKeysList(): DomainKey[] {
  return domainsList().map(d => d.key);
}

/** @deprecated Use getDomainKeysList() after registry load. */
export const DOMAIN_KEYS_LIST: DomainKey[] = FALLBACK_DOMAINS.map(d => d.key);

export function getDefaultDomainKey(): DomainKey {
  const list = domainsList();
  return list[0]?.key ?? 'politics';
}

/** Full URL for registry_domains — aligned with getCurrentApiUrl / getApiOrigin (see apiConnectionManager health). */
function getRegistryDomainsUrl(): string {
  const path = '/api/system_monitoring/registry_domains';
  const base = getCurrentApiUrl();
  const origin = getApiOrigin();
  if (!base || base === '') {
    return path;
  }
  const root = (origin !== '' ? origin : base).replace(/\/$/, '');
  return `${root}${path}`;
}

/**
 * Fetch active domains from the API.
 */
export async function fetchRegistryDomains(): Promise<Domain[]> {
  const url = getRegistryDomainsUrl();
  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) {
    throw new Error(`registry_domains HTTP ${res.status}`);
  }
  const body = (await res.json()) as {
    success?: boolean;
    data?: { domains?: Array<Record<string, unknown>> };
  };
  const raw = body.data?.domains;
  if (!body.success || !Array.isArray(raw) || !raw.length) {
    throw new Error('registry_domains: empty or invalid payload');
  }
  const out: Domain[] = [];
  for (const row of raw) {
    const key = String(row.domain_key || '').trim();
    const schema = String(row.schema_name || '').trim();
    const name = String(row.display_name || key || '').trim() || key;
    if (!key || !schema) {
      continue;
    }
    out.push({ key, name, schema });
  }
  if (!out.length) {
    throw new Error('registry_domains: no valid rows');
  }
  return out;
}

/**
 * Path after the domain segment: `/politics/storylines` → `/storylines`; `/politics` → `/dashboard`.
 */
export function getPathAfterDomain(pathname: string): string {
  const m = pathname.match(/^\/([^/]+)(\/.*)?$/);
  if (!m) {
    return '/dashboard';
  }
  const seg = m[1];
  const rest = m[2];
  if (!isValidDomain(seg)) {
    return '/dashboard';
  }
  return rest && rest.length > 0 ? rest : '/dashboard';
}

/**
 * Get current domain from localStorage or return default
 */
export const getCurrentDomain = (): DomainKey => {
  if (typeof window === 'undefined') {
    return getDefaultDomainKey();
  }

  const stored = localStorage.getItem('news_intelligence_domain');
  if (stored && isValidDomain(stored)) {
    return stored;
  }

  return getDefaultDomainKey();
};

/**
 * Set current domain in localStorage
 */
export const setCurrentDomain = (domain: DomainKey): void => {
  if (typeof window === 'undefined') {
    return;
  }

  if (isValidDomain(domain)) {
    localStorage.setItem('news_intelligence_domain', domain);
  }
};

/**
 * Validate if a string is a valid domain key
 */
export const isValidDomain = (domain: string): boolean => {
  return domainsList().some(d => d.key === domain);
};

/**
 * Get domain object by key
 */
export const getDomain = (key: DomainKey): Domain | undefined => {
  return domainsList().find(d => d.key === key);
};

/**
 * Lowercase tokens for domain keys, schema names, and display names (Topics: "that's a domain, not a topic").
 */
export function domainSearchHintTokensFrom(domains: Domain[]): Set<string> {
  const set = new Set<string>();
  const add = (s: string) => {
    const t = s.toLowerCase().trim();
    if (t) set.add(t);
  };
  for (const d of domains) {
    add(d.key);
    add(d.schema);
    add(d.schema.replace(/_/g, '-'));
    add(d.schema.replace(/_/g, ' '));
    add(d.name);
    add(d.name.replace(/\s*&\s*/g, ' and '));
    add(
      d.name
        .replace(/\s*&\s*/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
    );
  }
  return set;
}

/** Registry display name for a domain segment, else a readable title-case fallback. */
export function formatDomainLabel(
  domainKey: string | undefined | null
): string {
  if (!domainKey) return 'Domain';
  const d = getDomain(domainKey);
  if (d?.name) return d.name;
  return (
    domainKey.charAt(0).toUpperCase() +
    domainKey.slice(1).replace(/-/g, ' ')
  );
}

/**
 * Get domain schema name from domain key
 */
export const getDomainSchema = (domain: DomainKey): string => {
  const domainObj = getDomain(domain);
  return domainObj?.schema || 'politics_2';
};
