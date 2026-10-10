/**
 * Domain Route Hook — domain context for Finance / Admin pages.
 * Classic /:domain spine is retired; paths resolve under /finance or News.
 */

import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import { useDomain } from '../contexts/DomainContext';
import {
  isValidDomain,
  DomainKey,
  getPathAfterDomain,
} from '../utils/domainHelper';

export const useDomainRoute = () => {
  const { domain: urlDomain } = useParams<{ domain: string }>();
  const [params] = useSearchParams();
  const { domain: contextDomain } = useDomain();
  const { pathname } = useLocation();

  const queryDomain = params.get('domain');
  const effectiveDomain =
    urlDomain && isValidDomain(urlDomain)
      ? (urlDomain as DomainKey)
      : queryDomain && isValidDomain(queryDomain)
        ? (queryDomain as DomainKey)
        : contextDomain;

  const getCurrentPathWithoutDomain = (): string =>
    getPathAfterDomain(pathname);

  /** Map legacy classic relative paths onto Finance product routes. */
  const getDomainPath = (path: string, _targetDomain?: DomainKey): string => {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    if (normalizedPath.startsWith('/finance')) {
      return normalizedPath;
    }
    if (normalizedPath.startsWith('/analysis')) {
      return `/finance/reporting${normalizedPath}`;
    }
    if (normalizedPath.startsWith('/trace')) {
      return `/finance/reporting/traces${normalizedPath.replace(/^\/trace/, '')}`;
    }
    if (normalizedPath.startsWith('/commodity')) {
      return `/finance/markets${normalizedPath}`;
    }
    return normalizedPath;
  };

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
