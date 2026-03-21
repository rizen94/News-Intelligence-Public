/**
 * Domain Breadcrumb Component
 * Shows domain context in page breadcrumbs
 */

import React from 'react';
import { Breadcrumbs, Link, Typography, Chip, Box } from '@mui/material';
import { Home, NavigateNext } from '@mui/icons-material';
import { useDomain } from '../../../contexts/DomainContext';
import { useDomainRoute } from '../../../hooks/useDomainRoute';
import { useNavigate } from 'react-router-dom';

interface DomainBreadcrumbProps {
  items?: Array<{ label: string; path?: string; icon?: React.ReactElement }>;
  showDomain?: boolean;
}

const DomainBreadcrumb: React.FC<DomainBreadcrumbProps> = ({
  items = [],
  showDomain = true,
}) => {
  const { domainName, domain } = useDomain();
  const { getDomainPath } = useDomainRoute();
  const navigate = useNavigate();

  // Domain-specific color
  const getDomainColor = () => {
    switch (domain) {
      case 'politics':
        return 'primary';
      case 'finance':
        return 'success';
      case 'science-tech':
        return 'secondary';
      default:
        return 'default';
    }
  };

  const breadcrumbItems: Array<{
    label: string;
    path?: string;
    icon?: React.ReactElement;
  }> = [
    {
      label: 'Home',
      path: getDomainPath('/dashboard'),
      icon: <Home fontSize='small' />,
    },
    ...items,
  ];

  return (
    <Box sx={{ mb: 2 }}>
      <Breadcrumbs
        separator={<NavigateNext fontSize='small' />}
        aria-label='breadcrumb'
      >
        {breadcrumbItems.map((item, index) => {
          const isLast = index === breadcrumbItems.length - 1;

          if (isLast) {
            return (
              <Typography
                key={index}
                color='text.primary'
                sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
              >
                {item.icon || null}
                {item.label}
              </Typography>
            );
          }

          return (
            <Link
              key={index}
              component='button'
              variant='body2'
              onClick={() => item.path && navigate(item.path)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                textDecoration: 'none',
                '&:hover': {
                  textDecoration: 'underline',
                },
              }}
            >
              {item.icon || null}
              {item.label}
            </Link>
          );
        })}
        {showDomain && (
          <Chip
            label={domainName}
            size='small'
            color={getDomainColor() as any}
            sx={{ ml: 1 }}
          />
        )}
      </Breadcrumbs>
    </Box>
  );
};

export default DomainBreadcrumb;
