import React from 'react';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Badge,
  Chip,
  Avatar,
  Tooltip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Article as ArticleIcon,
  GroupWork as ClusterIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
  RssFeed as SourceIcon,
  Search as SearchIcon,
  Settings as SettingsIcon,
  Monitor as MonitorIcon,
  Notifications as NotificationsIcon,
  TrendingUp as PrioritizationIcon,
  Timeline as TimelineIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  SmartToy as LivingNarratorIcon,
  Visibility as ArticleViewerIcon,
  Insights as InsightsIcon,
  Analytics as AnalyticsIcon,
  Security as SecurityIcon,
  ContentCopy as DeduplicationIcon,
  Speed as MLProcessingIcon,
  Assessment as AssessmentIcon,
  AutoStories as BriefingsIcon,
  SettingsApplications as AutomationIcon,
  Storage as DataManagementIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import NotificationBell from '../StorylineAlerts/NotificationBell';
import { useNewsSystem } from '../../contexts/NewsSystemContext';
import MLProcessingStatus from '../MLProcessingStatus/MLProcessingStatus';
import SystemStatusIndicator from '../SystemStatus/SystemStatusIndicator';

const drawerWidth = 280;

const menuItems = [
  // Core Features
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard', category: 'core' },
  { text: 'Intelligence', icon: <InsightsIcon />, path: '/intelligence', category: 'core' },
  { text: 'Articles & Analysis', icon: <ArticleIcon />, path: '/articles', category: 'core' },
  { text: 'Story Dossiers', icon: <TimelineIcon />, path: '/story-dossiers', category: 'core' },
  
  // AI & ML Features
  { text: 'ML Processing', icon: <MLProcessingIcon />, path: '/ml-processing', category: 'ai' },
  { text: 'Living Story Narrator', icon: <LivingNarratorIcon />, path: '/living-narrator', category: 'ai' },
  { text: 'Enhanced Article Viewer', icon: <ArticleViewerIcon />, path: '/article-viewer', category: 'ai' },
  
  // Data Management (Phase 2)
  { text: 'Deduplication', icon: <DeduplicationIcon />, path: '/deduplication', category: 'data', phase: 1 },
  { text: 'RSS Management', icon: <SourceIcon />, path: '/rss-management', category: 'data', phase: 1 },
  { text: 'Content Prioritization', icon: <PrioritizationIcon />, path: '/prioritization', category: 'data', phase: 1 },
  
  // Automation & Briefings (Phase 2)
  { text: 'Daily Briefings', icon: <BriefingsIcon />, path: '/briefings', category: 'automation', phase: 1 },
  { text: 'Automation Pipeline', icon: <AutomationIcon />, path: '/automation', category: 'automation', phase: 1 },
  
  // Advanced Features (Phase 3)
  { text: 'Advanced Monitoring', icon: <AssessmentIcon />, path: '/monitoring', category: 'advanced', phase: 1 },
  { text: 'Data Management', icon: <DataManagementIcon />, path: '/data-management', category: 'advanced', phase: 1 },
];

const entityTypeItems = [
  { text: 'People', icon: <PersonIcon />, path: '/entities?type=PERSON' },
  { text: 'Organizations', icon: <BusinessIcon />, path: '/entities?type=ORG' },
  { text: 'Locations', icon: <LocationIcon />, path: '/entities?type=GPE' },
];

