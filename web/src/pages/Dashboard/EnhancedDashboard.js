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

import { apiService } from '../../services/apiService';
import { useDomainRoute } from '../../hooks/useDomainRoute';

const EnhancedDashboard = () => {
  const { domain } = useDomainRoute();
  // Topic clustering state
  const [topics, setTopics] = useState([]);
  const [clustering, setClustering] = useState(false);
  const [loading, setLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState(null);
  const [monitoringData, setMonitoringData] = useState(null);
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

      // Load dashboard data from working endpoints with better error handling
      const [
        monitoringData,
        healthData,
        articlesData,
        storylinesData,
        rssData,
        pipelineStatusData,
      ] = await Promise.allSettled([
        apiService.getMonitoringDashboard().catch(err => {
          console.error('❌ Monitoring dashboard error:', err);
          // Check if it's a connection error
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            setError('⚠️ API server is not running. Please start the API server on port 8000.');
          }
          return null;
        }),
        apiService.getHealth().catch(err => {
          console.error('❌ Health check error:', err);
          // Check if it's a connection error
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            setError('⚠️ Cannot connect to API server. Please check if the API server is running.');
          }
          return { success: false, status: 'unknown', error: 'Connection failed' };
        }),
        apiService.getArticles({ limit: 100 }, domain).catch(err => {
          console.error('❌ Articles fetch error:', err);
          // Only return empty data if it's not a connection error
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            throw err; // Re-throw connection errors so they're visible
          }
          return { data: { articles: [], total: 0 } };
        }),
        apiService.getStorylines({ limit: 100 }, domain).catch(err => {
          console.error('❌ Storylines fetch error:', err);
          // Only return empty data if it's not a connection error
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            throw err; // Re-throw connection errors so they're visible
          }
          return { data: { storylines: [], total: 0 } };
        }),
        apiService.getRSSFeeds({ limit: 100 }, domain).catch(err => {
          console.error('❌ RSS feeds fetch error:', err);
          // Only return empty data if it's not a connection error
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            throw err; // Re-throw connection errors so they're visible
          }
          return { data: { feeds: [], total: 0 } };
        }),
        apiService.getPipelineStatus().catch(err => {
          console.error('❌ Pipeline status error:', err);
          // Only return default data if it's not a connection error
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            throw err; // Re-throw connection errors so they're visible
          }
          return { success: false, data: { status: 'idle', success_rate: 0, total_traces: 0, active_traces: 0 } };
        }),
      ]);

      // Extract values from Promise.allSettled results
      const monitoringResult = monitoringData.status === 'fulfilled' ? monitoringData.value : null;
      const healthResult = healthData.status === 'fulfilled' ? healthData.value : { success: false, status: 'unknown' };
      const articlesResult = articlesData.status === 'fulfilled' ? articlesData.value : { data: { articles: [], total: 0 } };
      const storylinesResult = storylinesData.status === 'fulfilled' ? storylinesData.value : { data: { storylines: [], total: 0 } };
      const rssResult = rssData.status === 'fulfilled' ? rssData.value : { data: { feeds: [], total: 0 } };
      const pipelineResult = pipelineStatusData.status === 'fulfilled' ? pipelineStatusData.value : { success: false, data: { pipeline_status: 'idle', success_rate: 0, total_traces: 0, active_traces: 0 } };

      // Extract articles from response (handle nested data structure)
      const articlesList = articlesResult.data?.articles ||
                          articlesResult.data?.data?.articles ||
                          articlesResult.articles ||
                          [];
      const totalArticlesCount = articlesResult.data?.total ||
                                 articlesResult.data?.data?.total ||
                                 articlesResult.total ||
                                 articlesList.length;

      // Extract storylines from response (handle new API format: { data: [...], pagination: {...} })
      const storylinesList = Array.isArray(storylinesResult.data) 
                          ? storylinesResult.data 
                          : storylinesResult.data?.storylines ||
                            storylinesResult.data?.data?.storylines ||
                            storylinesResult.storylines ||
                            [];
      const totalStorylinesCount = storylinesResult.pagination?.total ||
                                   storylinesResult.data?.total ||
                                   storylinesResult.data?.data?.total ||
                                   storylinesResult.total ||
                                   storylinesList.length;

      // Calculate today's articles
      const today = new Date().toISOString().split('T')[0];
      const todayArticles = articlesList.filter(
        article =>
          article.published_at && article.published_at.startsWith(today),
      );

      // Calculate this week's articles
      const weekAgo = new Date();
      weekAgo.setDate(weekAgo.getDate() - 7);
      const weekArticles = articlesList.filter(
        article =>
          article.published_at && new Date(article.published_at) >= weekAgo,
      );

      // Determine overall health status
      const healthStatus = healthResult?.status || 
                          healthResult?.data?.status ||
                          (monitoringResult?.data?.database?.status === 'healthy' && 
                           monitoringResult?.data?.redis?.status === 'healthy' ? 'healthy' : 'unknown');

      // Combine the data into system status
      const status = {
        overall: monitoringResult?.data?.overall_status || healthStatus,
        health: healthResult,
        articleStats: {
          data: {
            total_articles: totalArticlesCount,
            articles_today: todayArticles.length,
            articles_this_week: weekArticles.length,
            top_sources: [],
          },
        },
        rssStats: {
          data: {
            total_feeds: rssResult.data?.total || rssResult.data?.feeds?.length || 0,
            active_feeds:
              rssResult.data?.feeds?.filter(feed => feed.is_active)?.length || 0,
            feeds_with_errors: 0,
          },
        },
        storylineStats: {
          data: {
            total_storylines: totalStorylinesCount,
            active_storylines:
              storylinesList.filter(
                s => s.status === 'active',
              )?.length || 0,
          },
        },
        pipelineStatus: {
          data: {
            status: pipelineResult?.data?.pipeline_status === 'running' ? 'running' : (pipelineResult?.data?.pipeline_status || 'idle'),
            success_rate: pipelineResult?.data?.success_rate || 0,
            total_traces: pipelineResult?.data?.total_traces || 0,
            active_traces: pipelineResult?.data?.active_traces || 0,
          },
        },
        recentArticles: articlesResult.data?.articles?.slice(0, 5) || [],
        analytics: {},
        systemMetrics: monitoringResult?.data?.system || {},
      };

      setSystemStatus(status);
      setMonitoringData(monitoringResult);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error loading system data:', err);
      setError('Failed to load system data');
    } finally {
      setLoading(false);
    }
  }, [domain]);

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

      const response = await apiService.updateRSSFeeds();

      // Wait for actual completion - API now runs synchronously
      if (response.success) {
        setDisplayRssETA(
          `Complete - ${response.articles_added || 0} articles added`,
        );
        setTimeout(() => {
          setDisplayRssETA(null);
        }, 2000); // Show success message for 2 seconds
      } else {
        setDisplayRssETA('Failed');
        setTimeout(() => {
          setDisplayRssETA(null);
        }, 2000);
      }

      setRssRunning(false);
      saveProcessStatus('rss', false);
      loadSystemData(); // Refresh data after completion
    } catch (error) {
      console.error('RSS update failed:', error);
      setRssRunning(false);
      setDisplayRssETA('Error');
      setTimeout(() => {
        setDisplayRssETA(null);
      }, 2000);
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
      setRssRunning(true);
      setPipelineRunning(true);
      setAnalysisRunning(true);
      saveProcessStatus('master', true);

      // Use orchestrated pipeline endpoint
      const response = await apiService.runAllPipelineProcesses();

      if (response.success) {
        setDisplayRssETA('Completed');
        setDisplayPipelineETA('Completed');
        setDisplayAnalysisETA('Completed');

        // Clear states after showing completion
        setTimeout(() => {
          setMasterRunning(false);
          setRssRunning(false);
          setPipelineRunning(false);
          setAnalysisRunning(false);
          setDisplayRssETA(null);
          setDisplayPipelineETA(null);
          setDisplayAnalysisETA(null);
          saveProcessStatus('master', false);
          loadSystemData(); // Refresh data after completion
        }, 3000);
      } else {
        throw new Error(response.error || 'Pipeline orchestration failed');
      }
    } catch (error) {
      console.error('Master switch execution failed:', error);
      setMasterRunning(false);
      setRssRunning(false);
      setPipelineRunning(false);
      setAnalysisRunning(false);
      setDisplayRssETA(null);
      setDisplayPipelineETA(null);
      setDisplayAnalysisETA(null);
      saveProcessStatus('master', false);
    }
  };

  const handleProcessAction = action => {
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

  const getStatusColor = status => {
    switch (status) {
    case 'healthy':
      return 'success';
    case 'degraded':
      return 'warning';
    case 'error':
      return 'error';
    default:
      return 'default';
    }
  };

  const getStatusIcon = status => {
    switch (status) {
    case 'healthy':
      return <CheckCircleIcon />;
    case 'degraded':
      return <WarningIcon />;
    case 'error':
      return <WarningIcon />;
    default:
      return <WarningIcon />;
    }
  };

  if (loading && !systemStatus) {
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
          News Intelligence Dashboard
        </Typography>
        <Box display='flex' alignItems='center' gap={2}>
          <Typography variant='body2' color='text.secondary'>
            Last updated:{' '}
            {lastUpdate ? lastUpdate.toLocaleTimeString() : 'Never'}
          </Typography>
          <Tooltip title='Refresh Data'>
            <IconButton onClick={handleRefresh} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      <Grid container spacing={3}>
        {/* System Health Overview */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <DashboardIcon color='primary' sx={{ mr: 1 }} />
                <Typography variant='h6'>System Health</Typography>
              </Box>
              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Chip
                      icon={getStatusIcon(systemStatus?.overall)}
                      label={systemStatus?.overall?.toUpperCase() || 'UNKNOWN'}
                      color={getStatusColor(systemStatus?.overall)}
                      size='large'
                    />
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mt: 1 }}
                    >
                      Overall Status
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {monitoringData?.data?.database?.status === 'healthy'
                        ? '✓'
                        : '✗'}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Database
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {monitoringData?.data?.redis?.status === 'healthy'
                        ? '✓'
                        : '✗'}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Redis Cache
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {monitoringData?.data?.system?.status === 'healthy'
                        ? '✓'
                        : '✗'}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
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
              <Box display='flex' alignItems='center' mb={2}>
                <Article color='primary' sx={{ mr: 1 }} />
                <Typography variant='h6'>Articles</Typography>
              </Box>
              <Typography variant='h4' color='primary'>
                {systemStatus?.articleStats?.data?.total_articles || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Total Articles
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant='body2' color='text.secondary'>
                Today: {systemStatus?.articleStats?.data?.articles_today || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                This Week:{' '}
                {systemStatus?.articleStats?.data?.articles_this_week || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <RssFeedIcon color='primary' sx={{ mr: 1 }} />
                <Typography variant='h6'>RSS Feeds</Typography>
              </Box>
              <Typography variant='h4' color='primary'>
                {systemStatus?.rssStats?.data?.active_feeds || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Active Feeds
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant='body2' color='text.secondary'>
                Total: {systemStatus?.rssStats?.data?.total_feeds || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Errors: {systemStatus?.rssStats?.data?.feeds_with_errors || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <TimelineIcon color='primary' sx={{ mr: 1 }} />
                <Typography variant='h6'>Storylines</Typography>
              </Box>
              <Typography variant='h4' color='primary'>
                {systemStatus?.storylineStats?.data?.active_storylines || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Active Storylines
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant='body2' color='text.secondary'>
                Total:{' '}
                {systemStatus?.storylineStats?.data?.total_storylines || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                New Today: {systemStatus?.storylineStats?.data?.new_today || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <SpeedIcon color='primary' sx={{ mr: 1 }} />
                <Typography variant='h6'>Pipeline Status</Typography>
              </Box>
              <Typography
                variant='h4'
                color={
                  systemStatus?.pipelineStatus?.data?.status === 'running'
                    ? 'warning'
                    : systemStatus?.pipelineStatus?.data?.status === 'healthy'
                      ? 'success'
                      : 'primary'
                }
              >
                {systemStatus?.pipelineStatus?.data?.status === 'running'
                  ? 'RUNNING'
                  : systemStatus?.pipelineStatus?.data?.status === 'healthy'
                    ? 'HEALTHY'
                    : 'IDLE'}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Processing Status
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant='body2' color='text.secondary'>
                Success Rate:{' '}
                {systemStatus?.pipelineStatus?.data?.success_rate || 0}%
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Active Traces:{' '}
                {systemStatus?.pipelineStatus?.data?.active_traces || 0}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Total Traces:{' '}
                {systemStatus?.pipelineStatus?.data?.total_traces || 0}
              </Typography>

              {/* Process Control Buttons with ETA */}
              <Divider sx={{ my: 2 }} />
              <Typography variant='subtitle2' gutterBottom>
                Process Controls
              </Typography>

              <Box display='flex' flexDirection='column' gap={1}>
                <Button
                  variant={pipelineRunning ? 'contained' : 'outlined'}
                  color={pipelineRunning ? 'warning' : 'primary'}
                  size='small'
                  startIcon={pipelineRunning ? <StopIcon /> : <PlayArrowIcon />}
                  onClick={() => handleProcessAction('pipeline')}
                  disabled={masterRunning || rssRunning || analysisRunning}
                  fullWidth
                >
                  {pipelineRunning
                    ? `Pipeline Running ${
                      displayPipelineETA ? `(${displayPipelineETA})` : ''
                    }`
                    : 'Trigger Pipeline'}
                </Button>

                <Button
                  variant={rssRunning ? 'contained' : 'outlined'}
                  color={rssRunning ? 'warning' : 'primary'}
                  size='small'
                  startIcon={rssRunning ? <StopIcon /> : <RssFeedIcon />}
                  onClick={() => handleProcessAction('rss')}
                  disabled={masterRunning || pipelineRunning || analysisRunning}
                  fullWidth
                >
                  {rssRunning
                    ? `RSS Updating ${
                      displayRssETA ? `(${displayRssETA})` : ''
                    }`
                    : 'Update RSS Feeds'}
                </Button>

                <Button
                  variant={analysisRunning ? 'contained' : 'outlined'}
                  color={analysisRunning ? 'warning' : 'primary'}
                  size='small'
                  startIcon={analysisRunning ? <StopIcon /> : <Analytics />}
                  onClick={() => handleProcessAction('analysis')}
                  disabled={masterRunning || pipelineRunning || rssRunning}
                  fullWidth
                >
                  {analysisRunning
                    ? `Analysis Running ${
                      displayAnalysisETA ? `(${displayAnalysisETA})` : ''
                    }`
                    : 'Run AI Analysis'}
                </Button>

                <Button
                  variant={masterRunning ? 'contained' : 'outlined'}
                  color={masterRunning ? 'warning' : 'secondary'}
                  size='small'
                  startIcon={masterRunning ? <StopIcon /> : <QueueIcon />}
                  onClick={() => handleProcessAction('master')}
                  disabled={pipelineRunning || rssRunning || analysisRunning}
                  fullWidth
                >
                  {masterRunning
                    ? 'Master Process Running'
                    : 'Complete All Processes'}
                </Button>
              </Box>

              {/* Queue Status Indicators */}
              {masterRunning && (
                <Box mt={2}>
                  <Typography
                    variant='caption'
                    color='primary'
                    display='block'
                    gutterBottom
                  >
                    Process Queue Status:
                  </Typography>
                  <Box display='flex' gap={0.5} flexWrap='wrap'>
                    <Chip
                      label={rssRunning ? 'RSS: Running' : 'RSS: Queued'}
                      color={rssRunning ? 'warning' : 'info'}
                      size='small'
                    />
                    <Chip
                      label={
                        pipelineRunning
                          ? 'Pipeline: Running'
                          : 'Pipeline: Queued'
                      }
                      color={pipelineRunning ? 'warning' : 'info'}
                      size='small'
                    />
                    <Chip
                      label={
                        analysisRunning
                          ? 'Analysis: Running'
                          : 'Analysis: Queued'
                      }
                      color={analysisRunning ? 'warning' : 'info'}
                      size='small'
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
              <Typography variant='h6' gutterBottom>
                <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                AI Analysis Features
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <AutoAwesomeIcon
                      color='primary'
                      sx={{ fontSize: 40, mb: 1 }}
                    />
                    <Typography variant='h6'>
                      Multi-Perspective Analysis
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Analyze news from multiple viewpoints
                    </Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Analytics color='primary' sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant='h6'>Impact Assessment</Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Evaluate potential impacts across dimensions
                    </Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Schedule color='primary' sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant='h6'>Predictive Analysis</Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Forecast future developments
                    </Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
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
              <Typography variant='h6' gutterBottom>
                Quick Actions
              </Typography>
              <Box display='flex' gap={2} flexWrap='wrap'>
                <Button variant='contained' startIcon={<Article />}>
                  View Articles
                </Button>
                <Button variant='outlined' startIcon={<RssFeedIcon />}>
                  Manage RSS Feeds
                </Button>
                <Button variant='outlined' startIcon={<TimelineIcon />}>
                  Create Storyline
                </Button>
                <Button variant='outlined' startIcon={<Analytics />}>
                  View Analytics
                </Button>
                <Button
                  variant='outlined'
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
              <Typography variant='h6' gutterBottom>
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
                        primary='API Endpoint'
                        secondary={
                          process.env.REACT_APP_API_URL ||
                          'http://localhost:8001'
                        }
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <MemoryIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary='Version'
                        secondary='News Intelligence System v3.0'
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <StorageIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary='Database'
                        secondary='PostgreSQL with Redis Cache'
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
                        primary='Status'
                        secondary={systemStatus?.overall || 'Unknown'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <Schedule />
                      </ListItemIcon>
                      <ListItemText
                        primary='Last Update'
                        secondary={
                          lastUpdate ? lastUpdate.toLocaleString() : 'Never'
                        }
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <PsychologyIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary='AI Features'
                        secondary='Multi-perspective, Impact Assessment, Predictive Analysis'
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
      <Dialog
        open={confirmDialogOpen}
        onClose={() => setConfirmDialogOpen(false)}
      >
        <DialogTitle>Confirm Process Action</DialogTitle>
        <DialogContent>
          <Typography>
            {confirmAction === 'pipeline' &&
              'This will trigger the article processing pipeline. This may take several minutes and will process all pending articles. Continue?'}
            {confirmAction === 'rss' &&
              'This will update all RSS feeds and collect new articles. This may take a few minutes depending on the number of feeds. Continue?'}
            {confirmAction === 'analysis' &&
              'This will run AI analysis on recent articles including sentiment analysis, entity extraction, and content classification. Continue?'}
            {confirmAction === 'master' &&
              'This will execute all processes in sequence: RSS update, pipeline processing, and AI analysis. This may take several minutes. Continue?'}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={confirmProcessAction}
            variant='contained'
            color='primary'
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnhancedDashboard;
