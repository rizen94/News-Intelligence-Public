/**
 * Main layout — Hero status bar, sidebar nav, domain switcher, content outlet.
 * Replaces the old Header + Navigation + DomainLayout.
 */
import React, { useEffect } from 'react';
import { Outlet, useParams, useNavigate, Navigate } from 'react-router-dom';
import { Box, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { HeroStatusBar } from './HeroStatusBar';
import { AppNav, APP_NAV_WIDTH } from './AppNav';
import { useDomain } from '../contexts/DomainContext';
import { isValidDomain } from '../utils/domainHelper';

const MainLayout: React.FC = () => {
  const { domain: urlDomain } = useParams<{ domain: string }>();
  const { domain: contextDomain, setDomain, availableDomains } = useDomain();
  const navigate = useNavigate();

  useEffect(() => {
    if (urlDomain && isValidDomain(urlDomain) && urlDomain !== contextDomain) {
      setDomain(urlDomain as 'politics' | 'finance' | 'science-tech');
    }
  }, [urlDomain, contextDomain, setDomain]);

  if (!urlDomain || !isValidDomain(urlDomain)) {
    return <Navigate to="/politics/dashboard" replace />;
  }

  const handleDomainChange = (newDomain: string) => {
    if (isValidDomain(newDomain)) {
      setDomain(newDomain as 'politics' | 'finance' | 'science-tech');
      navigate(`/${newDomain}/dashboard`, { replace: true });
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <HeroStatusBar />
      <Box sx={{ display: 'flex', flex: 1 }}>
        <AppNav />
        <Box
          component="main"
          sx={{
            flex: 1,
            width: { md: `calc(100% - ${APP_NAV_WIDTH}px)` },
            p: 2,
            bgcolor: 'grey.50',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Domain</InputLabel>
              <Select
                value={contextDomain}
                label="Domain"
                onChange={(e) => handleDomainChange(e.target.value)}
              >
                {availableDomains.map((d) => (
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
