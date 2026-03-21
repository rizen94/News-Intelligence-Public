/**
 * Domain Context Provider
 * Provides domain context throughout the application for v5.0 multi-domain architecture
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import {
  getCurrentDomain,
  setCurrentDomain,
  isValidDomain,
  AVAILABLE_DOMAINS,
  DomainKey,
  Domain,
} from '../utils/domainHelper';

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
  const [domain, setDomainState] = useState<DomainKey>(getCurrentDomain());

  // Update domain and persist to localStorage
  const setDomain = (newDomain: DomainKey) => {
    if (isValidDomain(newDomain)) {
      setDomainState(newDomain);
      setCurrentDomain(newDomain);
      // Trigger a custom event so components can react to domain changes
      window.dispatchEvent(
        new CustomEvent('domainChanged', { detail: { domain: newDomain } })
      );
    } else {
      console.warn(`Invalid domain: ${newDomain}`);
    }
  };

  // Get domain name for display
  const domainObj = AVAILABLE_DOMAINS.find(d => d.key === domain);
  const domainName = domainObj?.name || 'Politics';

  // Listen for domain changes from other components
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

  // Load domain from localStorage on mount
  useEffect(() => {
    const storedDomain = getCurrentDomain();
    if (storedDomain !== domain) {
      setDomainState(storedDomain);
    }
  }, []);

  const value: DomainContextType = {
    domain,
    setDomain,
    availableDomains: AVAILABLE_DOMAINS,
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
