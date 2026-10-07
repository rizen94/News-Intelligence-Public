/**
 * Redirect legacy /v2/* bookmarks onto primary-domain paths.
 * /v2?domain=politics → /?domain=politics
 * /v2 (no domain) → /?domain=politics (former default home)
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { stripLegacyV2Path, NEWS_HOME } from '../paths';
import { getDefaultDomainKey } from '../utils/domainHelper';

export default function LegacyV2Redirect() {
  const { pathname, search, hash } = useLocation();
  const targetPath = stripLegacyV2Path(pathname);
  const params = new URLSearchParams(search);
  if (
    (targetPath === NEWS_HOME || targetPath === '') &&
    !params.has('domain')
  ) {
    params.set('domain', getDefaultDomainKey());
  }
  const qs = params.toString();
  return (
    <Navigate
      to={`${targetPath || NEWS_HOME}${qs ? `?${qs}` : ''}${hash}`}
      replace
    />
  );
}
