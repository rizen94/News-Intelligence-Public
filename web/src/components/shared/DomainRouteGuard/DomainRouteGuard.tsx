/**
 * Domain Route Guard Component
 * Validates domain parameter and redirects if invalid
 * Never returns null - shows loading to avoid blank white screen
 */

import React, { useEffect, ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';
import {
  getDefaultDomainKey,
  isValidDomain,
} from '../../../utils/domainHelper';

interface DomainRouteGuardProps {
  children: ReactNode;
}

const DomainRouteGuard: React.FC<DomainRouteGuardProps> = ({ children }) => {
  const { domain } = useParams<{ domain: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    if (!domain || !isValidDomain(domain)) {
      navigate(`/${getDefaultDomainKey()}/dashboard`, { replace: true });
    }
  }, [domain, navigate]);

  if (!domain || !isValidDomain(domain)) {
    // Show loading instead of null - prevents blank white screen
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 300,
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant='body2' color='text.secondary'>
          Loading...
        </Typography>
      </Box>
    );
  }

  return <>{children}</>;
};

export default DomainRouteGuard;
