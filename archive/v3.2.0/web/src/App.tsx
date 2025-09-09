import React, { useState, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate
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
  useMediaQuery,
  useTheme,
  Badge,
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
  Analytics as AnalyticsIcon,
  Settings as SettingsIcon,
  HealthAndSafety as HealthIcon,
  Refresh as RefreshIcon,
  Close as CloseIcon
} from '@mui/icons-material';

// Import pages
import Dashboard from './pages/Dashboard/Dashboard';
import Articles from './pages/Articles/Articles';
import RSSFeeds from './pages/RSSFeeds/RSSFeeds';
import Storylines from './pages/Storylines/Storylines';
import AIAnalysis from './pages/AIAnalysis/AIAnalysis';
import Monitoring from './pages/Monitoring/Monitoring';
import Settings from './pages/Settings/Settings';
import Health from './pages/Health/Health';

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

interface AppState {
  loading: boolean;
  error: string | null;
  systemHealth: any;
  articleStats: any;
  rssStats: any;
}

function App() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [appState, setAppState] = useState<AppState>({
    loading: true,
    error: null,
    systemHealth: null,
    articleStats: null,
    rssStats: null
  });
  const [snackbar, setSnackbar] = useState({ open: false, message: '' });

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
    { text: 'Articles', icon: <ArticleIcon />, path: '/articles' },
    { text: 'RSS Feeds', icon: <RssFeedIcon />, path: '/rss-feeds' },
    { text: 'Storylines', icon: <TimelineIcon />, path: '/storylines' },
    { text: 'AI Analysis', icon: <AnalyticsIcon />, path: '/ai-analysis' },
    { text: 'Monitoring', icon: <HealthIcon />, path: '/monitoring' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ];

  useEffect(() => {
    loadSystemData();
  }, []);

  const loadSystemData = async () => {
    try {
      setAppState(prev => ({ ...prev, loading: true, error: null }));

      // Load dashboard data which contains all the information we need
      const dashboardResponse = await apiService.getDashboard();

      setAppState({
        loading: false,
        error: null,
        systemHealth: dashboardResponse.data.system_health,
        articleStats: dashboardResponse.data.article_stats,
        rssStats: dashboardResponse.data.rss_stats
      });
    } catch (error) {
      console.error('Error loading system data:', error);
      setAppState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load system data'
      }));
      setSnackbar({ open: true, message: 'Failed to load system data' });
    }
  };

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleRefresh = () => {
    loadSystemData();
  };

  const handleSnackbarClose = () => {
    setSnackbar({ open: false, message: '' });
  };

  const drawer = (
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          News Intelligence
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <IconButton onClick={handleRefresh} color="inherit">
          <RefreshIcon />
        </IconButton>
      </Toolbar>
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton component="a" href={item.path}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  );

  if (appState.loading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
          <LinearProgress />
          <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography variant="h6">Loading News Intelligence System...</Typography>
          </Box>
        </Box>
      </ThemeProvider>
    );
  }

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
                News Intelligence System v3.1.0
              </Typography>
              {appState.systemHealth && (
                <Chip
                  label={appState.systemHealth.status}
                  color={appState.systemHealth.status === 'healthy' ? 'success' : 'warning'}
                  size="small"
                  sx={{ mr: 2 }}
                />
              )}
              <IconButton color="inherit" onClick={handleRefresh}>
                <RefreshIcon />
              </IconButton>
            </Toolbar>
          </AppBar>

          <Box
            component="nav"
            sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
          >
            <Drawer
              variant="temporary"
              open={mobileOpen}
              onClose={handleDrawerToggle}
              ModalProps={{ keepMounted: true }}
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
              mt: 8
            }}
          >
            {appState.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {appState.error}
              </Alert>
            )}

            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard systemData={appState} />} />
              <Route path="/articles" element={<Articles />} />
              <Route path="/rss-feeds" element={<RSSFeeds />} />
              <Route path="/storylines" element={<Storylines />} />
              <Route path="/ai-analysis" element={<AIAnalysis />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/health" element={<Health />} />
            </Routes>
          </Box>
        </Box>

        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={handleSnackbarClose}
          message={snackbar.message}
          action={
            <IconButton size="small" color="inherit" onClick={handleSnackbarClose}>
              <CloseIcon fontSize="small" />
            </IconButton>
          }
        />
      </Router>
    </ThemeProvider>
  );
}

export default App;
