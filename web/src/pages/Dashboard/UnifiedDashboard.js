import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
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
  Paper
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

const UnifiedDashboard = () => {
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
      setError('Failed to fetch dashboard data: ' + err.message);
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
      <div className="unified-container">
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      </div>
    );
  }

  return (
    <div className="unified-container">
      {/* Header */}
      <div className="unified-section">
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
      </div>

      {/* Key Metrics Cards */}
      <div className="unified-section">
        <div className="unified-grid unified-grid-4">
          {/* Articles */}
          <div className="unified-stat-card unified-fade-in">
            <ArticleIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#1976d2' }}>
              {dashboardData.articles.total}
            </div>
            <div className="unified-stat-label">Articles</div>
            <div className="unified-stat-description">
              Processed: {dashboardData.articles.processed} | Pending: {dashboardData.articles.pending}
            </div>
          </div>

          {/* Story Threads */}
          <div className="unified-stat-card unified-fade-in">
            <TimelineIcon color="secondary" sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#9c27b0' }}>
              {dashboardData.stories.total}
            </div>
            <div className="unified-stat-label">Story Threads</div>
            <div className="unified-stat-description">
              Active: {dashboardData.stories.active} | Alerts: {dashboardData.stories.alerts}
            </div>
          </div>

          {/* System Status */}
          <div className="unified-stat-card unified-fade-in">
            {getStatusIcon(dashboardData.system.status)}
            <div className="unified-stat-number" style={{ color: getStatusColor(dashboardData.system.status) === 'success' ? '#2e7d32' : '#f57c00' }}>
              {dashboardData.system.status}
            </div>
            <div className="unified-stat-label">System Status</div>
            <div className="unified-stat-description">
              Uptime: {dashboardData.system.uptime} | v{dashboardData.system.version}
            </div>
          </div>

          {/* ML Processing */}
          <div className="unified-stat-card unified-fade-in">
            <PsychologyIcon color="info" sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#0288d1' }}>
              {dashboardData.ml.processing ? 'Active' : 'Idle'}
            </div>
            <div className="unified-stat-label">ML Processing</div>
            <div className="unified-stat-description">
              Queue: {dashboardData.ml.queue} | Completed: {dashboardData.ml.completed}
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Metrics */}
      <div className="unified-section">
        <div className="unified-grid unified-grid-3">
          {/* Master Articles */}
          <div className="unified-stat-card unified-fade-in">
            <ArticleIcon color="success" sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#2e7d32' }}>
              {dashboardData.masterArticles.total}
            </div>
            <div className="unified-stat-label">Master Articles</div>
            <div className="unified-stat-description">
              Consolidated: {dashboardData.masterArticles.consolidated} | Single: {dashboardData.masterArticles.singleSource}
            </div>
          </div>

          {/* Pipeline Status */}
          <div className="unified-stat-card unified-fade-in">
            <SpeedIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#1976d2' }}>
              {dashboardData.pipeline?.running ? 'Running' : 'Stopped'}
            </div>
            <div className="unified-stat-label">Automated Pipeline</div>
            <div className="unified-stat-description">
              Runs: {dashboardData.pipeline?.pipeline_runs || 0} | Collected: {dashboardData.pipeline?.articles_collected || 0}
            </div>
          </div>

          {/* Preprocessing */}
          <div className="unified-stat-card unified-fade-in">
            <MemoryIcon color="info" sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#0288d1' }}>
              {dashboardData.preprocessing.tagsExtracted}
            </div>
            <div className="unified-stat-label">Tags Extracted</div>
            <div className="unified-stat-description">
              Last Run: {dashboardData.preprocessing.lastRun ? new Date(dashboardData.preprocessing.lastRun).toLocaleDateString() : 'Never'}
            </div>
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="unified-section">
        <div className="unified-grid unified-grid-3">
          {/* CPU Usage */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <MemoryIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">CPU Usage</div>
            </div>
            <div className="unified-content-body">
              <div className="unified-progress unified-progress-lg">
                <div 
                  className="unified-progress-bar" 
                  style={{ width: `${dashboardData.performance.cpu}%` }}
                />
              </div>
              <div className="unified-stat-description">{dashboardData.performance.cpu}%</div>
            </div>
          </div>

          {/* Memory Usage */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <MemoryIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Memory Usage</div>
            </div>
            <div className="unified-content-body">
              <div className="unified-progress unified-progress-lg">
                <div 
                  className="unified-progress-bar" 
                  style={{ width: `${dashboardData.performance.memory}%` }}
                />
              </div>
              <div className="unified-stat-description">{dashboardData.performance.memory}%</div>
            </div>
          </div>

          {/* Disk Usage */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <SpeedIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Disk Usage</div>
            </div>
            <div className="unified-content-body">
              <div className="unified-progress unified-progress-lg">
                <div 
                  className="unified-progress-bar" 
                  style={{ width: `${dashboardData.performance.disk}%` }}
                />
              </div>
              <div className="unified-stat-description">{dashboardData.performance.disk}%</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity and Alerts */}
      <div className="unified-section">
        <div className="unified-grid unified-grid-2">
          {/* Recent Activity */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <ArticleIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Recent Articles</div>
            </div>
            <div className="unified-content-body">
              <List dense>
                {recentActivity.map((article, index) => (
                  <React.Fragment key={article.id || index}>
                    <ListItem>
                      <ListItemIcon>
                        <ArticleIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText
                        primary={article.title || 'Untitled Article'}
                        secondary={article.source || 'Unknown Source'}
                      />
                    </ListItem>
                    {index < recentActivity.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </div>
          </div>

          {/* System Alerts */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <NotificationsIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">System Alerts</div>
            </div>
            <div className="unified-content-body">
              <List dense>
                {dashboardData.stories.alerts > 0 ? (
                  <ListItem>
                    <ListItemIcon>
                      <NotificationsIcon color="warning" />
                    </ListItemIcon>
                    <ListItemText
                      primary={`${dashboardData.stories.alerts} Storyline Alerts`}
                      secondary="New developments in tracked stories"
                    />
                  </ListItem>
                ) : (
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" />
                    </ListItemIcon>
                    <ListItemText
                      primary="No Active Alerts"
                      secondary="All systems operating normally"
                    />
                  </ListItem>
                )}
                
                {dashboardData.ml.processing && (
                  <ListItem>
                    <ListItemIcon>
                      <PsychologyIcon color="info" />
                    </ListItemIcon>
                    <ListItemText
                      primary="ML Processing Active"
                      secondary={`${dashboardData.ml.queue} items in queue`}
                    />
                  </ListItem>
                )}
                
                {dashboardData.pipeline?.running && (
                  <ListItem>
                    <ListItemIcon>
                      <SpeedIcon color="primary" />
                    </ListItemIcon>
                    <ListItemText
                      primary="Automated Pipeline Running"
                      secondary="Continuous processing active"
                    />
                  </ListItem>
                )}
              </List>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UnifiedDashboard;
