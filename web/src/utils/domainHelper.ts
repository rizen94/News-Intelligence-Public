/**
 * Domain Helper Utility
 * Provides domain context and helper functions for v4.0 multi-domain architecture
 */

export type DomainKey = 'politics' | 'finance' | 'science-tech';

export interface Domain {
  key: DomainKey;
  name: string;
  schema: string;
}

export const AVAILABLE_DOMAINS: Domain[] = [
  { key: 'politics', name: 'Politics', schema: 'politics' },
  { key: 'finance', name: 'Finance', schema: 'finance' },
  { key: 'science-tech', name: 'Science & Technology', schema: 'science_tech' },
];

const DEFAULT_DOMAIN: DomainKey = 'politics';

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



