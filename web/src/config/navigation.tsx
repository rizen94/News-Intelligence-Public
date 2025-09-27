/**
 * Navigation Configuration for News Intelligence System v3.3.0
 * Organized by user type and functionality
 */

import React from 'react';
import {
  Dashboard as DashboardIcon,
  Article as ArticleIcon,
  RssFeed as RssFeedIcon,
  Timeline as TimelineIcon,
  Settings as SettingsIcon,
  HealthAndSafety as HealthIcon,
  Psychology as PsychologyIcon,
  Assessment as AssessmentIcon,
  BugReport as BugReportIcon,
  AdminPanelSettings as AdminIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';

export interface NavigationItem {
  text: string;
  icon: React.ReactElement;
  path: string;
  description?: string;
  requiresAuth?: boolean;
  adminOnly?: boolean;
  category?: 'main' | 'admin' | 'system';
}

// Main navigation items for all users
export const mainNavigationItems: NavigationItem[] = [
  {
    text: 'Dashboard',
    icon: <DashboardIcon />,
    path: '/',
    description: 'Main dashboard with system overview',
    category: 'main',
  },
  {
    text: 'Articles',
    icon: <ArticleIcon />,
    path: '/articles',
    description: 'Browse and manage news articles',
    category: 'main',
  },
  {
    text: 'Storylines',
    icon: <TimelineIcon />,
    path: '/storylines',
    description: 'Create and manage storylines',
    category: 'main',
  },
  {
    text: 'Intelligence',
    icon: <PsychologyIcon />,
    path: '/intelligence',
    description: 'AI-powered insights and analysis',
    category: 'main',
  },
  {
    text: 'RSS Feeds',
    icon: <RssFeedIcon />,
    path: '/rss-feeds',
    description: 'Manage news sources and feeds',
    category: 'main',
  },
  {
    text: 'Settings',
    icon: <SettingsIcon />,
    path: '/settings',
    description: 'User preferences and configuration',
    category: 'main',
  },
];

// Advanced features for power users (hidden by default)
export const advancedNavigationItems: NavigationItem[] = [
  {
    text: 'Enhanced Dashboard',
    icon: <AssessmentIcon />,
    path: '/phase2-dashboard',
    description: 'Advanced dashboard with real-time monitoring',
    category: 'admin',
    adminOnly: true,
  },
  {
    text: 'System Monitoring',
    icon: <HealthIcon />,
    path: '/monitoring',
    description: 'System health and performance monitoring',
    category: 'admin',
    adminOnly: true,
  },
  {
    text: 'Real-time Logs',
    icon: <BugReportIcon />,
    path: '/realtime-monitor',
    description: 'Live system logs and debugging',
    category: 'system',
    adminOnly: true,
  },
  {
    text: 'System Analytics',
    icon: <AssessmentIcon />,
    path: '/analytics',
    description: 'Advanced system analytics and metrics',
    category: 'system',
    adminOnly: true,
  },
  {
    text: 'System Health',
    icon: <HealthIcon />,
    path: '/health',
    description: 'Detailed system health information',
    category: 'system',
    adminOnly: true,
  },
];

// Navigation categories
export const navigationCategories = {
  main: {
    title: 'Main Features',
    description: 'Core functionality for news analysis',
  },
  admin: {
    title: 'Administration',
    description: 'Advanced features for system administrators',
  },
  system: {
    title: 'System Tools',
    description: 'Technical tools for system monitoring and debugging',
  },
};

// Helper functions
export const getNavigationByCategory = (category: 'main' | 'admin' | 'system') => {
  return [...mainNavigationItems, ...advancedNavigationItems].filter(
    item => item.category === category,
  );
};

export const getMainNavigation = () => {
  return mainNavigationItems;
};

export const getAdvancedNavigation = () => {
  return advancedNavigationItems;
};

export const getAdminNavigation = () => {
  return advancedNavigationItems.filter(item => item.adminOnly);
};

export const getSystemNavigation = () => {
  return advancedNavigationItems.filter(item => item.category === 'system');
};

// Check if user has access to advanced features
export const hasAdvancedAccess = (userRole: string = 'user') => {
  return ['admin', 'developer', 'system'].includes(userRole.toLowerCase());
};

// Get navigation items based on user role
export const getNavigationForUser = (userRole: string = 'user') => {
  const mainItems = getMainNavigation();

  if (hasAdvancedAccess(userRole)) {
    return {
      main: mainItems,
      advanced: getAdvancedNavigation(),
    };
  }

  return {
    main: mainItems,
    advanced: [],
  };
};
