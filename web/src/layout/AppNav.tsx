/**
 * Sidebar navigation — Dashboard, Discover, Investigate, Monitor, Analyze.
 */
import React, { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Box, List, ListItemButton, ListItemIcon, ListItemText, Drawer } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ExploreIcon from '@mui/icons-material/Explore';
import SearchIcon from '@mui/icons-material/Search';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AutoStoriesIcon from '@mui/icons-material/AutoStories';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import NewspaperIcon from '@mui/icons-material/Newspaper';

export const APP_NAV_WIDTH = 220;

const NAV_ITEMS: { path: string; label: string; icon: React.ReactNode; domain?: string }[] = [
  { path: 'dashboard', label: 'Dashboard', icon: <DashboardIcon /> },
  { path: 'discover', label: 'Discover', icon: <ExploreIcon /> },
  { path: 'storylines', label: 'Storylines', icon: <AutoStoriesIcon /> },
  { path: 'briefings', label: 'Briefings', icon: <MenuBookIcon /> },
  { path: 'report', label: "Today's Report", icon: <NewspaperIcon /> },
  { path: 'investigate', label: 'Investigate', icon: <SearchIcon /> },
  { path: 'monitor', label: 'Monitor', icon: <MonitorHeartIcon /> },
  { path: 'analyze', label: 'Analyze', icon: <AnalyticsIcon /> },
  { path: 'commodity/gold', label: 'Commodity', icon: <ShowChartIcon />, domain: 'finance' },
];

export function AppNav() {
  const { domain } = useParams<{ domain: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const base = `/${domain ?? 'politics'}`;
  const currentPath = location.pathname.replace(new RegExp(`^/${domain ?? 'politics'}`), '') || '/';
  const activePath = currentPath.split('/')[1] || 'dashboard';

  const items = NAV_ITEMS.filter((item) => !item.domain || item.domain === domain);
  const navContent = (
    <Box sx={{ pt: 2, width: APP_NAV_WIDTH }}>
      <List dense>
        {items.map(({ path, label, icon }) => (
          <ListItemButton
            key={path}
            selected={activePath === path || activePath === path.split('/')[0] || location.pathname === `${base}/${path}`}
            onClick={() => {
              navigate(`${base}/${path}`);
              setMobileOpen(false);
            }}
          >
            <ListItemIcon sx={{ minWidth: 40 }}>{icon}</ListItemIcon>
            <ListItemText primary={label} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { width: APP_NAV_WIDTH, boxSizing: 'border-box' },
        }}
      >
        <Box sx={{ px: 1, py: 2, fontWeight: 600 }}>NewsIntel</Box>
        {navContent}
      </Drawer>
      <Drawer
        variant="permanent"
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
