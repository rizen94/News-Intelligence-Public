/**
 * News Intelligence System v3.3.0 - Real-time Monitoring Component
 * Provides live monitoring of system health, logs, and performance metrics
 *
 * TODO: Phase 2 (Week 5-8) - Real-time Monitoring Features
 * - Live system logs and debugging
 * - Real-time updates for deduplication metrics
 * - Visual indicators for system health
 * - Advanced monitoring dashboards
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
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Badge,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  BugReport as BugReportIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  Assessment as AssessmentIcon,
  Visibility as VisibilityIcon,
  FilterList as FilterIcon,
  Download as DownloadIcon,
  DeleteSweep as CleanupIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  VideogameAsset as VideogameAssetIcon,
} from '@mui/icons-material';

import apiService from '../../services/apiService';
import Logger from '../../utils/logger';

interface LogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  module?: string;
  function?: string;
  line?: number;
  exception?: any;
  extra_data?: any;
}

interface SystemHealthMetrics {
  error_rate_last_hour: number;
  total_errors_last_24h: number;
  hourly_error_trend: number[];
  system_health_score: number;
  timestamp: string;
}

const RealtimeMonitor: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<ReturnType<
    typeof setTimeout
  > | null>(null);

  // Data states
  const [realtimeLogs, setRealtimeLogs] = useState<LogEntry[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealthMetrics | null>(
    null
  );
  const [logStats, setLogStats] = useState<any>(null);
  const [systemMetrics, setSystemMetrics] = useState<any>(null);

  // Filter states
  const [logLevelFilter, setLogLevelFilter] = useState<string>('ALL');
  const [loggerFilter, setLoggerFilter] = useState<string>('ALL');
  const [maxLogs, setMaxLogs] = useState<number>(50);

  // Dialog states
  const [logDetailDialog, setLogDetailDialog] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);

  const loadRealtimeData = useCallback(async () => {
    try {
      setRefreshing(true);
      setError(null);

      Logger.info('Loading real-time monitoring data');

      // Load real-time data in parallel
      const [logsData, healthData, statsData, metricsData] =
        await Promise.allSettled([
          apiService.getRealtimeLogs(maxLogs), // v4 endpoint
          apiService.getAPIStatus(), // v4 endpoint (includes health metrics)
          apiService.getLogStatistics(7), // v4 endpoint
          apiService.getSystemMetrics(),
        ]);

      // Process results
      if (
        logsData.status === 'fulfilled' &&
        logsData.value?.success &&
        logsData.value?.data?.entries
      ) {
        setRealtimeLogs(logsData.value.data.entries as LogEntry[]);
      }
      if (healthData.status === 'fulfilled' && healthData.value?.success) {
        // Extract health metrics from API status response
        const statusData = healthData.value.data;
        if (statusData) {
          setSystemHealth({
            error_rate_last_hour: statusData.alerts?.recent_errors || 0,
            total_errors_last_24h: statusData.alerts?.recent_errors || 0,
            hourly_error_trend: [],
            system_health_score:
              statusData.overall_status === 'healthy' ? 100 : 50,
            timestamp: healthData.value.timestamp || new Date().toISOString(),
          });
          // Prefer status for current system metrics (includes GPU)
          setSystemMetrics(statusData.system ?? null);
        }
      }
      if (statsData.status === 'fulfilled' && statsData.value?.success) {
        setLogStats(statsData.value);
      }
      if (
        metricsData.status === 'fulfilled' &&
        metricsData.value &&
        (healthData.status !== 'fulfilled' ||
          !healthData.value?.data?.system)
      ) {
        setSystemMetrics(
          metricsData.value?.data?.metrics?.[0] ?? metricsData.value
        );
      }

      Logger.info('Real-time monitoring data loaded successfully');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      Logger.error('Failed to load real-time monitoring data', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [maxLogs]);

  useEffect(() => {
    loadRealtimeData();
  }, [loadRealtimeData]);

  // Auto-refresh setup
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(loadRealtimeData, 10000); // 10 seconds for real-time
      setRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, loadRealtimeData]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleRefresh = () => {
    loadRealtimeData();
  };

  const handleLogClick = (log: LogEntry) => {
    setSelectedLog(log);
    setLogDetailDialog(true);
  };

  const handleExportLogs = async () => {
    try {
      // Use log statistics endpoint for export
      const logs = await apiService.getLogStatistics();
      const logData = JSON.stringify(logs, null, 2);
      const blob = new Blob([logData], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `realtime-logs-${new Date().toISOString()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      /* Commented out until v4 API endpoint is available
      const blob = await apiService.exportLogs({
        format: 'json',
        start_time: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `realtime_logs_${
        new Date().toISOString().split('T')[0]
      }.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      */
    } catch (err) {
      Logger.error('Failed to export logs', err);
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case 'ERROR':
        return 'error';
      case 'WARNING':
        return 'warning';
      case 'INFO':
        return 'info';
      case 'DEBUG':
        return 'default';
      default:
        return 'default';
    }
  };

  const getLogLevelIcon = (level: string) => {
    switch (level?.toUpperCase()) {
      case 'ERROR':
        return <ErrorIcon />;
      case 'WARNING':
        return <WarningIcon />;
      case 'INFO':
        return <InfoIcon />;
      case 'DEBUG':
        return <BugReportIcon />;
      default:
        return <InfoIcon />;
    }
  };

  const filteredLogs = realtimeLogs.filter(log => {
    if (logLevelFilter !== 'ALL' && log.level !== logLevelFilter) return false;
    if (loggerFilter !== 'ALL' && !log.logger.includes(loggerFilter))
      return false;
    return true;
  });

  const getHealthScoreColor = (score: number) => {
    if (score >= 90) return 'success';
    if (score >= 70) return 'warning';
    return 'error';
  };

  if (loading) {
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress />
        <Typography variant='h6' sx={{ ml: 2 }}>
          Loading Real-time Monitor...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Header */}
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1'>
          Real-time System Monitor
        </Typography>
        <Box display='flex' gap={2} alignItems='center'>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
              />
            }
            label='Auto Refresh (10s)'
          />
          <Button
            variant='outlined'
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant='scrollable'>
          <Tab icon={<BugReportIcon />} label='Live Logs' />
          <Tab icon={<AssessmentIcon />} label='System Health' />
          <Tab icon={<SpeedIcon />} label='Performance' />
          <Tab icon={<VisibilityIcon />} label='Log Analysis' />
        </Tabs>
      </Paper>

      {/* Live Logs Tab */}
      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          {/* Filters */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  Log Filters
                </Typography>
                <Grid container spacing={2} alignItems='center'>
                  <Grid item xs={12} sm={3}>
                    <FormControl fullWidth size='small'>
                      <InputLabel>Log Level</InputLabel>
                      <Select
                        value={logLevelFilter}
                        onChange={e => setLogLevelFilter(e.target.value)}
                      >
                        <MenuItem value='ALL'>All Levels</MenuItem>
                        <MenuItem value='ERROR'>Error</MenuItem>
                        <MenuItem value='WARNING'>Warning</MenuItem>
                        <MenuItem value='INFO'>Info</MenuItem>
                        <MenuItem value='DEBUG'>Debug</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <FormControl fullWidth size='small'>
                      <InputLabel>Logger</InputLabel>
                      <Select
                        value={loggerFilter}
                        onChange={e => setLoggerFilter(e.target.value)}
                      >
                        <MenuItem value='ALL'>All Loggers</MenuItem>
                        <MenuItem value='api'>API</MenuItem>
                        <MenuItem value='database'>Database</MenuItem>
                        <MenuItem value='ml'>ML Processing</MenuItem>
                        <MenuItem value='error'>Error Handler</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <TextField
                      fullWidth
                      size='small'
                      label='Max Logs'
                      type='number'
                      value={maxLogs}
                      onChange={e => setMaxLogs(parseInt(e.target.value) || 50)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={3}>
                    <Button
                      variant='outlined'
                      startIcon={<DownloadIcon />}
                      onClick={handleExportLogs}
                      fullWidth
                    >
                      Export Logs
                    </Button>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Logs List */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box
                  display='flex'
                  justifyContent='space-between'
                  alignItems='center'
                  mb={2}
                >
                  <Typography variant='h6'>
                    Real-time Logs ({filteredLogs.length} entries)
                  </Typography>
                  <Badge badgeContent={realtimeLogs.length} color='primary'>
                    <Chip
                      icon={autoRefresh ? <PlayArrowIcon /> : <StopIcon />}
                      label={autoRefresh ? 'Live' : 'Paused'}
                      color={autoRefresh ? 'success' : 'default'}
                    />
                  </Badge>
                </Box>
                <List sx={{ maxHeight: 600, overflow: 'auto' }}>
                  {filteredLogs.map((log, index) => (
                    <ListItem
                      key={index}
                      divider
                      button
                      onClick={() => handleLogClick(log)}
                      sx={{ cursor: 'pointer' }}
                    >
                      <ListItemIcon>
                        <Chip
                          icon={getLogLevelIcon(log.level)}
                          label={log.level}
                          color={getLogLevelColor(log.level)}
                          size='small'
                        />
                      </ListItemIcon>
                      <ListItemText
                        primary={log.message}
                        secondary={`${log.logger} - ${new Date(
                          log.timestamp
                        ).toLocaleString()}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* System Health Tab */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={3}>
          {systemHealth && (
            <>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      System Health Score
                    </Typography>
                    <Typography
                      variant='h2'
                      color={getHealthScoreColor(
                        systemHealth.system_health_score
                      )}
                    >
                      {systemHealth.system_health_score.toFixed(1)}
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemHealth.system_health_score}
                      color={getHealthScoreColor(
                        systemHealth.system_health_score
                      )}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Error Rate (Last Hour)
                    </Typography>
                    <Typography
                      variant='h2'
                      color={
                        systemHealth.error_rate_last_hour > 0.1
                          ? 'error'
                          : 'success'
                      }
                    >
                      {(systemHealth.error_rate_last_hour * 100).toFixed(2)}%
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Total Errors (24h)
                    </Typography>
                    <Typography
                      variant='h2'
                      color={
                        systemHealth.total_errors_last_24h > 10
                          ? 'error'
                          : 'success'
                      }
                    >
                      {systemHealth.total_errors_last_24h}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Performance Tab */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={3}>
          {systemMetrics && (
            <>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      CPU Usage
                    </Typography>
                    <Typography variant='h4' color='primary'>
                      {systemMetrics.cpu_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemMetrics.cpu_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Memory Usage
                    </Typography>
                    <Typography variant='h4' color='primary'>
                      {systemMetrics.memory_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemMetrics.memory_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Disk Usage
                    </Typography>
                    <Typography variant='h4' color='primary'>
                      {systemMetrics.disk_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemMetrics.disk_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>
              {/* GPU: show when metrics available; highlight overwork (≥85% warning, ≥95% error) */}
              {(systemMetrics.gpu_utilization_percent != null ||
                systemMetrics.gpu_vram_percent != null) && (
                <>
                  <Grid item xs={12} md={4}>
                    <Card
                      sx={{
                        borderLeft:
                          systemMetrics.gpu_utilization_percent != null &&
                          systemMetrics.gpu_utilization_percent >= 95
                            ? '4px solid'
                            : systemMetrics.gpu_utilization_percent != null &&
                              systemMetrics.gpu_utilization_percent >= 85
                            ? '4px solid'
                            : undefined,
                        borderColor:
                          systemMetrics.gpu_utilization_percent != null &&
                          systemMetrics.gpu_utilization_percent >= 95
                            ? 'error.main'
                            : systemMetrics.gpu_utilization_percent != null &&
                              systemMetrics.gpu_utilization_percent >= 85
                            ? 'warning.main'
                            : undefined,
                      }}
                    >
                      <CardContent>
                        <Typography
                          variant='h6'
                          gutterBottom
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                          }}
                        >
                          <VideogameAssetIcon fontSize='small' /> GPU
                          Utilization
                          {systemMetrics.gpu_utilization_percent != null &&
                            systemMetrics.gpu_utilization_percent >= 85 && (
                              <Chip
                                size='small'
                                label={
                                  systemMetrics.gpu_utilization_percent >= 95
                                    ? 'Overwork'
                                    : 'High'
                                }
                                color={
                                  systemMetrics.gpu_utilization_percent >= 95
                                    ? 'error'
                                    : 'warning'
                                }
                                sx={{ ml: 0.5 }}
                              />
                            )}
                        </Typography>
                        <Typography variant='h4' color='primary'>
                          {systemMetrics.gpu_utilization_percent != null
                            ? `${systemMetrics.gpu_utilization_percent.toFixed(
                                1
                              )}%`
                            : '—'}
                        </Typography>
                        <LinearProgress
                          variant='determinate'
                          value={Math.min(
                            systemMetrics.gpu_utilization_percent ?? 0,
                            100
                          )}
                          color={
                            systemMetrics.gpu_utilization_percent != null &&
                            systemMetrics.gpu_utilization_percent >= 95
                              ? 'error'
                              : systemMetrics.gpu_utilization_percent != null &&
                                systemMetrics.gpu_utilization_percent >= 85
                              ? 'warning'
                              : 'primary'
                          }
                          sx={{ mt: 2 }}
                        />
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Card
                      sx={{
                        borderLeft:
                          systemMetrics.gpu_vram_percent != null &&
                          systemMetrics.gpu_vram_percent >= 95
                            ? '4px solid'
                            : systemMetrics.gpu_vram_percent != null &&
                              systemMetrics.gpu_vram_percent >= 85
                            ? '4px solid'
                            : undefined,
                        borderColor:
                          systemMetrics.gpu_vram_percent != null &&
                          systemMetrics.gpu_vram_percent >= 95
                            ? 'error.main'
                            : systemMetrics.gpu_vram_percent != null &&
                              systemMetrics.gpu_vram_percent >= 85
                            ? 'warning.main'
                            : undefined,
                      }}
                    >
                      <CardContent>
                        <Typography
                          variant='h6'
                          gutterBottom
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                          }}
                        >
                          <MemoryIcon fontSize='small' /> GPU VRAM
                          {systemMetrics.gpu_vram_percent != null &&
                            systemMetrics.gpu_vram_percent >= 85 && (
                              <Chip
                                size='small'
                                label={
                                  systemMetrics.gpu_vram_percent >= 95
                                    ? 'Overwork'
                                    : 'High'
                                }
                                color={
                                  systemMetrics.gpu_vram_percent >= 95
                                    ? 'error'
                                    : 'warning'
                                }
                                sx={{ ml: 0.5 }}
                              />
                            )}
                        </Typography>
                        <Typography variant='h4' color='primary'>
                          {systemMetrics.gpu_vram_percent != null
                            ? `${systemMetrics.gpu_vram_percent.toFixed(1)}%`
                            : '—'}
                        </Typography>
                        {systemMetrics.gpu_memory_used_mb != null &&
                          systemMetrics.gpu_memory_total_mb != null && (
                            <Typography
                              variant='body2'
                              color='text.secondary'
                              sx={{ mt: 0.5 }}
                            >
                              {systemMetrics.gpu_memory_used_mb} /{' '}
                              {systemMetrics.gpu_memory_total_mb} MB
                            </Typography>
                          )}
                        <LinearProgress
                          variant='determinate'
                          value={Math.min(
                            systemMetrics.gpu_vram_percent ?? 0,
                            100
                          )}
                          color={
                            systemMetrics.gpu_vram_percent != null &&
                            systemMetrics.gpu_vram_percent >= 95
                              ? 'error'
                              : systemMetrics.gpu_vram_percent != null &&
                                systemMetrics.gpu_vram_percent >= 85
                              ? 'warning'
                              : 'primary'
                          }
                          sx={{ mt: 2 }}
                        />
                      </CardContent>
                    </Card>
                  </Grid>
                  {systemMetrics.gpu_temperature_c != null && (
                    <Grid item xs={12} md={4}>
                      <Card>
                        <CardContent>
                          <Typography variant='h6' gutterBottom>
                            GPU Temperature
                          </Typography>
                          <Typography variant='h4' color='primary'>
                            {systemMetrics.gpu_temperature_c}°C
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  )}
                </>
              )}
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Log Analysis Tab */}
      <TabPanel value={tabValue} index={3}>
        <Grid container spacing={3}>
          {logStats && (
            <>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Log Statistics (24h)
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant='h4' color='primary'>
                          {logStats.total_entries}
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          Total Entries
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant='h4' color='error'>
                          {logStats.error_count}
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          Errors
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant='h4' color='warning'>
                          {logStats.warning_count}
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          Warnings
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant='h4' color='info'>
                          {logStats.info_count}
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          Info
                        </Typography>
                      </Grid>
                    </Grid>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Top Loggers
                    </Typography>
                    <List dense>
                      {logStats.top_loggers
                        ?.slice(0, 5)
                        .map((logger: any, index: number) => (
                          <ListItem key={index}>
                            <ListItemText
                              primary={logger.logger}
                              secondary={`${logger.count} entries`}
                            />
                          </ListItem>
                        ))}
                    </List>
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Log Detail Dialog */}
      <Dialog
        open={logDetailDialog}
        onClose={() => setLogDetailDialog(false)}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>Log Entry Details</DialogTitle>
        <DialogContent>
          {selectedLog && (
            <Box>
              <Typography variant='h6' gutterBottom>
                {selectedLog.message}
              </Typography>
              <Typography variant='body2' color='text.secondary' paragraph>
                <strong>Level:</strong> {selectedLog.level}
                <br />
                <strong>Logger:</strong> {selectedLog.logger}
                <br />
                <strong>Timestamp:</strong>{' '}
                {new Date(selectedLog.timestamp).toLocaleString()}
                <br />
                {selectedLog.module && (
                  <>
                    <strong>Module:</strong> {selectedLog.module}
                    <br />
                  </>
                )}
                {selectedLog.function && (
                  <>
                    <strong>Function:</strong> {selectedLog.function}
                    <br />
                  </>
                )}
                {selectedLog.line && (
                  <>
                    <strong>Line:</strong> {selectedLog.line}
                    <br />
                  </>
                )}
              </Typography>
              {selectedLog.exception && (
                <Box>
                  <Typography variant='h6' gutterBottom>
                    Exception Details:
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                    <Typography variant='body2' component='pre'>
                      {JSON.stringify(selectedLog.exception, null, 2)}
                    </Typography>
                  </Paper>
                </Box>
              )}
              {selectedLog.extra_data && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant='h6' gutterBottom>
                    Extra Data:
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                    <Typography variant='body2' component='pre'>
                      {JSON.stringify(selectedLog.extra_data, null, 2)}
                    </Typography>
                  </Paper>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLogDetailDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// TabPanel component
interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role='tabpanel'
      hidden={value !== index}
      id={`monitor-tabpanel-${index}`}
      aria-labelledby={`monitor-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default RealtimeMonitor;
