/**
 * Domain Helper Utility
 * Provides domain context and helper functions for v5.0 multi-domain architecture
 */

export type DomainKey = 'politics' | 'finance' | 'science-tech' | 'legal';

export interface Domain {
  key: DomainKey;
  name: string;
  schema: string;
}

export const AVAILABLE_DOMAINS: Domain[] = [
  { key: 'politics', name: 'Politics', schema: 'politics' },
  { key: 'finance', name: 'Finance', schema: 'finance' },
  { key: 'science-tech', name: 'Science & Technology', schema: 'science_tech' },
  { key: 'legal', name: 'Legal', schema: 'legal' },
];

/** Alternation for first path segment after `/` (domain keys). Keep in sync with AVAILABLE_DOMAINS. */
export const DOMAIN_ROUTE_ALTERNATION = AVAILABLE_DOMAINS.map(d => d.key).join(
  '|'
);

/** Keys in nav/API order — use for forms and filters that list all domains. */
export const DOMAIN_KEYS_LIST: DomainKey[] = AVAILABLE_DOMAINS.map(d => d.key);

const DEFAULT_DOMAIN: DomainKey = 'politics';

/**
 * Path after the domain segment: `/politics/storylines` → `/storylines`; `/legal` → `/dashboard`.
 */
export function getPathAfterDomain(pathname: string): string {
  const re = new RegExp(`^/(?:${DOMAIN_ROUTE_ALTERNATION})(/.*)?$`);
  const m = pathname.match(re);
  return m?.[1] || '/dashboard';
}

/**
 * Get current domain from localStorage or return default
 */
export const getCurrentDomain = (): DomainKey => {
  if (typeof window === 'undefined') {
    return DEFAULT_DOMAIN;
  }

  const stored = localStorage.getItem('news_intelligence_domain');
  if (stored && isValidDomain(stored)) {
    return stored as DomainKey;
  }

  return DEFAULT_DOMAIN;
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
  return AVAILABLE_DOMAINS.some(d => d.key === domain);
};

/**
 * Get domain object by key
 */
export const getDomain = (key: DomainKey): Domain | undefined => {
  return AVAILABLE_DOMAINS.find(d => d.key === key);
};

/**
 * Get domain schema name from domain key
 */
export const getDomainSchema = (domain: DomainKey): string => {
  const domainObj = getDomain(domain);
  return domainObj?.schema || 'politics';
};
