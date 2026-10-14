/**
 * Redirects away from routes that are admin/ops-only when public demo read-only is on.
 */
import React from 'react';
import { Navigate } from 'react-router-dom';
import { usePublicDemoMode } from '../../contexts/PublicDemoContext';
import { NEWS_HOME } from '../../paths';

type Props = { children: React.ReactNode };

export const DemoRouteGuard: React.FC<Props> = ({ children }) => {
  const { readonly, loading } = usePublicDemoMode();

  if (loading) return null;
  if (readonly) {
    return <Navigate to={NEWS_HOME} replace />;
  }
  return <>{children}</>;
};
