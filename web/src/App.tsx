/**
 * News Intelligence System v3.3.0 - Main Application
 * Clean, organized frontend with role-based navigation
 */

import React, { useState, useEffect } from 'react';
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
  Snackbar,
  Divider,
  Switch,
  FormControlLabel,
  Collapse,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Refresh as RefreshIcon,
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  AdminPanelSettings as AdminIcon,
} from '@mui/icons-material';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Link,
} from 'react-router-dom';

// Import pages - Core functionality
import ArticleDetail from './pages/Articles/ArticleDetail';
import Articles from './pages/Articles/EnhancedArticles';
import Dashboard from './pages/Dashboard/EnhancedDashboard';
import IntelligenceHub from './pages/Intelligence/IntelligenceHub';
import RSSFeeds from './pages/RSSFeeds/EnhancedRSSFeeds';
import Settings from './pages/Settings/Settings';
import Storylines from './pages/Storylines/Storylines';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import SimpleStorylineReport from './pages/Storylines/SimpleStorylineReport';
import StorylineTimeline from './pages/Timeline/StorylineTimeline';

// Import pages - Advanced features (admin only)
import Phase2Dashboard from './pages/Dashboard/Phase2Dashboard';
import Health from './pages/Health/Health';
import Monitoring from './pages/Monitoring/EnhancedMonitoring';
import RealtimeMonitor from './components/Monitoring/RealtimeMonitor';
import SystemAnalytics from './components/Analytics/SystemAnalytics';

// Import services and utilities
import { apiService } from './services/apiService';
import Logger from './utils/logger';
import { getNavigationForUser, navigationCategories } from './config/navigation';

// Theme configuration
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
      paper: '#ffffff',
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

const drawerWidth = 280;

const App: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedExpanded, setAdvancedExpanded] = useState(false);
  const [userRole, setUserRole] = useState<string>('user'); // Default to basic user

  useEffect(() => {
    loadSystemData();
    // Set up periodic refresh
    const interval = setInterval(loadSystemData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadSystemData = async() => {
    try {
      setLoading(true);
      const healthResponse = await apiService.getHealth();
      setSystemHealth(healthResponse);
      setError(null);
    } catch (err) {
      Logger.error('Error loading system data:', err as Error);
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

  const handleAdvancedToggle = () => {
    setShowAdvanced(!showAdvanced);
    if (!showAdvanced) {
      setAdvancedExpanded(true);
    }
  };

  const handleAdvancedExpand = () => {
    setAdvancedExpanded(!advancedExpanded);
  };

  // Get navigation items based on user role
  const navigation = getNavigationForUser(userRole);
  const mainItems = navigation.main;
  const advancedItems = navigation.advanced;

  const drawer = (
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          News Intelligence
        </Typography>
      </Toolbar>

      {/* Main Navigation */}
      <List>
        <ListItem>
          <ListItemText
            primary={navigationCategories.main.title}
            primaryTypographyProps={{
              variant: 'caption',
              color: 'text.secondary',
              sx: { fontWeight: 'bold', textTransform: 'uppercase' },
            }}
          />
        </ListItem>
        {mainItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton component={Link} to={item.path}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}

        {/* Advanced Features Toggle */}
        {advancedItems.length > 0 && (
          <>
            <Divider sx={{ my: 1 }} />
            <ListItem>
              <FormControlLabel
                control={
                  <Switch
                    checked={showAdvanced}
                    onChange={handleAdvancedToggle}
                    size="small"
                  />
                }
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <AdminIcon fontSize="small" />
                    <Typography variant="body2" fontWeight="bold">
                      Advanced Features
                    </Typography>
                  </Box>
                }
              />
            </ListItem>

            {/* Advanced Features */}
            {showAdvanced && (
              <>
                <ListItem>
                  <ListItemButton onClick={handleAdvancedExpand}>
                    <ListItemIcon>
                      {advancedExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </ListItemIcon>
                    <ListItemText
                      primary={navigationCategories.admin.title}
                      primaryTypographyProps={{
                        variant: 'caption',
                        color: 'text.secondary',
                        sx: { fontWeight: 'bold', textTransform: 'uppercase' },
                      }}
                    />
                  </ListItemButton>
                </ListItem>
                <Collapse in={advancedExpanded} timeout="auto" unmountOnExit>
                  <List component="div" disablePadding>
                    {advancedItems.map((item) => (
                      <ListItem key={item.text} disablePadding sx={{ pl: 4 }}>
                        <ListItemButton component={Link} to={item.path}>
                          <ListItemIcon>{item.icon}</ListItemIcon>
                          <ListItemText
                            primary={item.text}
                            secondary={item.description}
                            secondaryTypographyProps={{ variant: 'caption' }}
                          />
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                </Collapse>
              </>
            )}
          </>
        )}
      </List>
    </Box>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex' }}>
        <Router>
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
                News Intelligence System v3.3.0
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
              {/* Main Routes */}
              <Route path="/" element={<Dashboard />} />
              <Route path="/articles" element={<Articles />} />
              <Route path="/articles/:id" element={<ArticleDetail />} />
              <Route path="/rss-feeds" element={<RSSFeeds />} />
              <Route path="/storylines" element={<Storylines />} />
              <Route path="/storylines/:id" element={<StorylineDetail />} />
              <Route path="/storylines/:id/report" element={<SimpleStorylineReport />} />
              <Route path="/storylines/:id/timeline" element={<StorylineTimeline />} />
              <Route path="/intelligence" element={<IntelligenceHub />} />
              <Route path="/settings" element={<Settings />} />

              {/* Advanced Routes (Admin Only) */}
              <Route path="/phase2-dashboard" element={<Phase2Dashboard />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/realtime-monitor" element={<RealtimeMonitor />} />
              <Route path="/analytics" element={<SystemAnalytics />} />
              <Route path="/health" element={<Health systemHealth={systemHealth} />} />

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Box>
        </Router>

        <Snackbar
          open={snackbarOpen}
          autoHideDuration={6000}
          onClose={handleCloseSnackbar}
          message={snackbarMessage}
          action={
            <IconButton
              size="small"
              aria-label="close"
              color="inherit"
              onClick={handleCloseSnackbar}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          }
        />
      </Box>
    </ThemeProvider>
  );
};

export default App;
