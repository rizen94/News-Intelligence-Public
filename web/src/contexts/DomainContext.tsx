/**
 * Domain Context Provider
 * Provides domain context throughout the application for v5.0 multi-domain architecture
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback,
  ReactNode,
} from 'react';
import {
  getCurrentDomain,
  setCurrentDomain,
  isValidDomain,
  getAvailableDomains,
  fetchRegistryDomains,
  applyRegistryDomains,
  getDefaultDomainKey,
  type DomainKey,
  type Domain,
} from '../utils/domainHelper';

import loggingService from '../services/loggingService';

interface DomainContextType {
  domain: DomainKey;
  setDomain: (domain: DomainKey) => void;
  availableDomains: Domain[];
  domainName: string;
}

const DomainContext = createContext<DomainContextType | undefined>(undefined);

interface DomainProviderProps {
  children: ReactNode;
}

export const DomainProvider: React.FC<DomainProviderProps> = ({ children }) => {
  const [domain, setDomainState] = useState<DomainKey>(() =>
    getCurrentDomain()
  );
  const [registryTick, setRegistryTick] = useState(0);

  const loadRegistryDomainsFromApi = useCallback(async () => {
    try {
      const list = await fetchRegistryDomains();
      if (!list.length) {
        return;
      }
      applyRegistryDomains(list);
      const stored =
        typeof window !== 'undefined'
          ? localStorage.getItem('news_intelligence_domain')
          : null;
      const fallback = getDefaultDomainKey();
      const next = stored && isValidDomain(stored) ? stored : fallback;
      setCurrentDomain(next);
      setDomainState(next);
      setRegistryTick(t => t + 1);
    } catch (e) {
      loggingService.warn('registry_domains fetch failed; using fallback list', {
        error: (e as Error)?.message,
      });
    }
  }, []);

  useEffect(() => {
    void loadRegistryDomainsFromApi();
  }, [loadRegistryDomainsFromApi]);

  useEffect(() => {
    const onApiUrlChanged = () => void loadRegistryDomainsFromApi();
    if (typeof window !== 'undefined') {
      window.addEventListener('apiUrlChanged', onApiUrlChanged);
      return () => window.removeEventListener('apiUrlChanged', onApiUrlChanged);
    }
    return undefined;
  }, [loadRegistryDomainsFromApi]);

  useEffect(() => {
    const onUpdate = () => setRegistryTick(t => t + 1);
    if (typeof window !== 'undefined') {
      window.addEventListener('registryDomainsUpdated', onUpdate);
      return () =>
        window.removeEventListener('registryDomainsUpdated', onUpdate);
    }
    return undefined;
  }, []);

  const availableDomains = useMemo(
    () => getAvailableDomains(),
    [registryTick]
  );

  const setDomain = (newDomain: DomainKey) => {
    if (isValidDomain(newDomain)) {
      setDomainState(newDomain);
      setCurrentDomain(newDomain);
      window.dispatchEvent(
        new CustomEvent('domainChanged', { detail: { domain: newDomain } })
      );
    } else {
      loggingService.warn(`Invalid domain: ${newDomain}`);
    }
  };

  const domainObj = availableDomains.find(d => d.key === domain);
  const domainName = domainObj?.name || 'Politics';

  useEffect(() => {
    const handleDomainChange = (event: CustomEvent) => {
      const newDomain = event.detail?.domain;
      if (newDomain && isValidDomain(newDomain) && newDomain !== domain) {
        setDomainState(newDomain);
      }
    };

    window.addEventListener(
      'domainChanged',
      handleDomainChange as (event: Event) => void
    );

    return () => {
      window.removeEventListener(
        'domainChanged',
        handleDomainChange as (event: Event) => void
      );
    };
  }, [domain]);

  useEffect(() => {
    const storedDomain = getCurrentDomain();
    if (storedDomain !== domain) {
      setDomainState(storedDomain);
    }
  }, []);

  const value: DomainContextType = {
    domain,
    setDomain,
    availableDomains,
    domainName,
  };

  return (
    <DomainContext.Provider value={value}>{children}</DomainContext.Provider>
  );
};

export const useDomain = (): DomainContextType => {
  const context = useContext(DomainContext);
  if (context === undefined) {
    throw new Error('useDomain must be used within a DomainProvider');
  }
  return context;
};

export default DomainContext;
