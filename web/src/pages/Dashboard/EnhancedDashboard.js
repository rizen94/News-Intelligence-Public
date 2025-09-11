import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  Chip,
  LinearProgress,
  Button,
  IconButton,
  Tooltip,
  Alert,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Article as ArticleIcon,
  RssFeed as RssFeedIcon,
  Timeline as TimelineIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Schedule as ScheduleIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  Analytics as AnalyticsIcon,
  AutoAwesome as AutoAwesomeIcon
} from '@mui/icons-material';
import { apiService } from '../../services/apiService';

const EnhancedDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    loadSystemData();
    const interval = setInterval(loadSystemData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadSystemData = async () => {
    try {
      setLoading(true);
      setError(null);
      const status = await apiService.getSystemStatus();
      setSystemStatus(status);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error loading system data:', err);
      setError('Failed to load system data');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    loadSystemData();
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon />;
      case 'degraded': return <WarningIcon />;
      case 'error': return <WarningIcon />;
      default: return <WarningIcon />;
    }
  };

  if (loading && !systemStatus) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          News Intelligence Dashboard
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="body2" color="text.secondary">
            Last updated: {lastUpdate ? lastUpdate.toLocaleTimeString() : 'Never'}
          </Typography>
          <Tooltip title="Refresh Data">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      <Grid container spacing={3}>
        {/* System Health Overview */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <DashboardIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">System Health</Typography>
              </Box>
              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <Box textAlign="center">
                    <Chip
                      icon={getStatusIcon(systemStatus?.overall)}
                      label={systemStatus?.overall?.toUpperCase() || 'UNKNOWN'}
                      color={getStatusColor(systemStatus?.overall)}
                      size="large"
                    />
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      Overall Status
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">
                      {systemStatus?.health?.data?.services?.database === 'healthy' ? '✓' : '✗'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Database
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">
                      {systemStatus?.health?.data?.services?.redis === 'healthy' ? '✓' : '✗'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Redis Cache
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">
                      {systemStatus?.health?.data?.services?.system === 'healthy' ? '✓' : '✗'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      System
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Core Metrics */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <ArticleIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Articles</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {systemStatus?.articleStats?.data?.total_articles || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Articles
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Today: {systemStatus?.articleStats?.data?.articles_today || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                This Week: {systemStatus?.articleStats?.data?.articles_this_week || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <RssFeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">RSS Feeds</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {systemStatus?.rssStats?.data?.active_feeds || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Feeds
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Total: {systemStatus?.rssStats?.data?.total_feeds || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Errors: {systemStatus?.rssStats?.data?.feeds_with_errors || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <TimelineIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Storylines</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {systemStatus?.storylineStats?.data?.active_storylines || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Storylines
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Total: {systemStatus?.storylineStats?.data?.total_storylines || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                New Today: 0
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <SpeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Pipeline</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {systemStatus?.pipelineStatus?.data?.status || 'idle'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Processing Status
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Success Rate: {systemStatus?.pipelineStatus?.data?.success_rate || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Traces: {systemStatus?.pipelineStatus?.data?.total_traces || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* AI & Analysis Features */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                AI Analysis Features
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <AutoAwesomeIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="h6">Multi-Perspective Analysis</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Analyze news from multiple viewpoints
                    </Typography>
                    <Chip label="Available" color="success" size="small" sx={{ mt: 1 }} />
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <AnalyticsIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="h6">Impact Assessment</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Evaluate potential impacts across dimensions
                    </Typography>
                    <Chip label="Available" color="success" size="small" sx={{ mt: 1 }} />
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <ScheduleIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="h6">Predictive Analysis</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Forecast future developments
                    </Typography>
                    <Chip label="Available" color="success" size="small" sx={{ mt: 1 }} />
                  </Paper>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                <Button variant="contained" startIcon={<ArticleIcon />}>
                  View Articles
                </Button>
                <Button variant="outlined" startIcon={<RssFeedIcon />}>
                  Manage RSS Feeds
                </Button>
                <Button variant="outlined" startIcon={<TimelineIcon />}>
                  Create Storyline
                </Button>
                <Button variant="outlined" startIcon={<AnalyticsIcon />}>
                  Run Analysis
                </Button>
                <Button variant="outlined" startIcon={<RefreshIcon />}>
                  Refresh Data
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* System Information */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Information
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <NetworkIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="API Endpoint"
                        secondary={process.env.REACT_APP_API_URL || 'http://localhost:8001'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <MemoryIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Version"
                        secondary="News Intelligence System v3.0"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <StorageIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Database"
                        secondary="PostgreSQL with Redis Cache"
                      />
                    </ListItem>
                  </List>
                </Grid>
                <Grid item xs={12} md={6}>
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Status"
                        secondary={systemStatus?.overall || 'Unknown'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <ScheduleIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Last Update"
                        secondary={lastUpdate ? lastUpdate.toLocaleString() : 'Never'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <PsychologyIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="AI Features"
                        secondary="Multi-perspective, Impact Assessment, Predictive Analysis"
                      />
                    </ListItem>
                  </List>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default EnhancedDashboard;