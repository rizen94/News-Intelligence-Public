import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Alert,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
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
} from '@mui/icons-material';

const ConsolidatedDashboard = () => {
  const [dashboardData, setDashboardData] = useState({
    articles: { total: 0, processed: 0, pending: 0 },
    stories: { total: 0, active: 0, alerts: 0 },
    system: { uptime: '0h 0m', status: 'healthy', version: '2.8.0' },
    ml: { processing: false, queue: 0, completed: 0 },
    performance: { cpu: 0, memory: 0, disk: 0 },
    masterArticles: { total: 0, consolidated: 0, singleSource: 0 },
    preprocessing: { tagsExtracted: 0, lastRun: null }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch articles data
      const articlesResponse = await fetch('/api/articles');
      const articlesData = await articlesResponse.json();
      
      // Fetch story threads data
      const storiesResponse = await fetch('/api/prioritization/story-threads?status=active');
      const storiesData = await storiesResponse.json();
      
      // Fetch system metrics
      const metricsResponse = await fetch('/api/monitoring/metrics');
      const metricsData = await metricsResponse.json();
      
      // Fetch ML processing status
      const mlResponse = await fetch('/api/ml/status');
      const mlData = await mlResponse.json();
      
      // Fetch automated pipeline status
      const pipelineResponse = await fetch('/api/automation/pipeline/status');
      const pipelineData = await pipelineResponse.json();
      
      // Fetch storyline alerts
      const alertsResponse = await fetch('/api/alerts/storyline/unread');
      const alertsData = await alertsResponse.json();
      
      // Fetch master articles data
      const masterArticlesResponse = await fetch('/api/master-articles');
      const masterArticlesData = await masterArticlesResponse.json();
      
      // Fetch preprocessing status
      const preprocessingResponse = await fetch('/api/automation/preprocessing/status');
      const preprocessingData = await preprocessingResponse.json();

      setDashboardData({
        articles: {
          total: articlesData.data?.length || 0,
          processed: articlesData.data?.filter(a => a.processed).length || 0,
          pending: articlesData.data?.filter(a => !a.processed).length || 0
        },
        stories: {
          total: storiesData.data?.length || 0,
          active: storiesData.data?.length || 0,
          alerts: alertsData.data?.length || 0
        },
        system: {
          uptime: metricsData.uptime || '0h 0m',
          status: metricsData.status || 'healthy',
          version: '2.8.0'
        },
        ml: {
          processing: mlData.processing || false,
          queue: mlData.queue || 0,
          completed: mlData.completed || 0
        },
        pipeline: {
          running: pipelineData.data?.pipeline?.running || false,
          last_run: pipelineData.data?.pipeline?.last_run || null,
          pipeline_runs: pipelineData.data?.pipeline?.pipeline_runs || 0,
          articles_collected: pipelineData.data?.pipeline?.statistics?.articles_collected || 0,
          articles_processed: pipelineData.data?.pipeline?.statistics?.articles_processed || 0,
          story_threads_created: pipelineData.data?.pipeline?.statistics?.story_threads_created || 0
        },
        performance: {
          cpu: metricsData.cpu_percent || 0,
          memory: metricsData.memory_percent || 0,
          disk: metricsData.disk_percent || 0
        },
        masterArticles: {
          total: masterArticlesData.total || 0,
          consolidated: preprocessingData.data?.consolidated_articles || 0,
          singleSource: preprocessingData.data?.single_source_articles || 0
        },
        preprocessing: {
          tagsExtracted: preprocessingData.data?.processing_statistics?.tags_extracted || 0,
          lastRun: preprocessingData.data?.last_run || null
        }
      });

      // Set recent activity (last 5 articles)
      setRecentActivity(articlesData.data?.slice(0, 5) || []);
      
    } catch (err) {
      setError('Failed to fetch dashboard data');
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'warning': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon />;
      case 'warning': return <WarningIcon />;
      case 'error': return <ErrorIcon />;
      default: return <CheckCircleIcon />;
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          News Intelligence Dashboard
        </Typography>
        <Tooltip title="Refresh Data">
          <IconButton onClick={fetchDashboardData} color="primary">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Key Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Articles */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <ArticleIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Articles</Typography>
              </Box>
              <Typography variant="h3" color="primary">
                {dashboardData.articles.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {dashboardData.articles.processed} processed, {dashboardData.articles.pending} pending
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={(dashboardData.articles.processed / dashboardData.articles.total) * 100} 
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Story Threads */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TimelineIcon color="secondary" sx={{ mr: 1 }} />
                <Typography variant="h6">Story Threads</Typography>
              </Box>
              <Typography variant="h3" color="secondary">
                {dashboardData.stories.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {dashboardData.stories.alerts} new alerts
              </Typography>
              {dashboardData.stories.alerts > 0 && (
                <Chip 
                  label={`${dashboardData.stories.alerts} alerts`} 
                  color="warning" 
                  size="small" 
                  sx={{ mt: 1 }}
                />
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* System Status */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                {getStatusIcon(dashboardData.system.status)}
                <Typography variant="h6" sx={{ ml: 1 }}>System</Typography>
              </Box>
              <Chip 
                label={dashboardData.system.status} 
                color={getStatusColor(dashboardData.system.status)} 
                sx={{ mb: 1 }}
              />
              <Typography variant="body2" color="text.secondary">
                Uptime: {dashboardData.system.uptime}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Version: {dashboardData.system.version}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* ML Processing */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <PsychologyIcon color="info" sx={{ mr: 1 }} />
                <Typography variant="h6">ML Processing</Typography>
              </Box>
              <Typography variant="h3" color="info">
                {dashboardData.ml.processing ? 'Active' : 'Idle'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Queue: {dashboardData.ml.queue} | Completed: {dashboardData.ml.completed}
              </Typography>
              {dashboardData.ml.processing && (
                <LinearProgress sx={{ mt: 1 }} />
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Master Articles */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <ArticleIcon color="success" sx={{ mr: 1 }} />
                <Typography variant="h6">Master Articles</Typography>
              </Box>
              <Typography variant="h3" color="success.main">
                {dashboardData.masterArticles.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Consolidated: {dashboardData.masterArticles.consolidated}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Single Source: {dashboardData.masterArticles.singleSource}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Pipeline Status */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SpeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Automated Pipeline</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Chip 
                  label={dashboardData.pipeline.running ? 'Running' : 'Stopped'} 
                  color={dashboardData.pipeline.running ? 'success' : 'default'} 
                  sx={{ mr: 2 }}
                />
                <Typography variant="body2" color="text.secondary">
                  Runs: {dashboardData.pipeline.pipeline_runs}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Articles Collected: {dashboardData.pipeline.articles_collected}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Articles Processed: {dashboardData.pipeline.articles_processed}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Story Threads Created: {dashboardData.pipeline.story_threads_created}
              </Typography>
              {dashboardData.pipeline.last_run && (
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                  Last Run: {new Date(dashboardData.pipeline.last_run).toLocaleString()}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Performance Metrics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <MemoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                CPU Usage
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={dashboardData.performance.cpu} 
                color={dashboardData.performance.cpu > 80 ? 'error' : 'primary'}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {dashboardData.performance.cpu.toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <MemoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Memory Usage
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={dashboardData.performance.memory} 
                color={dashboardData.performance.memory > 80 ? 'error' : 'primary'}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {dashboardData.performance.memory.toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <SpeedIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Disk Usage
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={dashboardData.performance.disk} 
                color={dashboardData.performance.disk > 80 ? 'error' : 'primary'}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {dashboardData.performance.disk.toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Activity */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Articles
              </Typography>
              <List>
                {recentActivity.map((article, index) => (
                  <React.Fragment key={article.id || index}>
                    <ListItem>
                      <ListItemIcon>
                        <ArticleIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary={article.title || 'Untitled Article'}
                        secondary={`${article.source || 'Unknown'} • ${new Date(article.published_at || Date.now()).toLocaleDateString()}`}
                      />
                    </ListItem>
                    {index < recentActivity.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
                {recentActivity.length === 0 && (
                  <ListItem>
                    <ListItemText primary="No recent articles" />
                  </ListItem>
                )}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Alerts
              </Typography>
              <List>
                {dashboardData.stories.alerts > 0 ? (
                  <ListItem>
                    <ListItemIcon>
                      <NotificationsIcon color="warning" />
                    </ListItemIcon>
                    <ListItemText
                      primary={`${dashboardData.stories.alerts} storyline alerts`}
                      secondary="New updates to tracked stories"
                    />
                  </ListItem>
                ) : (
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" />
                    </ListItemIcon>
                    <ListItemText primary="No alerts" secondary="All systems normal" />
                  </ListItem>
                )}
                {dashboardData.performance.cpu > 80 && (
                  <ListItem>
                    <ListItemIcon>
                      <WarningIcon color="warning" />
                    </ListItemIcon>
                    <ListItemText
                      primary="High CPU Usage"
                      secondary={`${dashboardData.performance.cpu.toFixed(1)}% utilization`}
                    />
                  </ListItem>
                )}
                {dashboardData.performance.memory > 80 && (
                  <ListItem>
                    <ListItemIcon>
                      <WarningIcon color="warning" />
                    </ListItemIcon>
                    <ListItemText
                      primary="High Memory Usage"
                      secondary={`${dashboardData.performance.memory.toFixed(1)}% utilization`}
                    />
                  </ListItem>
                )}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ConsolidatedDashboard;
