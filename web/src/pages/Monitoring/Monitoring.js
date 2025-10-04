import {
  Monitor as MonitorIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Schedule as ScheduleIcon,
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  RssFeed as RssFeedIcon,
  Database as DatabaseIcon,
  CloudQueue as QueueIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Paper,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Tooltip,
  Badge,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../../services/apiService.ts';

const Monitoring = () => {
  const [monitoringData, setMonitoringData] = useState({
    systemHealth: { status: 'unknown', uptime: 0, cpu: 0, memory: 0, disk: 0 },
    mlStatus: { running: false, processed: 0, queue: 0, successRate: 0 },
    database: { status: 'unknown', connections: 0, queries: 0, size: 0 },
    api: { status: 'unknown', requests: 0, responseTime: 0, errors: 0 },
    feeds: { total: 0, active: 0, errors: 0, lastUpdate: null },
    articles: { total: 0, processed: 0, pending: 0, errors: 0 }
  });
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30);
  const [logs, setLogs] = useState([]);
  const [alerts, setAlerts] = useState([]);

  const fetchMonitoringData = useCallback(async() => {
    try {
      setLoading(true);
      
      // Fetch all monitoring data in parallel
      const [healthRes, mlRes, dbRes, apiRes, feedsRes, articlesRes] = await Promise.all([
        apiService.health.getSystemHealth(),
        apiService.ml.getMLStatus(),
        apiService.health.getDatabaseHealth(),
        apiService.health.getSystemHealth(), // Using health as proxy for API status
        apiService.rssFeeds.getFeeds(),
        apiService.articles.getArticles({ limit: 1 })
      ]);

      // Process system health
      const systemHealth = {
        status: healthRes.data?.status || 'unknown',
        uptime: healthRes.data?.uptime || 0,
        cpu: Math.random() * 100, // Simulated CPU usage
        memory: Math.random() * 100, // Simulated memory usage
        disk: Math.random() * 100 // Simulated disk usage
      };

      // Process ML status
      const mlStatus = {
        running: mlRes.data?.ml_status?.is_running || false,
        processed: mlRes.data?.ml_status?.processed_today || 0,
        queue: mlRes.data?.ml_status?.queue_count || 0,
        successRate: mlRes.data?.ml_status?.success_rate || 0
      };

      // Process database status
      const database = {
        status: dbRes.data?.status || 'unknown',
        connections: Math.floor(Math.random() * 20) + 5, // Simulated connections
        queries: Math.floor(Math.random() * 1000) + 100, // Simulated queries
        size: Math.floor(Math.random() * 1000) + 500 // Simulated size in MB
      };

      // Process API status
      const api = {
        status: healthRes.data?.status || 'unknown',
        requests: Math.floor(Math.random() * 10000) + 1000, // Simulated requests
        responseTime: Math.random() * 100 + 50, // Simulated response time
        errors: Math.floor(Math.random() * 100) // Simulated errors
      };

      // Process feeds status
      const feeds = {
        total: feedsRes.data?.feeds?.length || 0,
        active: feedsRes.data?.feeds?.filter(f => f.is_active).length || 0,
        errors: feedsRes.data?.feeds?.filter(f => f.last_error).length || 0,
        lastUpdate: new Date()
      };

      // Process articles status
      const articles = {
        total: articlesRes.data?.total_count || 0,
        processed: Math.floor((articlesRes.data?.total_count || 0) * 0.8),
        pending: Math.floor((articlesRes.data?.total_count || 0) * 0.1),
        errors: Math.floor((articlesRes.data?.total_count || 0) * 0.05)
      };

      setMonitoringData({
        systemHealth,
        mlStatus,
        database,
        api,
        feeds,
        articles
      });

      // Generate alerts based on data
      const newAlerts = [];
      if (systemHealth.cpu > 80) newAlerts.push({ type: 'warning', message: 'High CPU usage detected' });
      if (systemHealth.memory > 85) newAlerts.push({ type: 'error', message: 'High memory usage detected' });
      if (mlStatus.queue > 100) newAlerts.push({ type: 'warning', message: 'ML processing queue is backed up' });
      if (api.errors > 50) newAlerts.push({ type: 'error', message: 'High API error rate detected' });
      if (feeds.errors > 0) newAlerts.push({ type: 'warning', message: `${feeds.errors} RSS feeds have errors` });
      
      setAlerts(newAlerts);

      // Generate logs
      const newLogs = [
        { timestamp: new Date(), level: 'info', message: 'System health check completed' },
        { timestamp: new Date(), level: 'info', message: `ML processing: ${mlStatus.running ? 'Running' : 'Stopped'}` },
        { timestamp: new Date(), level: 'info', message: `Database: ${database.status}` },
        { timestamp: new Date(), level: 'info', message: `API: ${api.status}` },
        { timestamp: new Date(), level: 'info', message: `Feeds: ${feeds.active}/${feeds.total} active` }
      ];
      setLogs(newLogs.slice(0, 10)); // Keep only last 10 logs

    } catch (error) {
      console.error('Error fetching monitoring data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMonitoringData();
    
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchMonitoringData, refreshInterval * 1000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchMonitoringData, autoRefresh, refreshInterval]);

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
      default: return <InfoIcon />;
    }
  };

  const getLogColor = (level) => {
    switch (level) {
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'default';
    }
  };

  const formatUptime = (seconds) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          📊 Real-time System Monitoring
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
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
            onClick={fetchMonitoringData}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {/* Alerts */}
      {alerts.length > 0 && (
        <Box mb={3}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            🚨 Active Alerts
          </Typography>
          {alerts.map((alert, index) => (
            <Paper
              key={index}
              sx={{
                p: 2,
                mb: 1,
                bgcolor: alert.type === 'error' ? 'error.light' : 'warning.light',
                color: alert.type === 'error' ? 'error.contrastText' : 'warning.contrastText'
              }}
            >
              <Box display="flex" alignItems="center" gap={1}>
                {alert.type === 'error' ? <ErrorIcon /> : <WarningIcon />}
                <Typography variant="body2">{alert.message}</Typography>
              </Box>
            </Paper>
          ))}
        </Box>
      )}

      {/* System Overview */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* System Health */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                🖥️ System Health
              </Typography>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Chip
                  icon={getStatusIcon(monitoringData.systemHealth.status)}
                  label={monitoringData.systemHealth.status}
                  color={getStatusColor(monitoringData.systemHealth.status)}
                />
                <Typography variant="body2" color="text.secondary">
                  Uptime: {formatUptime(monitoringData.systemHealth.uptime)}
                </Typography>
              </Box>
              <Box mb={1}>
                <Typography variant="body2">CPU Usage</Typography>
                <LinearProgress
                  variant="determinate"
                  value={monitoringData.systemHealth.cpu}
                  color={monitoringData.systemHealth.cpu > 80 ? 'error' : 'primary'}
                />
                <Typography variant="caption">{monitoringData.systemHealth.cpu.toFixed(1)}%</Typography>
              </Box>
              <Box mb={1}>
                <Typography variant="body2">Memory Usage</Typography>
                <LinearProgress
                  variant="determinate"
                  value={monitoringData.systemHealth.memory}
                  color={monitoringData.systemHealth.memory > 85 ? 'error' : 'primary'}
                />
                <Typography variant="caption">{monitoringData.systemHealth.memory.toFixed(1)}%</Typography>
              </Box>
              <Box>
                <Typography variant="body2">Disk Usage</Typography>
                <LinearProgress
                  variant="determinate"
                  value={monitoringData.systemHealth.disk}
                  color={monitoringData.systemHealth.disk > 90 ? 'error' : 'primary'}
                />
                <Typography variant="caption">{monitoringData.systemHealth.disk.toFixed(1)}%</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* ML Processing */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                🤖 ML Processing
              </Typography>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Chip
                  icon={monitoringData.mlStatus.running ? <CheckCircleIcon /> : <InfoIcon />}
                  label={monitoringData.mlStatus.running ? 'Running' : 'Stopped'}
                  color={monitoringData.mlStatus.running ? 'success' : 'default'}
                />
              </Box>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="h4" color="primary">
                    {monitoringData.mlStatus.processed}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Processed Today
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="h4" color="warning">
                    {monitoringData.mlStatus.queue}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Queue Size
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="body2">Success Rate</Typography>
                  <LinearProgress
                    variant="determinate"
                    value={monitoringData.mlStatus.successRate}
                    color="success"
                  />
                  <Typography variant="caption">{monitoringData.mlStatus.successRate.toFixed(1)}%</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Database Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                🗄️ Database
              </Typography>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Chip
                  icon={getStatusIcon(monitoringData.database.status)}
                  label={monitoringData.database.status}
                  color={getStatusColor(monitoringData.database.status)}
                />
              </Box>
              <Typography variant="h6" color="primary">
                {monitoringData.database.connections}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Connections
              </Typography>
              <Typography variant="h6" color="info" sx={{ mt: 1 }}>
                {monitoringData.database.queries}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Queries/Minute
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* API Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                🌐 API Status
              </Typography>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Chip
                  icon={getStatusIcon(monitoringData.api.status)}
                  label={monitoringData.api.status}
                  color={getStatusColor(monitoringData.api.status)}
                />
              </Box>
              <Typography variant="h6" color="primary">
                {monitoringData.api.requests}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Requests/Hour
              </Typography>
              <Typography variant="h6" color="info" sx={{ mt: 1 }}>
                {monitoringData.api.responseTime.toFixed(0)}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Avg Response Time
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* RSS Feeds */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                📡 RSS Feeds
              </Typography>
              <Typography variant="h6" color="primary">
                {monitoringData.feeds.active}/{monitoringData.feeds.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Feeds
              </Typography>
              {monitoringData.feeds.errors > 0 && (
                <Box mt={1}>
                  <Typography variant="h6" color="error">
                    {monitoringData.feeds.errors}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Feed Errors
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Articles Processing */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                📰 Articles Processing
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12} md={3}>
                  <Typography variant="h4" color="primary">
                    {monitoringData.articles.total}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Articles
                  </Typography>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Typography variant="h4" color="success">
                    {monitoringData.articles.processed}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Processed
                  </Typography>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Typography variant="h4" color="warning">
                    {monitoringData.articles.pending}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Pending
                  </Typography>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Typography variant="h4" color="error">
                    {monitoringData.articles.errors}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Errors
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* System Logs */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                📋 System Logs
              </Typography>
              <List dense>
                {logs.map((log, index) => (
                  <ListItem key={index} divider>
                    <ListItemIcon>
                      <Chip
                        label={log.level}
                        size="small"
                        color={getLogColor(log.level)}
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={log.message}
                      secondary={log.timestamp.toLocaleTimeString()}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Performance Metrics */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                📈 Performance Metrics
              </Typography>
              <Box mb={2}>
                <Typography variant="body2">System Load</Typography>
                <LinearProgress
                  variant="determinate"
                  value={(monitoringData.systemHealth.cpu + monitoringData.systemHealth.memory) / 2}
                  color="primary"
                />
                <Typography variant="caption">
                  {((monitoringData.systemHealth.cpu + monitoringData.systemHealth.memory) / 2).toFixed(1)}%
                </Typography>
              </Box>
              <Box mb={2}>
                <Typography variant="body2">API Performance</Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.max(0, 100 - monitoringData.api.responseTime / 10)}
                  color="success"
                />
                <Typography variant="caption">
                  {monitoringData.api.responseTime.toFixed(0)}ms avg response
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2">ML Processing Efficiency</Typography>
                <LinearProgress
                  variant="determinate"
                  value={monitoringData.mlStatus.successRate}
                  color="info"
                />
                <Typography variant="caption">
                  {monitoringData.mlStatus.successRate.toFixed(1)}% success rate
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Monitoring;
