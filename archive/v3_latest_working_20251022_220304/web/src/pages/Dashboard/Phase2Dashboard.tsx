/**
 * News Intelligence System v3.3.0 - Phase 2 Enhanced Dashboard
 * Integrates with comprehensive logging, monitoring, and API documentation systems
 *
 * TODO: Phase 2 (Week 5) - Deduplication Dashboard Integration
 * - Add deduplication statistics to main dashboard
 * - Display duplicate detection metrics and trends
 * - Show cluster information and storyline suggestions
 * - Add real-time updates for deduplication metrics
 * - Create visual indicators for system health
 */

import React, { useState, useEffect, useCallback } from 'react';
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
  Tabs,
  Tab,
  Badge,
  ListItemSecondaryAction,
  Switch,
  FormControlLabel,
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
  AutoAwesome as AutoAwesomeIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Queue as QueueIcon,
  BugReport as BugReportIcon,
  Assessment as AssessmentIcon,
  Code as CodeIcon,
  Monitor as MonitorIcon,
  Security as SecurityIcon,
  DataUsage as DataUsageIcon,
  TrendingUp as TrendingUpIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Visibility as VisibilityIcon,
  Download as DownloadIcon,
  DeleteSweep as CleanupIcon,
} from '@mui/icons-material';

import { enhancedApiService } from '../../services/enhancedApiService';
import Logger from '../../utils/logger';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`dashboard-tabpanel-${index}`}
      aria-labelledby={`dashboard-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const Phase2Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  // System data states
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  const [databaseMetrics, setDatabaseMetrics] = useState<any>(null);
  const [logStats, setLogStats] = useState<any>(null);
  const [realtimeLogs, setRealtimeLogs] = useState<any[]>([]);
  const [deduplicationStats, setDeduplicationStats] = useState<any>(null);
  const [apiStatus, setApiStatus] = useState<any>(null);

  // Dialog states
  const [logDialogOpen, setLogDialogOpen] = useState(false);
  const [selectedLogs, setSelectedLogs] = useState<any[]>([]);

  const loadSystemData = useCallback(async() => {
    try {
      setRefreshing(true);
      setError(null);

      Logger.info('Loading system data for Phase 2 dashboard');

      // Load all system data in parallel
      const [
        healthData,
        metricsData,
        dbMetricsData,
        logStatsData,
        realtimeLogsData,
        dedupStatsData,
        apiStatusData,
      ] = await Promise.allSettled([
        enhancedApiService.getSystemHealth(),
        enhancedApiService.getSystemMetrics(),
        enhancedApiService.getDatabaseMetrics(),
        enhancedApiService.getLogStatistics(7),
        enhancedApiService.getRealtimeLogs(20),
        enhancedApiService.getDeduplicationStats(),
        enhancedApiService.getAPIStatus(),
      ]);

      // Process results
      if (healthData.status === 'fulfilled') {
        setSystemHealth(healthData.value);
      }
      if (metricsData.status === 'fulfilled') {
        setSystemMetrics(metricsData.value);
      }
      if (dbMetricsData.status === 'fulfilled') {
        setDatabaseMetrics(dbMetricsData.value);
      }
      if (logStatsData.status === 'fulfilled') {
        setLogStats(logStatsData.value);
      }
      if (realtimeLogsData.status === 'fulfilled') {
        setRealtimeLogs(realtimeLogsData.value);
      }
      if (dedupStatsData.status === 'fulfilled') {
        setDeduplicationStats(dedupStatsData.value);
      }
      if (apiStatusData.status === 'fulfilled') {
        setApiStatus(apiStatusData.value);
      }

      Logger.info('System data loaded successfully');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      Logger.error('Failed to load system data', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadSystemData();
  }, [loadSystemData]);

  // Auto-refresh setup
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(loadSystemData, 30000); // 30 seconds
      setRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, loadSystemData]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleRefresh = () => {
    loadSystemData();
  };

  const handleExportLogs = async() => {
    try {
      const blob = await enhancedApiService.exportLogs({
        format: 'json',
        start_time: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `logs_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      Logger.error('Failed to export logs', err);
    }
  };

  const handleCleanupLogs = async() => {
    try {
      await enhancedApiService.cleanupLogs();
      loadSystemData(); // Refresh data
    } catch (err) {
      Logger.error('Failed to cleanup logs', err);
    }
  };

  const getHealthColor = (status: string) => {
    switch (status?.toLowerCase()) {
    case 'healthy': return 'success';
    case 'warning': return 'warning';
    case 'error': return 'error';
    default: return 'default';
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level?.toUpperCase()) {
    case 'ERROR': return 'error';
    case 'WARNING': return 'warning';
    case 'INFO': return 'info';
    case 'DEBUG': return 'default';
    default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading Phase 2 Dashboard...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Phase 2 Enhanced Dashboard
        </Typography>
        <Box display="flex" gap={2} alignItems="center">
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
            }
            label="Auto Refresh"
          />
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant="scrollable">
          <Tab icon={<DashboardIcon />} label="Overview" />
          <Tab icon={<MonitorIcon />} label="System Health" />
          <Tab icon={<BugReportIcon />} label="Logs & Monitoring" />
          <Tab icon={<AssessmentIcon />} label="Analytics" />
          <Tab icon={<CodeIcon />} label="API Status" />
        </Tabs>
      </Paper>

      {/* Overview Tab */}
      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          {/* System Health Cards */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System Health
                </Typography>
                {systemHealth ? (
                  <Box>
                    <Chip
                      label={systemHealth.status}
                      color={getHealthColor(systemHealth.status)}
                      sx={{ mb: 2 }}
                    />
                    <List dense>
                      <ListItem>
                        <ListItemIcon>
                          <CheckCircleIcon color="success" />
                        </ListItemIcon>
                        <ListItemText primary="Database" secondary={systemHealth.services?.database} />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <CheckCircleIcon color="success" />
                        </ListItemIcon>
                        <ListItemText primary="Redis" secondary={systemHealth.services?.redis} />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          <CheckCircleIcon color="success" />
                        </ListItemIcon>
                        <ListItemText primary="System" secondary={systemHealth.services?.system} />
                      </ListItem>
                    </List>
                  </Box>
                ) : (
                  <CircularProgress size={24} />
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Database Metrics */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Database Metrics
                </Typography>
                {databaseMetrics ? (
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {databaseMetrics.total_articles}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Articles
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {databaseMetrics.total_storylines}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Storylines
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {databaseMetrics.total_rss_feeds}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        RSS Feeds
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {databaseMetrics.recent_articles}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Recent (24h)
                      </Typography>
                    </Grid>
                  </Grid>
                ) : (
                  <CircularProgress size={24} />
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Log Statistics */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Log Statistics (7 days)
                </Typography>
                {logStats ? (
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {logStats.total_entries}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Entries
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="error">
                        {logStats.error_count}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Errors
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="warning">
                        {logStats.warning_count}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Warnings
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="info">
                        {logStats.info_count}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Info
                      </Typography>
                    </Grid>
                  </Grid>
                ) : (
                  <CircularProgress size={24} />
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Deduplication Stats */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Deduplication System
                </Typography>
                {deduplicationStats ? (
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {deduplicationStats.total_articles}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Articles Processed
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {deduplicationStats.total_clusters}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Clusters
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="h4" color="primary">
                        {deduplicationStats.total_duplicate_pairs}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Duplicate Pairs
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Chip
                        label={deduplicationStats.system_status}
                        color={getHealthColor(deduplicationStats.system_status)}
                      />
                    </Grid>
                  </Grid>
                ) : (
                  <CircularProgress size={24} />
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* System Health Tab */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={3}>
          {systemMetrics && (
            <>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      CPU Usage
                    </Typography>
                    <Typography variant="h4" color="primary">
                      {systemMetrics.cpu_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={systemMetrics.cpu_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Memory Usage
                    </Typography>
                    <Typography variant="h4" color="primary">
                      {systemMetrics.memory_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={systemMetrics.memory_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Disk Usage
                    </Typography>
                    <Typography variant="h4" color="primary">
                      {systemMetrics.disk_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={systemMetrics.disk_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Logs & Monitoring Tab */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">
                    Real-time Logs
                  </Typography>
                  <Box>
                    <Button
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={handleExportLogs}
                      sx={{ mr: 1 }}
                    >
                      Export
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<CleanupIcon />}
                      onClick={handleCleanupLogs}
                    >
                      Cleanup
                    </Button>
                  </Box>
                </Box>
                <List>
                  {realtimeLogs.map((log, index) => (
                    <ListItem key={index} divider>
                      <ListItemIcon>
                        <Chip
                          label={log.level}
                          color={getLogLevelColor(log.level)}
                          size="small"
                        />
                      </ListItemIcon>
                      <ListItemText
                        primary={log.message}
                        secondary={`${log.logger} - ${new Date(log.timestamp).toLocaleString()}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Analytics Tab */}
      <TabPanel value={tabValue} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System Analytics
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Advanced analytics and insights will be implemented here using the structured data
                  from our comprehensive logging and monitoring systems.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* API Status Tab */}
      <TabPanel value={tabValue} index={4}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  API Documentation Status
                </Typography>
                {apiStatus ? (
                  <Box>
                    <Typography variant="h5" gutterBottom>
                      {apiStatus.api?.name} v{apiStatus.api?.version}
                    </Typography>
                    <Chip
                      label={apiStatus.api?.status}
                      color={getHealthColor(apiStatus.api?.status)}
                      sx={{ mb: 2 }}
                    />
                    <Typography variant="body1" paragraph>
                      {apiStatus.api?.description}
                    </Typography>
                    <Typography variant="h6" gutterBottom>
                      Available Features:
                    </Typography>
                    <List>
                      {apiStatus.api?.features?.map((feature: string, index: number) => (
                        <ListItem key={index}>
                          <ListItemIcon>
                            <CheckCircleIcon color="success" />
                          </ListItemIcon>
                          <ListItemText primary={feature} />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                ) : (
                  <CircularProgress size={24} />
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};

export default Phase2Dashboard;
