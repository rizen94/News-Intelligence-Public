/**
 * Redirects away from routes that are admin/ops-only when public demo read-only is on.
 */
import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { usePublicDemoMode } from '../../contexts/PublicDemoContext';

type Props = { children: React.ReactNode };

export const DemoRouteGuard: React.FC<Props> = ({ children }) => {
  const { domain } = useParams<{ domain: string }>();
  const { readonly, loading } = usePublicDemoMode();

  if (loading) return null;
  if (readonly) {
    return <Navigate to={`/${domain ?? 'politics'}/dashboard`} replace />;
  }
  return <>{children}</>;
};
