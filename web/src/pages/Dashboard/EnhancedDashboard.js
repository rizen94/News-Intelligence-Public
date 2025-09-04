import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Button,
  Tabs,
  Tab,
  Badge
} from '@mui/material';
import {
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  Psychology as PsychologyIcon,
  Memory as MemoryIcon,
  Speed as SpeedIcon,
  TrendingUp as TrendingUpIcon,
  Notifications as NotificationsIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkCheckIcon,
  Assessment as AssessmentIcon,
  AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';
import { newsSystemService } from '../../services/newsSystemService';
import { useNotifications } from '../../components/Notifications/NotificationSystem';

const EnhancedDashboard = () => {
  const { showSuccess, showError, showLoading, showInfo } = useNotifications();
  const [dashboardStats, setDashboardStats] = useState(null);
  const [ingestionStats, setIngestionStats] = useState(null);
  const [mlStats, setMlStats] = useState(null);
  const [storyStats, setStoryStats] = useState(null);
  const [systemAlerts, setSystemAlerts] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [buttonLoading, setButtonLoading] = useState({});

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async (isManualRefresh = false) => {
    try {
      setRefreshing(true);
      setError(null);

      if (isManualRefresh) {
        showInfo('Refreshing dashboard data...', 'Dashboard Refresh');
      }

      // Fetch all dashboard data in parallel
      const [
        stats,
        ingestion,
        ml,
        stories,
        alerts,
        activity,
        metrics
      ] = await Promise.allSettled([
        newsSystemService.getDashboardStats(),
        newsSystemService.getIngestionStats('hour'),
        newsSystemService.getMLPipelineStats(),
        newsSystemService.getStoryEvolutionStats(),
        newsSystemService.getSystemAlerts(),
        newsSystemService.getRecentActivity(10),
        newsSystemService.getSystemMetrics()
      ]);

      // Set data if successful
      if (stats.status === 'fulfilled') setDashboardStats(stats.value);
      if (ingestion.status === 'fulfilled') setIngestionStats(ingestion.value);
      if (ml.status === 'fulfilled') setMlStats(ml.value);
      if (stories.status === 'fulfilled') setStoryStats(stories.value);
      if (alerts.status === 'fulfilled') setSystemAlerts(alerts.value);
      if (activity.status === 'fulfilled') setRecentActivity(activity.value.activities || []);
      if (metrics.status === 'fulfilled') setSystemMetrics(metrics.value);

      // Count successful vs failed requests
      const successful = [stats, ingestion, ml, stories, alerts, activity, metrics].filter(r => r.status === 'fulfilled').length;
      const total = 7;

      if (isManualRefresh) {
        if (successful === total) {
          showSuccess('Dashboard refreshed successfully!', 'Dashboard Updated');
        } else {
          showWarning(`Dashboard refreshed with ${successful}/${total} data sources`, 'Partial Update');
        }
      }

      setLoading(false);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError(err.message);
      setLoading(false);
      
      if (isManualRefresh) {
        showError(`Failed to refresh dashboard: ${err.message}`, 'Refresh Error');
      }
    } finally {
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    fetchDashboardData(true);
  };

  const handleRetry = async () => {
    setButtonLoading(prev => ({ ...prev, retry: true }));
    try {
      await fetchDashboardData(true);
    } finally {
      setButtonLoading(prev => ({ ...prev, retry: false }));
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const StatCard = ({ title, value, icon, color, subtitle, trend }) => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography color="textSecondary" gutterBottom variant="h6">
              {title}
            </Typography>
            <Typography variant="h4" component="h2" color={color}>
              {value}
            </Typography>
            {subtitle && (
              <Typography color="textSecondary" variant="body2">
                {subtitle}
              </Typography>
            )}
            {trend && (
              <Box display="flex" alignItems="center" mt={1}>
                <TrendingUpIcon fontSize="small" color="success" />
                <Typography variant="body2" color="success.main" ml={0.5}>
                  {trend}
                </Typography>
              </Box>
            )}
          </Box>
          <Box color={color}>
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  const StatusIndicator = ({ status, label }) => {
    const getStatusColor = (status) => {
      switch (status?.toLowerCase()) {
        case 'healthy':
        case 'active':
        case 'ready':
          return 'success';
        case 'warning':
        case 'degraded':
          return 'warning';
        case 'error':
        case 'unhealthy':
        case 'failed':
          return 'error';
        default:
          return 'default';
      }
    };

    const getStatusIcon = (status) => {
      switch (status?.toLowerCase()) {
        case 'healthy':
        case 'active':
        case 'ready':
          return <CheckCircleIcon />;
        case 'warning':
        case 'degraded':
          return <WarningIcon />;
        case 'error':
        case 'unhealthy':
        case 'failed':
          return <ErrorIcon />;
        default:
          return <MemoryIcon />;
      }
    };

    return (
      <Chip
        icon={getStatusIcon(status)}
        label={label || status}
        color={getStatusColor(status)}
        variant="outlined"
        size="small"
      />
    );
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" ml={2}>
          Loading dashboard...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button 
          color="inherit" 
          size="small" 
          onClick={handleRetry}
          disabled={buttonLoading.retry}
          startIcon={buttonLoading.retry ? <CircularProgress size={16} /> : null}
        >
          {buttonLoading.retry ? 'Retrying...' : 'Retry'}
        </Button>
      }>
        Error loading dashboard: {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          News Intelligence Dashboard
        </Typography>
        <Box>
          <Tooltip title={refreshing ? "Refreshing..." : "Refresh Dashboard"}>
            <IconButton onClick={handleRefresh} disabled={refreshing}>
              {refreshing ? <CircularProgress size={20} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
          {dashboardStats && (
            <Typography variant="body2" color="textSecondary" ml={2}>
              Last updated: {new Date(dashboardStats.last_update).toLocaleTimeString()}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Overview" />
          <Tab label="System Health" />
          <Tab label="ML Pipeline" />
          <Tab label="Stories" />
          <Tab label="Alerts" />
        </Tabs>
      </Box>

      {/* Overview Tab */}
      {activeTab === 0 && (
        <Box>
          {/* Key Metrics */}
          <Grid container spacing={3} mb={3}>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                title="Total Articles"
                value={dashboardStats?.total_articles || 0}
                icon={<ArticleIcon sx={{ fontSize: 40 }} />}
                color="primary"
                subtitle={`${dashboardStats?.articles_today || 0} today`}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                title="Active Stories"
                value={dashboardStats?.active_stories || 0}
                icon={<TimelineIcon sx={{ fontSize: 40 }} />}
                color="secondary"
                subtitle={`${dashboardStats?.articles_this_hour || 0} this hour`}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                title="ML Queue"
                value={dashboardStats?.ml_processing_queue || 0}
                icon={<PsychologyIcon sx={{ fontSize: 40 }} />}
                color="info"
                subtitle="Processing queue"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                title="System Uptime"
                value={`${dashboardStats?.system_uptime_hours || 0}h`}
                icon={<MemoryIcon sx={{ fontSize: 40 }} />}
                color="success"
                subtitle="Running time"
              />
            </Grid>
          </Grid>

          {/* System Status */}
          <Grid container spacing={3} mb={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="System Status" />
                <CardContent>
                  <Box display="flex" flexDirection="column" gap={2}>
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="body1">Database</Typography>
                      <StatusIndicator status="healthy" />
                    </Box>
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="body1">ML Pipeline</Typography>
                      <StatusIndicator status={mlStats?.models_status?.llama || 'unknown'} />
                    </Box>
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="body1">Monitoring</Typography>
                      <StatusIndicator status="healthy" />
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="System Resources" />
                <CardContent>
                  {systemMetrics && (
                    <Box display="flex" flexDirection="column" gap={2}>
                      <Box>
                        <Box display="flex" justifyContent="space-between" mb={1}>
                          <Typography variant="body2">CPU Usage</Typography>
                          <Typography variant="body2">{systemMetrics.cpu_percent}%</Typography>
                        </Box>
                        <LinearProgress 
                          variant="determinate" 
                          value={systemMetrics.cpu_percent} 
                          color={systemMetrics.cpu_percent > 80 ? 'error' : 'primary'}
                        />
                      </Box>
                      <Box>
                        <Box display="flex" justifyContent="space-between" mb={1}>
                          <Typography variant="body2">Memory Usage</Typography>
                          <Typography variant="body2">{systemMetrics.memory_percent}%</Typography>
                        </Box>
                        <LinearProgress 
                          variant="determinate" 
                          value={systemMetrics.memory_percent} 
                          color={systemMetrics.memory_percent > 80 ? 'error' : 'primary'}
                        />
                      </Box>
                      <Box>
                        <Box display="flex" justifyContent="space-between" mb={1}>
                          <Typography variant="body2">Disk Usage</Typography>
                          <Typography variant="body2">{systemMetrics.disk_percent}%</Typography>
                        </Box>
                        <LinearProgress 
                          variant="determinate" 
                          value={systemMetrics.disk_percent} 
                          color={systemMetrics.disk_percent > 80 ? 'error' : 'primary'}
                        />
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Recent Activity */}
          <Card>
            <CardHeader title="Recent Activity" />
            <CardContent>
              {recentActivity.length > 0 ? (
                <List>
                  {recentActivity.map((activity, index) => (
                    <React.Fragment key={index}>
                      <ListItem>
                        <ListItemIcon>
                          <ArticleIcon />
                        </ListItemIcon>
                        <ListItemText
                          primary={activity.title}
                          secondary={`${activity.source} • ${new Date(activity.timestamp).toLocaleString()}`}
                        />
                      </ListItem>
                      {index < recentActivity.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography color="textSecondary">
                  No recent activity
                </Typography>
              )}
            </CardContent>
          </Card>
        </Box>
      )}

      {/* System Health Tab */}
      {activeTab === 1 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Ingestion Statistics" />
                <CardContent>
                  {ingestionStats && (
                    <Box display="flex" flexDirection="column" gap={2}>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Articles ({ingestionStats.period})</Typography>
                        <Typography variant="h6">{ingestionStats.articles_count}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Active Sources</Typography>
                        <Typography variant="h6">{ingestionStats.sources_count}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Avg Processing Time</Typography>
                        <Typography variant="h6">{ingestionStats.avg_processing_time.toFixed(2)}s</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Success Rate</Typography>
                        <Typography variant="h6">{ingestionStats.success_rate.toFixed(1)}%</Typography>
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Database Connections" />
                <CardContent>
                  {systemMetrics && (
                    <Box display="flex" flexDirection="column" gap={2}>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Active Connections</Typography>
                        <Typography variant="h6">{systemMetrics.active_connections}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Articles Processed Today</Typography>
                        <Typography variant="h6">{systemMetrics.articles_processed_today}</Typography>
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* ML Pipeline Tab */}
      {activeTab === 2 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="ML Pipeline Status" />
                <CardContent>
                  {mlStats && (
                    <Box display="flex" flexDirection="column" gap={2}>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Queue Size</Typography>
                        <Typography variant="h6">{mlStats.queue_size}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Processing Rate</Typography>
                        <Typography variant="h6">{mlStats.processing_rate.toFixed(1)}/hour</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Avg Processing Time</Typography>
                        <Typography variant="h6">{mlStats.avg_processing_time.toFixed(2)}s</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Last Processed</Typography>
                        <Typography variant="body2">
                          {mlStats.last_processed ? new Date(mlStats.last_processed).toLocaleString() : 'Never'}
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Model Status" />
                <CardContent>
                  {mlStats?.models_status && (
                    <Box display="flex" flexDirection="column" gap={2}>
                      {Object.entries(mlStats.models_status).map(([model, status]) => (
                        <Box key={model} display="flex" justifyContent="space-between" alignItems="center">
                          <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                            {model}
                          </Typography>
                          <StatusIndicator status={status} />
                        </Box>
                      ))}
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Stories Tab */}
      {activeTab === 3 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Story Statistics" />
                <CardContent>
                  {storyStats && (
                    <Box display="flex" flexDirection="column" gap={2}>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Total Stories</Typography>
                        <Typography variant="h6">{storyStats.total_stories}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Active Stories</Typography>
                        <Typography variant="h6">{storyStats.active_stories}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">New Today</Typography>
                        <Typography variant="h6">{storyStats.stories_today}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body1">Avg Articles/Story</Typography>
                        <Typography variant="h6">{storyStats.avg_articles_per_story.toFixed(1)}</Typography>
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Top Categories" />
                <CardContent>
                  {storyStats?.top_categories && storyStats.top_categories.length > 0 ? (
                    <List>
                      {storyStats.top_categories.map((category, index) => (
                        <ListItem key={index}>
                          <ListItemText
                            primary={category.category}
                            secondary={`${category.count} stories`}
                          />
                        </ListItem>
                      ))}
                    </List>
                  ) : (
                    <Typography color="textSecondary">
                      No category data available
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Alerts Tab */}
      {activeTab === 4 && (
        <Box>
          <Card>
            <CardHeader 
              title="System Alerts" 
              action={
                systemAlerts && (
                  <Badge badgeContent={systemAlerts.critical_count + systemAlerts.warning_count} color="error">
                    <NotificationsIcon />
                  </Badge>
                )
              }
            />
            <CardContent>
              {systemAlerts && systemAlerts.alerts.length > 0 ? (
                <List>
                  {systemAlerts.alerts.map((alert, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        {alert.severity === 'critical' && <ErrorIcon color="error" />}
                        {alert.severity === 'warning' && <WarningIcon color="warning" />}
                        {alert.severity === 'info' && <CheckCircleIcon color="info" />}
                      </ListItemIcon>
                      <ListItemText
                        primary={alert.message}
                        secondary={`${alert.category} • ${new Date(alert.timestamp).toLocaleString()}`}
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography color="textSecondary">
                  No active alerts
                </Typography>
              )}
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
};

export default EnhancedDashboard;