export default function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, actions } = useNewsSystem();
  const { ui, systemStatus, monitoring } = state;

  const handleDrawerToggle = () => {
    actions.toggleSidebar();
  };

  const handleNavigation = (path) => {
    navigate(path);
  };



  const getNotificationCount = () => {
    return monitoring.alerts.filter(alert => alert.level === 'critical').length;
  };

  const getSystemStatusColor = () => {
    if (systemStatus.status === 'healthy') return 'success';
    if (systemStatus.status === 'warning') return 'warning';
    return 'error';
  };

  const drawer = (
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          News Intelligence
        </Typography>
      </Toolbar>
      <Divider />
      
      {/* System Status */}
      <Box sx={{ p: 2 }}>
        <Chip
          label={`System: ${systemStatus.status}`}
          color={getSystemStatusColor()}
          size="small"
          sx={{ mb: 1 }}
        />
        <Typography variant="caption" display="block" color="text.secondary">
          Version: {systemStatus.version}
        </Typography>
        <Typography variant="caption" display="block" color="text.secondary">
          Uptime: {systemStatus.uptime}
        </Typography>
      </Box>
      
      <Divider />
      
      {/* Main Navigation */}
      <List>
        {/* Core Features */}
        <ListItem>
          <Typography variant="subtitle2" color="text.secondary" sx={{ px: 2, py: 1, fontWeight: 'bold' }}>
            Core Features
          </Typography>
        </ListItem>
        {menuItems.filter(item => item.category === 'core').map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'primary.light',
                  '&:hover': {
                    backgroundColor: 'primary.light',
                  },
                },
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
        
        <Divider sx={{ my: 1 }} />
        
        {/* AI & ML Features */}
        <ListItem>
          <Typography variant="subtitle2" color="text.secondary" sx={{ px: 2, py: 1, fontWeight: 'bold' }}>
            AI & ML Features
          </Typography>
        </ListItem>
        {menuItems.filter(item => item.category === 'ai').map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'primary.light',
                  '&:hover': {
                    backgroundColor: 'primary.light',
                  },
                },
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
        
        <Divider sx={{ my: 1 }} />
        
        {/* Data Management */}
        <ListItem>
          <Typography variant="subtitle2" color="text.secondary" sx={{ px: 2, py: 1, fontWeight: 'bold' }}>
            Data Management
          </Typography>
        </ListItem>
        {menuItems.filter(item => item.category === 'data').map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
              disabled={item.phase > 1}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'primary.light',
                  '&:hover': {
                    backgroundColor: 'primary.light',
                  },
                },
                opacity: item.phase > 1 ? 0.5 : 1,
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
              {item.phase > 1 && (
                <Chip label="Coming Soon" size="small" color="info" variant="outlined" />
              )}
            </ListItemButton>
          </ListItem>
        ))}
        
        <Divider sx={{ my: 1 }} />
        
        {/* Automation (Phase 2) */}
        <ListItem>
          <Typography variant="subtitle2" color="text.secondary" sx={{ px: 2, py: 1, fontWeight: 'bold' }}>
            Automation <Chip label="Phase 2" size="small" color="info" variant="outlined" />
          </Typography>
        </ListItem>
        {menuItems.filter(item => item.category === 'automation').map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
              disabled={item.phase > 1}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'primary.light',
                  '&:hover': {
                    backgroundColor: 'primary.light',
                  },
                },
                opacity: item.phase > 1 ? 0.5 : 1,
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
              {item.phase > 1 && (
                <Chip label="Coming Soon" size="small" color="info" variant="outlined" />
              )}
            </ListItemButton>
          </ListItem>
        ))}
        
        <Divider sx={{ my: 1 }} />
        
        {/* Advanced Features (Phase 3) */}
        <ListItem>
          <Typography variant="subtitle2" color="text.secondary" sx={{ px: 2, py: 1, fontWeight: 'bold' }}>
            Advanced Features <Chip label="Phase 3" size="small" color="warning" variant="outlined" />
          </Typography>
        </ListItem>
        {menuItems.filter(item => item.category === 'advanced').map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
              disabled={item.phase > 1}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'primary.light',
                  '&:hover': {
                    backgroundColor: 'primary.light',
                  },
                },
                opacity: item.phase > 1 ? 0.5 : 1,
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? 'primary.main' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
              {item.phase > 1 && (
                <Chip label="Future" size="small" color="warning" variant="outlined" />
              )}
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      
      <Divider />
      
      {/* Quick Actions */}
      <Box sx={{ p: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Quick Actions
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Chip
            label="Run Pipeline"
            size="small"
            onClick={() => actions.runPipeline()}
            color="primary"
            variant="outlined"
          />
          <Chip
            label="Refresh Data"
            size="small"
            onClick={() => window.location.reload()}
            variant="outlined"
          />
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            News Intelligence System v2.9.0
          </Typography>
          
          {/* System Status Indicator */}
          <SystemStatusIndicator compact />
          
          {/* Storyline Alerts */}
          <NotificationBell />
          
          {/* User Avatar */}
          <Tooltip title="System User">
            <Avatar sx={{ ml: 1, width: 32, height: 32, bgcolor: 'secondary.main' }}>
              AI
            </Avatar>
          </Tooltip>
        </Toolbar>
      </AppBar>
      
      {/* Sidebar */}
      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={ui.sidebarOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        
        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
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
          p: { xs: 1, sm: 2, md: 3, lg: 4 },
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          mt: '64px', // AppBar height
          maxWidth: '100%',
          overflow: 'auto',
          height: 'calc(100vh - 64px)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* ML Processing Status - Always visible */}
        <MLProcessingStatus />
        {children}
      </Box>
    </Box>
  );
}
