/**
 * Sidebar navigation — domain-scoped IA (Overview, Corpus, Stories, Signals, Investigate, Arcs, Outputs, Finance, Operations).
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
import SearchIcon from '@mui/icons-material/Search';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AutoStoriesIcon from '@mui/icons-material/AutoStories';
import NewspaperIcon from '@mui/icons-material/Newspaper';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import LabelIcon from '@mui/icons-material/Label';
import EventNoteIcon from '@mui/icons-material/EventNote';
import ChecklistIcon from '@mui/icons-material/Checklist';
import RateReviewIcon from '@mui/icons-material/RateReview';
import TableChartIcon from '@mui/icons-material/TableChart';
import HubIcon from '@mui/icons-material/Hub';
import TimelineIcon from '@mui/icons-material/Timeline';
import MapIcon from '@mui/icons-material/Map';
import ArticleIcon from '@mui/icons-material/Article';
import PsychologyIcon from '@mui/icons-material/Psychology';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import DescriptionIcon from '@mui/icons-material/Description';
import LinkIcon from '@mui/icons-material/Link';
import ScienceIcon from '@mui/icons-material/Science';
import MemoryIcon from '@mui/icons-material/Memory';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ExploreIcon from '@mui/icons-material/Explore';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { usePublicDemoMode } from '../contexts/PublicDemoContext';
import { getDefaultDomainKey } from '../utils/domainHelper';

export const APP_NAV_WIDTH = 220;

type NavItem = {
  path: string;
  label: string;
  icon: React.ReactNode;
  /** Show only when the URL domain segment matches (e.g. finance-only tools). */
  domain?: string;
  /** Navigate to this domain regardless of current URL domain (cross-silo link). */
  hrefDomain?: string;
  demoHidden?: boolean;
  exact?: boolean;
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
      { path: 'rss_feeds', label: 'RSS Feeds', icon: <RssFeedIcon />, demoHidden: true },
    ],
  },
  {
    id: 'stories',
    label: 'Stories',
    items: [
      { path: 'storylines', label: 'Storylines', icon: <AutoStoriesIcon /> },
      {
        path: 'storylines/discovery',
        label: 'Embedding catch-up',
        icon: <ExploreIcon />,
        demoHidden: true,
      },
      {
        path: 'storylines/review-queue',
        label: 'Review queue',
        icon: <RateReviewIcon />,
        demoHidden: true,
      },
    ],
  },
  {
    id: 'signals',
    label: 'Signals',
    items: [
      { path: 'topics', label: 'Topics (staging)', icon: <LabelIcon /> },
      { path: 'events', label: 'Timeline atoms', icon: <EventNoteIcon /> },
    ],
  },
  {
    id: 'investigate',
    label: 'Investigate',
    items: [
      { path: 'investigate', label: 'Hub', icon: <HubIcon />, exact: true },
      { path: 'investigate/entities', label: 'Entities', icon: <AccountTreeIcon /> },
      { path: 'investigate/search', label: 'Search', icon: <SearchIcon /> },
      { path: 'investigate/documents', label: 'Documents', icon: <DescriptionIcon /> },
      {
        path: 'investigate/narrative-threads',
        label: 'Narrative threads (derived)',
        icon: <AutoStoriesIcon />,
      },
      {
        path: 'investigate/entity-resolution',
        label: 'Entity resolution',
        icon: <LinkIcon />,
      },
      {
        path: 'investigate/spine-browser',
        label: 'Spine browser',
        icon: <ManageSearchIcon />,
      },
      { path: 'investigate/hypotheses', label: 'Hypotheses', icon: <ScienceIcon /> },
    ],
  },
  {
    id: 'arcs',
    label: 'Arcs',
    items: [
      { path: 'arcs', label: 'Arc catalog', icon: <TimelineIcon />, exact: true },
      { path: 'arcs/rolling', label: 'Rolling 12m', icon: <TimelineIcon /> },
    ],
  },
  {
    id: 'outputs',
    label: 'Outputs',
    items: [
      { path: 'briefings', label: 'Briefings', icon: <ArticleIcon /> },
      { path: 'arcs/reports', label: 'Arc reports', icon: <NewspaperIcon /> },
    ],
  },
  {
    id: 'finance',
    label: 'Finance',
    items: [
      {
        path: 'signals/review',
        label: 'Trade signals',
        icon: <ShowChartIcon />,
        hrefDomain: 'finance',
      },
      {
        path: 'analysis',
        label: 'Analysis',
        icon: <AnalyticsIcon />,
        domain: 'finance',
        demoHidden: true,
      },
      {
        path: 'commodity/gold',
        label: 'Commodity',
        icon: <ShowChartIcon />,
        domain: 'finance',
        demoHidden: true,
      },
      {
        path: 'credit-spread',
        label: 'Credit spread',
        icon: <ShowChartIcon />,
        hrefDomain: 'finance',
        demoHidden: true,
      },
{
  path: 'usd-purchasing-power-tracker',
  label: 'USD Purchasing Power Tracker',
  icon: <ShowChartIcon />,
  hrefDomain: 'finance',
  demoHidden: true,
},
      {
        path: 'trace',
        label: 'Task trace',
        icon: <TimelineIcon />,
        domain: 'finance',
        demoHidden: true,
      },
    ],
  },
  {
    id: 'politics',
    label: 'Politics',
    items: [
      {
        path: 'congress-trading',
        label: 'Congress Trading',
        icon: <HowToVoteIcon />,
        domain: 'politics',
        demoHidden: true,
      },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { path: 'monitor', label: 'Monitor', icon: <MonitorHeartIcon />, exact: true },
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
      {
        path: 'operations/investigation-ops',
        label: 'Investigation ops',
        icon: <PsychologyIcon />,
      },
      {
        path: 'operations/llm-activity',
        label: 'LLM activity',
        icon: <MemoryIcon />,
      },
    ],
  },
];

function isNavSelected(pathname: string, base: string, path: string, exact?: boolean): boolean {
  const fullPath = `${base}/${path}`;
  if (exact) {
    return pathname === fullPath;
  }
  if (pathname === fullPath) return true;
  if (path.includes('/')) {
    return pathname.startsWith(`${fullPath}/`) || pathname === fullPath;
  }
  if (pathname.startsWith(`${fullPath}/`)) {
    if (path === 'monitor' && pathname !== `${base}/monitor`) {
      return false;
    }
    if (path === 'arcs' && pathname.startsWith(`${base}/arcs/`)) {
      return pathname === `${base}/arcs`;
    }
    return true;
  }
  return false;
}

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
      if (item.domain && item.domain !== domain && !item.hrefDomain) return false;
      if (demoReadonly) {
        if (section.id === 'operations') return false;
        if (item.demoHidden) return false;
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
          {section.items.map(({ path, label, icon, exact, hrefDomain }) => {
            const itemBase = hrefDomain ? `/${hrefDomain}` : base;
            const navSelected = isNavSelected(location.pathname, itemBase, path, exact);
            return (
              <ListItemButton
                key={path}
                selected={navSelected}
                onClick={() => {
                  navigate(`${itemBase}/${path}`);
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
