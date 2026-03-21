/**
 * Main layout for all authenticated-style dashboard pages.
 *
 * - Reads `domain` from the URL (`useParams`); syncs with `DomainContext`.
 * - Invalid/missing domain redirects to `/politics/dashboard`.
 * - Domain switcher preserves the path after the domain segment so users stay on
 *   the same feature (e.g. storylines) when changing politics → finance.
 * - Renders `HeroStatusBar`, `AppNav` (sidebar), and `<Outlet />` for child routes
 *   defined in `App.tsx`.
 */
import React, { useEffect } from 'react';
import {
  Outlet,
  useParams,
  useNavigate,
  useLocation,
  Navigate,
} from 'react-router-dom';
import { Box, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { HeroStatusBar } from './HeroStatusBar';
import { AppNav, APP_NAV_WIDTH } from './AppNav';
import { useDomain } from '../contexts/DomainContext';
import {
  isValidDomain,
  type DomainKey,
  getPathAfterDomain,
} from '../utils/domainHelper';

const MainLayout: React.FC = () => {
  const { domain: urlDomain } = useParams<{ domain: string }>();
  const { domain: contextDomain, setDomain, availableDomains } = useDomain();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (urlDomain && isValidDomain(urlDomain) && urlDomain !== contextDomain) {
      setDomain(urlDomain as DomainKey);
    }
  }, [urlDomain, contextDomain, setDomain]);

  if (!urlDomain || !isValidDomain(urlDomain)) {
    return <Navigate to='/politics/dashboard' replace />;
  }

  const handleDomainChange = (newDomain: string) => {
    if (!isValidDomain(newDomain) || newDomain === contextDomain) return;
    setDomain(newDomain as DomainKey);
    // Stay on the same page: preserve path after domain (e.g. /politics/storylines/123 → /finance/storylines/123)
    const pathWithoutDomain = getPathAfterDomain(location.pathname);
    navigate(`/${newDomain}${pathWithoutDomain}`, { replace: true });
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <HeroStatusBar />
      <Box sx={{ display: 'flex', flex: 1 }}>
        <AppNav />
        <Box
          component='main'
          sx={{
            flex: 1,
            width: { md: `calc(100% - ${APP_NAV_WIDTH}px)` },
            p: 2,
            bgcolor: 'grey.50',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
            <FormControl size='small' sx={{ minWidth: 140 }}>
              <InputLabel>Domain</InputLabel>
              <Select
                value={contextDomain}
                label='Domain'
                onChange={e => handleDomainChange(e.target.value)}
              >
                {availableDomains.map(d => (
                  <MenuItem key={d.key} value={d.key}>
                    {d.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
};

export default MainLayout;
