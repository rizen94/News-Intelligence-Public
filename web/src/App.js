import React, { useState, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Link
} from 'react-router-dom';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Chip,
  LinearProgress,
  Alert,
  Snackbar
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Article as ArticleIcon,
  RssFeed as RssFeedIcon,
  Timeline as TimelineIcon,
  Settings as SettingsIcon,
  HealthAndSafety as HealthIcon,
  Refresh as RefreshIcon,
  Close as CloseIcon,
  Psychology as PsychologyIcon
} from '@mui/icons-material';

// Import pages
import Dashboard from './pages/Dashboard/EnhancedDashboard';
import Articles from './pages/Articles/EnhancedArticles';
import RSSFeeds from './pages/RSSFeeds/EnhancedRSSFeeds';
import Storylines from './pages/Storylines/EnhancedStorylines';
// import AIAnalysis from './pages/AIAnalysis/AIAnalysis';
import Monitoring from './pages/Monitoring/EnhancedMonitoring';
import Settings from './pages/Settings/Settings';
import Health from './pages/Health/Health';

// Import advanced pages from v2.9/v3.2
import IntelligenceHub from './pages/Intelligence/IntelligenceHub';
import ArticleDetail from './pages/Articles/ArticleDetail';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import StorylineTimeline from './pages/Timeline/StorylineTimeline';
// import SystemMonitoring from './pages/Monitoring/SystemMonitoring';

// Import API service
import { apiService } from './services/apiService';

const drawerWidth = 240;

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 500,
    },
  },
});

function App() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');


  useEffect(() => {
    loadSystemData();
    // Set up periodic refresh
    const interval = setInterval(loadSystemData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadSystemData = async () => {
    try {
      setLoading(true);
      const healthResponse = await apiService.getHealth();

      setSystemHealth(healthResponse);
      setError(null);
    } catch (err) {
      console.error('Error loading system data:', err);
      setError('Failed to load system data');
      setSnackbarMessage('Failed to load system data');
      setSnackbarOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleRefresh = () => {
    loadSystemData();
  };

  const handleCloseSnackbar = () => {
    setSnackbarOpen(false);
  };

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
    { text: 'Intelligence', icon: <PsychologyIcon />, path: '/intelligence' },
    { text: 'Articles', icon: <ArticleIcon />, path: '/articles' },
    { text: 'RSS Feeds', icon: <RssFeedIcon />, path: '/rss-feeds' },
    { text: 'Storylines', icon: <TimelineIcon />, path: '/storylines' },
    { text: 'Monitoring', icon: <HealthIcon />, path: '/monitoring' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ];

  const drawer = (
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          News Intelligence v3.0
        </Typography>
      </Toolbar>
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton component={Link} to={item.path}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Box sx={{ display: 'flex' }}>
          <AppBar
            position="fixed"
            sx={{
              width: { md: `calc(100% - ${drawerWidth}px)` },
              ml: { md: `${drawerWidth}px` },
            }}
          >
            <Toolbar>
              <IconButton
                color="inherit"
                aria-label="open drawer"
                edge="start"
                onClick={handleDrawerToggle}
                sx={{ mr: 2, display: { md: 'none' } }}
              >
                <MenuIcon />
              </IconButton>
              <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
                News Intelligence System
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                {systemHealth && (
                  <Chip
                    label={`Status: ${systemHealth.data?.status || 'unknown'}`}
                    color={systemHealth.data?.status === 'healthy' ? 'success' : 'error'}
                    size="small"
                  />
                )}
                <IconButton color="inherit" onClick={handleRefresh} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Box>
            </Toolbar>
            {loading && <LinearProgress />}
          </AppBar>

          <Box
            component="nav"
            sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
          >
            <Drawer
              variant="temporary"
              open={mobileOpen}
              onClose={handleDrawerToggle}
              ModalProps={{
                keepMounted: true,
              }}
              sx={{
                display: { xs: 'block', md: 'none' },
                '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
              }}
            >
              {drawer}
            </Drawer>
            <Drawer
              variant="permanent"
              sx={{
                display: { xs: 'none', md: 'block' },
                '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
              }}
              open
            >
              {drawer}
            </Drawer>
          </Box>

          <Box
            component="main"
            sx={{
              flexGrow: 1,
              p: 3,
              width: { md: `calc(100% - ${drawerWidth}px)` },
              mt: 8,
            }}
          >
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/intelligence" element={<IntelligenceHub />} />
              <Route path="/articles" element={<Articles />} />
              <Route path="/articles/:id" element={<ArticleDetail />} />
              <Route path="/rss-feeds" element={<RSSFeeds />} />
              <Route path="/storylines" element={<Storylines />} />
              <Route path="/storylines/:id" element={<StorylineDetail />} />
              <Route path="/storylines/:id/timeline" element={<StorylineTimeline />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/health" element={<Health systemHealth={systemHealth} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Box>
        </Box>

        <Snackbar
          open={snackbarOpen}
          autoHideDuration={6000}
          onClose={handleCloseSnackbar}
          message={snackbarMessage}
          action={
            <IconButton size="small" color="inherit" onClick={handleCloseSnackbar}>
              <CloseIcon fontSize="small" />
            </IconButton>
          }
        />
      </Router>
    </ThemeProvider>
  );
}

export default App;
