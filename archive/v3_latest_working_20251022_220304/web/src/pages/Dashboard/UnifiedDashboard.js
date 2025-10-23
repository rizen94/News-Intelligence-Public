import {
  Article,
  Timeline as TimelineIcon,
  Psychology as PsychologyIcon,
  Memory as MemoryIcon,
  Speed as SpeedIcon,
  TrendingUp as TrendingUpIcon,
  Notifications as NotificationsIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh,
} from '@mui/icons-material';
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
  Paper,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

const UnifiedDashboard = () => {
  const [dashboardData, setDashboardData] = useState({
    articles: { total: 0, processed: 0, pending: 0 },
    stories: { total: 0, active: 0, alerts: 0 },
    system: { uptime: '0h 0m', status: 'healthy', version: '3.1.0' },
    ml: { processing: false, queue: 0, completed: 0 },
    performance: { cpu: 0, memory: 0, disk: 0 },
    masterArticles: { total: 0, consolidated: 0, singleSource: 0 },
    preprocessing: { tagsExtracted: 0, lastRun: null },
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async() => {
    try {
      // Fetch articles data (this works)
      const articlesResponse = await fetch('/api/articles');
      const articlesData = await articlesResponse.json();

      // Get today's articles for daily digest
      const today = new Date().toISOString().split('T')[0];
      const todayArticles = articlesData.articles?.filter(article =>
        article.published_date && article.published_date.startsWith(today),
      ) || [];

      // Fetch system status (this works)
      const systemResponse = await fetch('/api/system/status');
      const systemData = await systemResponse.json();

      // Try to fetch other data, but handle failures gracefully
      let storiesData = { data: [] };
      let mlData = { processing: false, queue: 0, completed: 0 };
      let pipelineData = { data: { pipeline: { running: false } } };
      let alertsData = { data: [] };
      let masterArticlesData = { total: 0 };
      let preprocessingData = { data: {} };

      try {
        const storiesResponse = await fetch('/api/prioritization/story-threads?status=active');
        if (storiesResponse.ok) storiesData = await storiesResponse.json();
      } catch (e) { console.log('Story threads API not available'); }

      try {
        const mlResponse = await fetch('/api/ml/status');
        if (mlResponse.ok) mlData = await mlResponse.json();
      } catch (e) { console.log('ML status API not available'); }

      try {
        const pipelineResponse = await fetch('/api/automation/pipeline/status');
        if (pipelineResponse.ok) pipelineData = await pipelineResponse.json();
      } catch (e) { console.log('Pipeline status API not available'); }

      try {
        const alertsResponse = await fetch('/api/alerts/storyline/unread');
        if (alertsResponse.ok) alertsData = await alertsResponse.json();
      } catch (e) { console.log('Alerts API not available'); }

      try {
        const masterArticlesResponse = await fetch('/api/master-articles');
        if (masterArticlesResponse.ok) masterArticlesData = await masterArticlesResponse.json();
      } catch (e) { console.log('Master articles API not available'); }

      try {
        const preprocessingResponse = await fetch('/api/automation/preprocessing/status');
        if (preprocessingResponse.ok) preprocessingData = await preprocessingResponse.json();
      } catch (e) { console.log('Preprocessing API not available'); }

      setDashboardData({
        articles: {
          total: articlesData.total || articlesData.articles?.length || 0,
          processed: articlesData.articles?.filter(a => a.processing_status === 'completed').length || 0,
          pending: articlesData.articles?.filter(a => a.processing_status === 'pending').length || 0,
          today: todayArticles.length,
          todayProcessed: todayArticles.filter(a => a.processing_status === 'completed').length,
        },
        stories: {
          total: storiesData.total || storiesData.data?.length || 0,
          active: storiesData.data?.length || 0,
          alerts: alertsData.data?.length || 0,
        },
        system: {
          uptime: systemData.uptime || '0h 0m',
          status: systemData.status || 'healthy',
          version: '3.1.0',
        },
        ml: {
          processing: mlData.processing || false,
          queue: mlData.queue || 0,
          completed: mlData.completed || 0,
        },
        pipeline: {
          running: pipelineData.data?.pipeline?.running || false,
          pipeline_runs: pipelineData.data?.pipeline?.pipeline_runs || 0,
          articles_collected: pipelineData.data?.pipeline?.statistics?.articles_collected || 0,
          articles_processed: pipelineData.data?.pipeline?.statistics?.articles_processed || 0,
          story_threads_created: pipelineData.data?.pipeline?.statistics?.story_threads_created || 0,
        },
        performance: {
          cpu: systemData.cpuUsage ? parseInt(systemData.cpuUsage.replace('%', '')) : 0,
          memory: systemData.memoryUsage ? parseInt(systemData.memoryUsage.replace('%', '')) : 0,
          disk: systemData.diskUsage ? parseInt(systemData.diskUsage.replace('%', '')) : 0,
        },
        masterArticles: {
          total: masterArticlesData.total || 0,
          consolidated: preprocessingData.data?.consolidated_articles || 0,
          singleSource: preprocessingData.data?.single_source_articles || 0,
        },
        preprocessing: {
          tagsExtracted: preprocessingData.data?.processing_statistics?.tags_extracted || 0,
          lastRun: preprocessingData.data?.last_run || null,
        },
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

  const handleRSSCollection = async() => {
    setPipelineLoading(true);
    try {
      const response = await fetch('/api/rss/collect-now', { method: 'POST' });
      const result = await response.json();
      if (result.success) {
        setError(null);
        // Refresh data after collection
        setTimeout(() => fetchDashboardData(), 2000);
      } else {
        setError(`RSS Collection failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err) {
      setError(`RSS Collection error: ${err.message}`);
    } finally {
      setPipelineLoading(false);
    }
  };

  const handlePipelineStart = async() => {
    setPipelineLoading(true);
    try {
      const response = await fetch('/api/automation/pipeline/start', { method: 'POST' });
      const result = await response.json();
      if (result.success) {
        setError(null);
        // Refresh data after starting
        setTimeout(() => fetchDashboardData(), 2000);
      } else {
        setError(`Pipeline start failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err) {
      setError(`Pipeline start error: ${err.message}`);
    } finally {
      setPipelineLoading(false);
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
      <div className="unified-container-fluid">
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      </div>
    );
  }

  return (
    <div className="unified-container-fluid">
      {/* Header */}
      <div className="unified-section">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            News Intelligence Dashboard
          </Typography>
          <Tooltip title="Refresh Data">
            <IconButton onClick={fetchDashboardData} color="primary">
              <Refresh />
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
        <div className="unified-grid unified-grid-6">
          {/* Articles */}
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <Article color="primary" sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#1976d2' }}>
                {dashboardData.articles.total}
              </div>
              <div className="unified-stat-label">Articles</div>
            </div>
            <div className="unified-stat-description">
              Processed: {dashboardData.articles.processed} | Pending: {dashboardData.articles.pending}
            </div>
          </div>

          {/* Story Threads */}
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <TimelineIcon color="secondary" sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#9c27b0' }}>
                {dashboardData.stories.total}
              </div>
              <div className="unified-stat-label">Story Threads</div>
            </div>
            <div className="unified-stat-description">
              Active: {dashboardData.stories.active} | Alerts: {dashboardData.stories.alerts}
            </div>
          </div>

          {/* System Status */}
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <div className="unified-stat-icon">
                {getStatusIcon(dashboardData.system.status)}
              </div>
              <div className="unified-stat-number" style={{ color: getStatusColor(dashboardData.system.status) === 'success' ? '#2e7d32' : '#f57c00' }}>
                {dashboardData.system.status}
              </div>
              <div className="unified-stat-label">System Status</div>
            </div>
            <div className="unified-stat-description">
              Uptime: {dashboardData.system.uptime} | v{dashboardData.system.version}
            </div>
          </div>

          {/* ML Processing */}
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <PsychologyIcon color="info" sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#0288d1' }}>
                {dashboardData.ml.processing ? 'Active' : 'Idle'}
              </div>
              <div className="unified-stat-label">ML Processing</div>
            </div>
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
            <div className="unified-stat-card-content">
              <Article color="success" sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#2e7d32' }}>
                {dashboardData.masterArticles.total}
              </div>
              <div className="unified-stat-label">Master Articles</div>
            </div>
            <div className="unified-stat-description">
              Consolidated: {dashboardData.masterArticles.consolidated} | Single: {dashboardData.masterArticles.singleSource}
            </div>
          </div>

          {/* Pipeline Status */}
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <SpeedIcon color="primary" sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#1976d2' }}>
                {dashboardData.pipeline?.running ? 'Running' : 'Stopped'}
              </div>
              <div className="unified-stat-label">Automated Pipeline</div>
            </div>
            <div className="unified-stat-description">
              Runs: {dashboardData.pipeline?.pipeline_runs || 0} | Collected: {dashboardData.pipeline?.articles_collected || 0}
            </div>
          </div>

          {/* Preprocessing */}
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <MemoryIcon color="info" sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#0288d1' }}>
                {dashboardData.preprocessing.tagsExtracted}
              </div>
              <div className="unified-stat-label">Tags Extracted</div>
            </div>
            <div className="unified-stat-description">
              Last Run: {dashboardData.preprocessing.lastRun ? new Date(dashboardData.preprocessing.lastRun).toLocaleDateString() : 'Never'}
            </div>
          </div>
        </div>
      </div>

      {/* Daily Digest & Pipeline Controls */}
      <div className="unified-section">
        <div className="unified-grid unified-grid-2">
          {/* Daily Digest */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <Article sx={{ mr: 1 }} />
              <div className="unified-content-title">Today's Articles</div>
            </div>
            <div className="unified-content-body">
              <div className="unified-content-text">
                <strong>{dashboardData.articles.today}</strong> articles collected today
                <br />
                <strong>{dashboardData.articles.todayProcessed}</strong> articles processed
                <br />
                <strong>{dashboardData.articles.today - dashboardData.articles.todayProcessed}</strong> articles pending
              </div>
              <div className="unified-content-actions">
                <button
                  className="unified-button unified-button-sm"
                  onClick={() => window.location.href = '/articles'}
                >
                  View All Articles
                </button>
              </div>
            </div>
          </div>

          {/* Pipeline Controls */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <SpeedIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Pipeline Controls</div>
            </div>
            <div className="unified-content-body">
              <div className="unified-content-text">
                Status: {dashboardData.pipeline.running ? 'Running' : 'Stopped'}
                <br />
                Last Run: {dashboardData.pipeline.lastRun || 'Never'}
              </div>
              <div className="unified-content-actions">
                <button
                  className="unified-button unified-button-sm"
                  onClick={handleRSSCollection}
                  disabled={pipelineLoading}
                  style={{ marginRight: '8px' }}
                >
                  {pipelineLoading ? 'Collecting...' : 'Collect RSS Now'}
                </button>
                <button
                  className="unified-button unified-button-sm"
                  onClick={handlePipelineStart}
                  disabled={pipelineLoading}
                >
                  {pipelineLoading ? 'Starting...' : 'Start Pipeline'}
                </button>
              </div>
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
              <Article sx={{ mr: 1 }} />
              <div className="unified-content-title">Recent Articles</div>
            </div>
            <div className="unified-content-body">
              <List dense>
                {recentActivity.map((article, index) => (
                  <React.Fragment key={article.id || index}>
                    <ListItem>
                      <ListItemIcon>
                        <Article fontSize="small" />
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
