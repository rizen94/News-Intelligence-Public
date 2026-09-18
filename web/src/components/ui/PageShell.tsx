import React from 'react';
import { Box, Typography, Breadcrumbs, Link } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

export type PageShellProps = {
  title: string;
  subtitle?: string;
  breadcrumbs?: { label: string; to?: string }[];
  actions?: React.ReactNode;
  children: React.ReactNode;
};

export function PageShell({ title, subtitle, breadcrumbs, actions, children }: PageShellProps) {
  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto' }}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs sx={{ mb: 1.5, fontSize: '0.85rem' }}>
          {breadcrumbs.map((crumb, i) =>
            crumb.to ? (
              <Link key={i} component={RouterLink} to={crumb.to} underline='hover' color='inherit'>
                {crumb.label}
              </Link>
            ) : (
              <Typography key={i} color='text.primary' fontSize='inherit'>
                {crumb.label}
              </Typography>
            ),
          )}
        </Breadcrumbs>
      )}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2, gap: 2 }}>
        <Box>
          <Typography variant='h5' fontWeight={700}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant='body2' color='text.secondary' sx={{ mt: 0.5 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions}
      </Box>
      {children}
    </Box>
  );
}
