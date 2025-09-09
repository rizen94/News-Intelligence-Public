/**
 * Newspaper Layout v3.0 for News Intelligence System
 * Enhanced with AI features and modern design
 */

import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  IconButton,
  Badge,
  Divider,
  useTheme,
  useMediaQuery,
  Chip,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Home as HomeIcon,
  Timeline as TimelineIcon,
  Explore as ExploreIcon,
  Article as ArticleIcon,
  Schedule as ScheduleIcon,
  Notifications as NotificationsIcon,
  Settings as SettingsIcon,
  Close as CloseIcon,
  Psychology as PsychologyIcon,
  Analytics as AnalyticsIcon,
  Speed as SpeedIcon,
  TrendingUp as TrendingUpIcon,
  Group as GroupIcon,
  Assessment as AssessmentIcon,
  Memory as MemoryIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useNotifications } from '../Notifications/NotificationSystem';

const drawerWidth = 300;

interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  ai_processing: boolean;
  cache_performance: number;
  last_update: string;
}

const NewspaperLayoutV3: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    status: 'healthy',
    ai_processing: true,
    cache_performance: 0.85,
    last_update: new Date().toLocaleTimeString()
  });
  const [isLoading, setIsLoading] = useState(false);
  
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();
  const { addNotification } = useNotifications();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  // Enhanced navigation with AI features
  const navigationItems = [
    { 
      text: 'Morning Briefing', 
      icon: <HomeIcon />, 
      path: '/', 
      exact: true,
      description: 'AI-powered daily summary'
    },
    { 
      text: 'My Storylines', 
      icon: <TimelineIcon />, 
      path: '/storylines',
      description: 'Track story evolution'
    },
    { 
      text: 'Discover', 
      icon: <ExploreIcon />, 
      path: '/discover',
      description: 'Find trending topics'
    },
    { 
      text: 'Articles', 
      icon: <ArticleIcon />, 
      path: '/articles',
      description: 'Browse all articles'
    },
    { 
      text: 'AI Analysis', 
      icon: <PsychologyIcon />, 
      path: '/ai-analysis',
      description: 'Sentiment & entity analysis',
      badge: 'NEW'
    },
    { 
      text: 'Trends', 
      icon: <TrendingUpIcon />, 
      path: '/trends',
      description: 'Pattern detection & predictions'
    },
    { 
      text: 'Clusters', 
      icon: <GroupIcon />, 
      path: '/clusters',
      description: 'Topic clustering & grouping'
    },
    { 
      text: 'Monitoring', 
      icon: <SpeedIcon />, 
      path: '/monitoring',
      description: 'System performance & health'
    },
  ];

  const isActiveRoute = (path: string, exact: boolean = false) => {
    if (exact) {
      return location.pathname === path;
    }
    return location.pathname.startsWith(path);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'unhealthy': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return '🟢';
      case 'degraded': return '🟡';
      case 'unhealthy': return '🔴';
      default: return '⚪';
    }
  };

  // Simulate system status updates
  useEffect(() => {
    const interval = setInterval(() => {
      setSystemStatus(prev => ({
        ...prev,
        last_update: new Date().toLocaleTimeString(),
        cache_performance: Math.random() * 0.3 + 0.7 // Simulate 70-100% performance
      }));
    }, 30000); // Update every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Typography variant="h5" component="div" sx={{ fontWeight: 'bold', color: 'primary.main', flexGrow: 1 }}>
            News Intelligence
          </Typography>
          <Chip 
            label="v3.0" 
            size="small" 
            color="primary" 
            variant="outlined"
            sx={{ ml: 1 }}
          />
        </Box>
        <Typography variant="body2" color="text.secondary">
          AI-Powered News Analysis
        </Typography>
        
        {/* System Status */}
        <Box sx={{ mt: 2, p: 1.5, backgroundColor: 'grey.50', borderRadius: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="caption" color="text.secondary">
              System Status
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Typography variant="caption" sx={{ fontSize: '0.75rem' }}>
                {getStatusIcon(systemStatus.status)}
              </Typography>
              <Chip 
                label={systemStatus.status.toUpperCase()} 
                size="small" 
                color={getStatusColor(systemStatus.status)}
                variant="outlined"
                sx={{ fontSize: '0.7rem', height: 20 }}
              />
            </Box>
          </Box>
          
          <Box sx={{ mb: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Cache Performance
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {Math.round(systemStatus.cache_performance * 100)}%
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={systemStatus.cache_performance * 100}
              sx={{ height: 4, borderRadius: 2 }}
            />
          </Box>
          
          <Typography variant="caption" color="text.secondary">
            Last update: {systemStatus.last_update}
          </Typography>
        </Box>
      </Box>

      {/* Navigation */}
      <List sx={{ flexGrow: 1, pt: 1 }}>
        {navigationItems.map((item) => (
          <Tooltip key={item.text} title={item.description} placement="right">
            <ListItem
              button
              onClick={() => {
                navigate(item.path);
                if (isMobile) setMobileOpen(false);
              }}
              sx={{
                mx: 1,
                mb: 0.5,
                borderRadius: 1,
                backgroundColor: isActiveRoute(item.path, item.exact) ? 'primary.main' : 'transparent',
                color: isActiveRoute(item.path, item.exact) ? 'white' : 'text.primary',
                '&:hover': {
                  backgroundColor: isActiveRoute(item.path, item.exact) ? 'primary.dark' : 'action.hover',
                },
              }}
            >
              <ListItemIcon
                sx={{
                  color: isActiveRoute(item.path, item.exact) ? 'white' : 'text.secondary',
                  minWidth: 40,
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography
                      sx={{
                        fontWeight: isActiveRoute(item.path, item.exact) ? 600 : 400,
                        fontSize: '0.9rem'
                      }}
                    >
                      {item.text}
                    </Typography>
                    {item.badge && (
                      <Chip 
                        label={item.badge} 
                        size="small" 
                        color="error" 
                        sx={{ height: 16, fontSize: '0.6rem' }}
                      />
                    )}
                  </Box>
                }
                secondary={
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    {item.description}
                  </Typography>
                }
              />
            </ListItem>
          </Tooltip>
        ))}
      </List>

      <Divider />

      {/* Footer */}
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary" display="block">
          Powered by Local AI
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block">
          {systemStatus.ai_processing ? '🟢 AI Processing Active' : '🔴 AI Processing Offline'}
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
          backgroundColor: 'white',
          color: 'text.primary',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          borderBottom: '1px solid #e0e0e0',
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
          
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
            {navigationItems.find(item => isActiveRoute(item.path, item.exact))?.text || 'News Intelligence'}
          </Typography>

          {/* AI Processing Indicator */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mr: 2 }}>
            <Chip
              icon={<PsychologyIcon />}
              label="AI Active"
              size="small"
              color="success"
              variant="outlined"
            />
            {isLoading && (
              <LinearProgress 
                sx={{ width: 60, height: 4, borderRadius: 2 }} 
                color="primary" 
              />
            )}
          </Box>

          <IconButton color="inherit" sx={{ mr: 1 }}>
            <Badge badgeContent={3} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>

          <IconButton color="inherit">
            <SettingsIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Drawer */}
      <Box
        component="nav"
        sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true,
          }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
            },
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', p: 1 }}>
            <IconButton onClick={handleDrawerToggle}>
              <CloseIcon />
            </IconButton>
          </Box>
          {drawer}
        </Drawer>

        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
              borderRight: '1px solid #e0e0e0',
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          minHeight: '100vh',
          backgroundColor: '#fafafa',
        }}
      >
        <Toolbar />
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
};

export default NewspaperLayoutV3;
