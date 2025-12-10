/**
 * Domain Route Guard Component
 * Validates domain parameter and redirects if invalid
 */

import React, { useEffect, ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { isValidDomain } from '../../../utils/domainHelper';

interface DomainRouteGuardProps {
  children: ReactNode;
}

const DomainRouteGuard: React.FC<DomainRouteGuardProps> = ({ children }) => {
  const { domain } = useParams<{ domain: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    if (!domain || !isValidDomain(domain)) {
      // Invalid domain, redirect to default
      navigate('/politics/dashboard', { replace: true });
    }
  }, [domain, navigate]);

  if (!domain || !isValidDomain(domain)) {
    return null; // Will redirect in useEffect
  }

  return <>{children}</>;
};

export default DomainRouteGuard;



