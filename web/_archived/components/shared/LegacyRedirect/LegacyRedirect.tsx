/**
 * Legacy Redirect Component
 * Handles redirects from old routes to new domain-aware routes
 */

import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { getDefaultDomainKey } from '../../../utils/domainHelper';

interface LegacyRedirectProps {
  to: string;
  preserveParams?: boolean;
}

const LegacyRedirect: React.FC<LegacyRedirectProps> = ({
  to,
  preserveParams = false,
}) => {
  const params = useParams();

  const prefix = `/${getDefaultDomainKey()}`;

  if (preserveParams) {
    // Build path with preserved parameters
    let path = `${prefix}${to}`;

    // Replace parameter placeholders with actual values
    Object.keys(params).forEach(key => {
      const value = params[key];
      if (value) {
        path = path.replace(`:${key}`, value);
      }
    });

    return <Navigate to={path} replace />;
  }

  return <Navigate to={`${prefix}${to}`} replace />;
};

export default LegacyRedirect;
