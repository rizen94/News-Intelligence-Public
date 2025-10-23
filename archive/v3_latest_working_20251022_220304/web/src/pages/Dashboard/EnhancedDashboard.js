import {
  Dashboard as DashboardIcon,
  Article,
  RssFeed as RssFeedIcon,
  Timeline as TimelineIcon,
  Refresh,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Schedule,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  Analytics,
  AutoAwesome as AutoAwesomeIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Queue as QueueIcon,
} from '@mui/icons-material';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';

import { apiService } from '../../services/apiService.ts';

const EnhancedDashboard = () => {

  // Topic clustering state
  const [topics, setTopics] = useState([]);
  const [clustering, setClustering] = useState(false);
  const [loading, setLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Process status states
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [rssRunning, setRssRunning] = useState(false);
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [masterRunning, setMasterRunning] = useState(false);

  // ETA states
  const [displayPipelineETA, setDisplayPipelineETA] = useState(null);
  const [displayRssETA, setDisplayRssETA] = useState(null);
  const [displayAnalysisETA, setDisplayAnalysisETA] = useState(null);

  // Dialog states
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  const loadSystemData = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);

      // Load dashboard data from the proper endpoint
      const [monitoringData, healthData, pipelineStatus, pipelinePerformance] = await Promise.all([
        apiService.getMonitoringDashboard(),
        apiService.getHealth(),
        apiService.getPipelineStatus(),
        apiService.getPipelinePerformance(),
      ]);

      // Combine the data into system status
      const status = {
        overall: healthData.data?.status || 'unknown',
        health: healthData,
        articleStats: {
          data: {
            total_articles: monitoringData?.data?.database_metrics?.total_articles || 0,
            articles_today: monitoringData?.data?.database_metrics?.recent_articles || 0,
            articles_this_week: systemStatus?.articleStats?.data?.articles_this_week || 0,
            top_sources: [],
          },
        },
        rssStats: {
          data: {
            total_feeds: systemStatus?.rssStats?.data?.total_feeds || 0,
            active_feeds: 0,
            feeds_with_errors: 0,
          },
        },
        storylineStats: {
          data: {
            total_storylines: systemStatus?.storylineStats?.data?.total_storylines || 0,
            active_storylines: 0,
          },
        },
        pipelineStatus: {
          data: {
            status: pipelineStatus.active_traces_count > 0 ? 'running' : 'idle',
            success_rate: pipelinePerformance.success_rate || 0,
            total_traces: pipelinePerformance.total_traces || 0,
            active_traces: pipelineStatus.active_traces_count || 0,
          },
        },
        recentArticles: [],
        analytics: {},
        systemMetrics: monitoringData?.data?.system_metrics || {},
      };

      setSystemStatus(status);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error loading system data:', err);
      setError('Failed to load system data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSystemData();
    const interval = setInterval(loadSystemData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [loadSystemData]);

  // Load process status from localStorage on mount
  useEffect(() => {
    const savedPipelineStatus = localStorage.getItem('pipelineStatus');
    const savedRssStatus = localStorage.getItem('rssStatus');
    const savedAnalysisStatus = localStorage.getItem('analysisStatus');
    const savedMasterStatus = localStorage.getItem('masterStatus');

    if (savedPipelineStatus) {
      const status = JSON.parse(savedPipelineStatus);
      setPipelineRunning(status.running);
      setDisplayPipelineETA(status.eta);
    }
    if (savedRssStatus) {
      const status = JSON.parse(savedRssStatus);
      setRssRunning(status.running);
      setDisplayRssETA(status.eta);
    }
    if (savedAnalysisStatus) {
      const status = JSON.parse(savedAnalysisStatus);
      setAnalysisRunning(status.running);
      setDisplayAnalysisETA(status.eta);
    }
    if (savedMasterStatus) {
      const status = JSON.parse(savedMasterStatus);
      setMasterRunning(status.running);
    }
  }, []);

  const handleRefresh = () => {
    loadSystemData();
  };

  // Process management functions
  const saveProcessStatus = (process, running, eta = null) => {
    const status = { running, eta, timestamp: new Date().toISOString() };
    localStorage.setItem(`${process}Status`, JSON.stringify(status));
  };

  const executeTriggerPipeline = async() => {
    try {
      setPipelineRunning(true);
      setDisplayPipelineETA('Processing...');
      saveProcessStatus('pipeline', true, 'Processing...');

      await apiService.triggerPipeline();

      // Simulate processing time
      setTimeout(() => {
        setPipelineRunning(false);
        setDisplayPipelineETA(null);
        saveProcessStatus('pipeline', false);
        loadSystemData(); // Refresh data after completion
      }, 30000); // 30 seconds
    } catch (error) {
      console.error('Pipeline execution failed:', error);
      setPipelineRunning(false);
      setDisplayPipelineETA(null);
      saveProcessStatus('pipeline', false);
    }
  };

  const executeUpdateRSSFeeds = async() => {
    try {
      setRssRunning(true);
      setDisplayRssETA('Updating...');
      saveProcessStatus('rss', true, 'Updating...');

      await apiService.updateRSSFeeds();

      // Simulate processing time
      setTimeout(() => {
        setRssRunning(false);
        setDisplayRssETA(null);
        saveProcessStatus('rss', false);
        loadSystemData(); // Refresh data after completion
      }, 15000); // 15 seconds
    } catch (error) {
      console.error('RSS update failed:', error);
      setRssRunning(false);
      setDisplayRssETA(null);
      saveProcessStatus('rss', false);
    }
  };

  const executeRunAIAnalysis = async() => {
    try {
      setAnalysisRunning(true);
      setDisplayAnalysisETA('Analyzing...');
      saveProcessStatus('analysis', true, 'Analyzing...');

      await apiService.runAIAnalysis();

      // Simulate processing time
      setTimeout(() => {
        setAnalysisRunning(false);
        setDisplayAnalysisETA(null);
        saveProcessStatus('analysis', false);
        loadSystemData(); // Refresh data after completion
      }, 20000); // 20 seconds
    } catch (error) {
      console.error('AI analysis failed:', error);
      setAnalysisRunning(false);
      setDisplayAnalysisETA(null);
      saveProcessStatus('analysis', false);
    }
  };

  const executeMasterSwitch = async() => {
    try {
      setMasterRunning(true);
      saveProcessStatus('master', true);

      // Execute processes in sequence
      await executeUpdateRSSFeeds();
      await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay

      await executeTriggerPipeline();
      await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay

      await executeRunAIAnalysis();

      setMasterRunning(false);
      saveProcessStatus('master', false);
    } catch (error) {
      console.error('Master switch execution failed:', error);
      setMasterRunning(false);
      saveProcessStatus('master', false);
    }
  };

  const handleProcessAction = (action) => {
    setConfirmAction(action);
    setConfirmDialogOpen(true);
  };

  const confirmProcessAction = () => {
    setConfirmDialogOpen(false);

    switch (confirmAction) {
    case 'pipeline':
      executeTriggerPipeline();
      break;
    case 'rss':
      executeUpdateRSSFeeds();
      break;
    case 'analysis':
      executeRunAIAnalysis();
      break;
    case 'master':
      executeMasterSwitch();
      break;
    default:
      break;
    }
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
              <Refresh />
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
                <Article color="primary" sx={{ mr: 1 }} />
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
                New Today: {systemStatus?.storylineStats?.data?.new_today || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <SpeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Pipeline Status</Typography>
              </Box>
              <Typography variant="h4" color={systemStatus?.pipelineStatus?.data?.status === 'running' ? 'warning' : 'primary'}>
                {systemStatus?.pipelineStatus?.data?.status === 'running' ? 'RUNNING' : 'IDLE'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Processing Status
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Success Rate: {systemStatus?.pipelineStatus?.data?.success_rate || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Traces: {systemStatus?.pipelineStatus?.data?.active_traces || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Traces: {systemStatus?.pipelineStatus?.data?.total_traces || 0}
              </Typography>

              {/* Process Control Buttons with ETA */}
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>
                Process Controls
              </Typography>

              <Box display="flex" flexDirection="column" gap={1}>
                <Button
                  variant={pipelineRunning ? 'contained' : 'outlined'}
                  color={pipelineRunning ? 'warning' : 'primary'}
                  size="small"
                  startIcon={pipelineRunning ? <StopIcon /> : <PlayArrowIcon />}
                  onClick={() => handleProcessAction('pipeline')}
                  disabled={masterRunning || rssRunning || analysisRunning}
                  fullWidth
                >
                  {pipelineRunning ? `Pipeline Running ${displayPipelineETA ? `(${displayPipelineETA})` : ''}` : 'Trigger Pipeline'}
                </Button>

                <Button
                  variant={rssRunning ? 'contained' : 'outlined'}
                  color={rssRunning ? 'warning' : 'primary'}
                  size="small"
                  startIcon={rssRunning ? <StopIcon /> : <RssFeedIcon />}
                  onClick={() => handleProcessAction('rss')}
                  disabled={masterRunning || pipelineRunning || analysisRunning}
                  fullWidth
                >
                  {rssRunning ? `RSS Updating ${displayRssETA ? `(${displayRssETA})` : ''}` : 'Update RSS Feeds'}
                </Button>

                <Button
                  variant={analysisRunning ? 'contained' : 'outlined'}
                  color={analysisRunning ? 'warning' : 'primary'}
                  size="small"
                  startIcon={analysisRunning ? <StopIcon /> : <Analytics />}
                  onClick={() => handleProcessAction('analysis')}
                  disabled={masterRunning || pipelineRunning || rssRunning}
                  fullWidth
                >
                  {analysisRunning ? `Analysis Running ${displayAnalysisETA ? `(${displayAnalysisETA})` : ''}` : 'Run AI Analysis'}
                </Button>

                <Button
                  variant={masterRunning ? 'contained' : 'outlined'}
                  color={masterRunning ? 'warning' : 'secondary'}
                  size="small"
                  startIcon={masterRunning ? <StopIcon /> : <QueueIcon />}
                  onClick={() => handleProcessAction('master')}
                  disabled={pipelineRunning || rssRunning || analysisRunning}
                  fullWidth
                >
                  {masterRunning ? 'Master Process Running' : 'Complete All Processes'}
                </Button>
              </Box>

              {/* Queue Status Indicators */}
              {masterRunning && (
                <Box mt={2}>
                  <Typography variant="caption" color="primary" display="block" gutterBottom>
                    Process Queue Status:
                  </Typography>
                  <Box display="flex" gap={0.5} flexWrap="wrap">
                    <Chip
                      label={rssRunning ? 'RSS: Running' : 'RSS: Queued'}
                      color={rssRunning ? 'warning' : 'info'}
                      size="small"
                    />
                    <Chip
                      label={pipelineRunning ? 'Pipeline: Running' : 'Pipeline: Queued'}
                      color={pipelineRunning ? 'warning' : 'info'}
                      size="small"
                    />
                    <Chip
                      label={analysisRunning ? 'Analysis: Running' : 'Analysis: Queued'}
                      color={analysisRunning ? 'warning' : 'info'}
                      size="small"
                    />
                  </Box>
                </Box>
              )}
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
                    <Analytics color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="h6">Impact Assessment</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Evaluate potential impacts across dimensions
                    </Typography>
                    <Chip label="Available" color="success" size="small" sx={{ mt: 1 }} />
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Schedule color="primary" sx={{ fontSize: 40, mb: 1 }} />
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
                <Button variant="contained" startIcon={<Article />}>
                  View Articles
                </Button>
                <Button variant="outlined" startIcon={<RssFeedIcon />}>
                  Manage RSS Feeds
                </Button>
                <Button variant="outlined" startIcon={<TimelineIcon />}>
                  Create Storyline
                </Button>
                <Button variant="outlined" startIcon={<Analytics />}>
                  View Analytics
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Refresh />}
                  onClick={handleRefresh}
                  disabled={loading}
                >
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
                        <Schedule />
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

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialogOpen} onClose={() => setConfirmDialogOpen(false)}>
        <DialogTitle>Confirm Process Action</DialogTitle>
        <DialogContent>
          <Typography>
            {confirmAction === 'pipeline' &&
              'This will trigger the article processing pipeline. This may take several minutes and will process all pending articles. Continue?'
            }
            {confirmAction === 'rss' &&
              'This will update all RSS feeds and collect new articles. This may take a few minutes depending on the number of feeds. Continue?'
            }
            {confirmAction === 'analysis' &&
              'This will run AI analysis on recent articles including sentiment analysis, entity extraction, and content classification. Continue?'
            }
            {confirmAction === 'master' &&
              'This will execute all processes in sequence: RSS update, pipeline processing, and AI analysis. This may take several minutes. Continue?'
            }
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmProcessAction} variant="contained" color="primary">
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnhancedDashboard;
