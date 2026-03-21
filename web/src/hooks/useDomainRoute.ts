/**
 * Domain Route Hook
 * Provides utilities for working with domain-aware routes
 */

import { useLocation, useParams } from 'react-router-dom';
import { useDomain } from '../contexts/DomainContext';
import { isValidDomain, DomainKey, getPathAfterDomain } from '../utils/domainHelper';

export const useDomainRoute = () => {
  const { domain: urlDomain } = useParams<{ domain: string }>();
  const { domain: contextDomain } = useDomain();
  const { pathname } = useLocation();

  // Use URL domain if available, otherwise fall back to context
  const effectiveDomain = (urlDomain && isValidDomain(urlDomain))
    ? urlDomain as DomainKey
    : contextDomain;

  /**
   * Get the current path without the domain prefix
   */
  const getCurrentPathWithoutDomain = (): string => getPathAfterDomain(pathname);

  /**
   * Get a domain-qualified path
   */
  const getDomainPath = (path: string, targetDomain?: DomainKey): string => {
    const domain = targetDomain || effectiveDomain;
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `/${domain}${normalizedPath}`;
  };

  /**
   * Check if we're in a specific domain
   */
  const isInDomain = (checkDomain: DomainKey): boolean => {
    return effectiveDomain === checkDomain;
  };

  return {
    domain: effectiveDomain,
    urlDomain: urlDomain as DomainKey | undefined,
    contextDomain,
    getCurrentPathWithoutDomain,
    getDomainPath,
    isInDomain,
  };
};
