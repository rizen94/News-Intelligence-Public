/**
 * Domain Navigation Hook — domain filter helpers for Finance / shared pages.
 */

import { useNavigate } from 'react-router-dom';
import { useDomain } from '../contexts/DomainContext';
import { isValidDomain, DomainKey } from '../utils/domainHelper';
import { NEWS_HOME, FINANCE_HOME } from '../paths';

export const useDomainNavigation = () => {
  const { domain } = useDomain();
  const navigate = useNavigate();

  const navigateToDomain = (path: string, _targetDomain?: DomainKey) => {
    // Classic domain spine retired — send callers to Finance or News.
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    if (normalizedPath.includes('finance') || normalizedPath.includes('commodity')) {
      navigate(`${FINANCE_HOME}${normalizedPath.replace(/^\/finance/, '')}`);
      return;
    }
    navigate(NEWS_HOME);
  };

  const switchDomain = (newDomain: DomainKey, _preservePath: boolean = true) => {
    if (!isValidDomain(newDomain)) {
      console.warn(`Invalid domain: ${newDomain}`);
      return;
    }
    navigate(`${NEWS_HOME}?domain=${encodeURIComponent(newDomain)}`);
  };

  const getDomainPath = (path: string, _targetDomain?: DomainKey): string => {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return normalizedPath.startsWith('/finance')
      ? normalizedPath
      : `${NEWS_HOME}${normalizedPath === '/' ? '' : normalizedPath}`;
  };

  return {
    navigateToDomain,
    switchDomain,
    getDomainPath,
    domain,
  };
};
