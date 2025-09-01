import React from 'react';
import {
  Breadcrumbs as MuiBreadcrumbs,
  Link,
  Typography,
  Box,
} from '@mui/material';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  Home as HomeIcon,
  Article as ArticleIcon,
  GroupWork as ClusterIcon,
  Person as PersonIcon,
  RssFeed as SourceIcon,
  Search as SearchIcon,
  Settings as SettingsIcon,
  Monitor as MonitorIcon,
} from '@mui/icons-material';

const getPageIcon = (path) => {
  switch (path) {
    case '/':
    case '/dashboard':
      return <HomeIcon fontSize="small" />;
    case '/articles':
      return <ArticleIcon fontSize="small" />;
    case '/clusters':
      return <ClusterIcon fontSize="small" />;
    case '/entities':
      return <PersonIcon fontSize="small" />;
    case '/sources':
      return <SourceIcon fontSize="small" />;
    case '/search':
      return <SearchIcon fontSize="small" />;
    case '/settings':
      return <SettingsIcon fontSize="small" />;
    case '/monitoring':
      return <MonitorIcon fontSize="small" />;
    default:
      return null;
  }
};

const getPageTitle = (path) => {
  switch (path) {
    case '/':
    case '/dashboard':
      return 'Dashboard';
    case '/articles':
      return 'Articles';
    case '/clusters':
      return 'Clusters';
    case '/entities':
      return 'Entities';
    case '/sources':
      return 'Sources';
    case '/search':
      return 'Search';
    case '/settings':
      return 'Settings';
    case '/monitoring':
      return 'Monitoring';
    default:
      return 'Unknown';
  }
};

export default function Breadcrumb() {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);

  const breadcrumbItems = [
    {
      path: '/',
      title: 'Home',
      icon: <HomeIcon fontSize="small" />,
    },
    ...pathnames.map((name, index) => {
      const path = `/${pathnames.slice(0, index + 1).join('/')}`;
      return {
        path,
        title: getPageTitle(path),
        icon: getPageIcon(path),
      };
    }),
  ];

  return (
    <Box sx={{ mb: 2 }}>
      <MuiBreadcrumbs aria-label="breadcrumb" separator="›">
        {breadcrumbItems.map((item, index) => {
          const isLast = index === breadcrumbItems.length - 1;
          
          if (isLast) {
            return (
              <Typography
                key={item.path}
                color="text.primary"
                sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
              >
                {item.icon}
                {item.title}
              </Typography>
            );
          }

          return (
            <Link
              key={item.path}
              component={RouterLink}
              to={item.path}
              color="inherit"
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                textDecoration: 'none',
                '&:hover': {
                  textDecoration: 'underline',
                },
              }}
            >
              {item.icon}
              {item.title}
            </Link>
          );
        })}
      </MuiBreadcrumbs>
    </Box>
  );
}
