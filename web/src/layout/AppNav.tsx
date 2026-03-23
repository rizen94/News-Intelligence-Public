/**
 * Sidebar navigation — Dashboard, Discover, Investigate, Monitor, Analyze.
 */
import React, { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Drawer,
  ListSubheader,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ExploreIcon from '@mui/icons-material/Explore';
import SearchIcon from '@mui/icons-material/Search';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AutoStoriesIcon from '@mui/icons-material/AutoStories';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import NewspaperIcon from '@mui/icons-material/Newspaper';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import LabelIcon from '@mui/icons-material/Label';
import VisibilityIcon from '@mui/icons-material/Visibility';
import EventNoteIcon from '@mui/icons-material/EventNote';
import ChecklistIcon from '@mui/icons-material/Checklist';
import TableChartIcon from '@mui/icons-material/TableChart';
import { usePublicDemoMode } from '../contexts/PublicDemoContext';
import { getDefaultDomainKey } from '../utils/domainHelper';

export const APP_NAV_WIDTH = 220;

type NavItem = {
  path: string;
  label: string;
  icon: React.ReactNode;
  domain?: string;
};
type NavSection = { id: string; label: string; items: NavItem[] };

const NAV_SECTIONS: NavSection[] = [
  {
    id: 'overview',
    label: 'Overview',
    items: [{ path: 'dashboard', label: 'Dashboard', icon: <DashboardIcon /> }],
  },
  {
    id: 'corpus',
    label: 'Corpus',
    items: [
      { path: 'articles', label: 'Articles', icon: <NewspaperIcon /> },
      { path: 'rss_feeds', label: 'RSS Feeds', icon: <RssFeedIcon /> },
    ],
  },
  {
    id: 'stories',
    label: 'Stories',
    items: [
      { path: 'storylines', label: 'Storylines', icon: <AutoStoriesIcon /> },
    ],
  },
  {
    id: 'signals',
    label: 'Signals',
    items: [
      { path: 'topics', label: 'Topics', icon: <LabelIcon /> },
      { path: 'events', label: 'Events', icon: <EventNoteIcon /> },
    ],
  },
  {
    id: 'investigate',
    label: 'Investigate',
    items: [
      { path: 'discover', label: 'Discover', icon: <ExploreIcon /> },
      { path: 'investigate', label: 'Investigate', icon: <SearchIcon /> },
    ],
  },
  {
    id: 'outputs',
    label: 'Outputs',
    items: [
      { path: 'briefings', label: 'Briefings', icon: <MenuBookIcon /> },
      { path: 'report', label: "Today's Report", icon: <NewspaperIcon /> },
      { path: 'watchlist', label: 'Watchlist', icon: <VisibilityIcon /> },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { path: 'monitor', label: 'Monitor', icon: <MonitorHeartIcon /> },
      {
        path: 'monitor/sql-explorer',
        label: 'SQL explorer',
        icon: <TableChartIcon />,
      },
      {
        path: 'audit-checklist',
        label: 'Audit checklist',
        icon: <ChecklistIcon />,
      },
      { path: 'analyze', label: 'Analyze (planned)', icon: <AnalyticsIcon /> },
    ],
  },
  {
    id: 'finance',
    label: 'Finance',
    items: [
      {
        path: 'commodity/gold',
        label: 'Commodity',
        icon: <ShowChartIcon />,
        domain: 'finance',
      },
    ],
  },
];

export function AppNav() {
  const { domain } = useParams<{ domain: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { readonly: demoReadonly } = usePublicDemoMode();

  const base = `/${domain ?? getDefaultDomainKey()}`;

  const sections = NAV_SECTIONS.map(section => ({
    ...section,
    items: section.items.filter(item => {
      if (item.domain && item.domain !== domain) return false;
      if (demoReadonly) {
        if (section.id === 'operations') return false;
        if (item.path === 'rss_feeds' || item.path === 'watchlist') return false;
        if (item.path?.startsWith('commodity')) return false;
      }
      return true;
    }),
  })).filter(section => section.items.length > 0);
  const navContent = (
    <Box sx={{ pt: 2, width: APP_NAV_WIDTH }}>
      {sections.map(section => (
        <List
          key={section.id}
          dense
          subheader={
            <ListSubheader
              component='div'
              disableSticky
              sx={{ lineHeight: '28px', fontSize: '0.72rem', fontWeight: 700 }}
            >
              {section.label}
            </ListSubheader>
          }
        >
          {section.items.map(({ path, label, icon }) => {
            const fullPath = `${base}/${path}`;
            const monitorExact = `${base}/monitor`;
            let navSelected = location.pathname === fullPath;
            if (!navSelected && !path.includes('/')) {
              navSelected = location.pathname.startsWith(`${fullPath}/`);
              if (
                path === 'monitor' &&
                location.pathname.startsWith(`${base}/monitor/`) &&
                location.pathname !== monitorExact
              ) {
                navSelected = false;
              }
            }
            return (
              <ListItemButton
                key={path}
                selected={navSelected}
                onClick={() => {
                  navigate(`${base}/${path}`);
                  setMobileOpen(false);
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>{icon}</ListItemIcon>
                <ListItemText primary={label} />
              </ListItemButton>
            );
          })}
        </List>
      ))}
    </Box>
  );

  return (
    <>
      <Drawer
        variant='temporary'
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            width: APP_NAV_WIDTH,
            boxSizing: 'border-box',
          },
        }}
      >
        <Box sx={{ px: 1, py: 2, fontWeight: 600 }}>NewsIntel</Box>
        {navContent}
      </Drawer>
      <Drawer
        variant='permanent'
        sx={{
          display: { xs: 'none', md: 'block' },
          width: APP_NAV_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: APP_NAV_WIDTH,
            boxSizing: 'border-box',
            mt: 0,
            borderRight: 1,
            borderColor: 'divider',
          },
        }}
        open
      >
        <Box sx={{ px: 1, py: 2, fontWeight: 600 }}>NewsIntel</Box>
        {navContent}
      </Drawer>
    </>
  );
}
