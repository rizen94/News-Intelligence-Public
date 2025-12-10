/**
 * Domain Navigation Hook
 * Provides utilities for navigating within and between domains
 */

import { useNavigate } from 'react-router-dom';
import { useDomain } from '../contexts/DomainContext';
import { isValidDomain, DomainKey } from '../utils/domainHelper';

export const useDomainNavigation = () => {
  const { domain } = useDomain();
  const navigate = useNavigate();

  /**
   * Navigate to a path within the current domain
   */
  const navigateToDomain = (path: string, targetDomain?: DomainKey) => {
    const effectiveDomain = targetDomain || domain;
    if (isValidDomain(effectiveDomain)) {
      // Ensure path starts with /
      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      navigate(`/${effectiveDomain}${normalizedPath}`);
    }
  };

  /**
   * Switch to a different domain, optionally preserving the current path
   */
  const switchDomain = (newDomain: DomainKey, preservePath: boolean = true) => {
    if (!isValidDomain(newDomain)) {
      console.warn(`Invalid domain: ${newDomain}`);
      return;
    }

    if (preservePath) {
      // Get current path without domain
      const currentPath = window.location.pathname;
      const pathMatch = currentPath.match(/^\/(?:politics|finance|science-tech)(\/.*)?$/);
      const pathWithoutDomain = pathMatch?.[1] || '/dashboard';
      navigate(`/${newDomain}${pathWithoutDomain}`);
    } else {
      navigate(`/${newDomain}/dashboard`);
    }
  };

  /**
   * Get the full domain path for a given route
   */
  const getDomainPath = (path: string, targetDomain?: DomainKey): string => {
    const effectiveDomain = targetDomain || domain;
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `/${effectiveDomain}${normalizedPath}`;
  };

  return {
    navigateToDomain,
    switchDomain,
    getDomainPath,
  };
};
