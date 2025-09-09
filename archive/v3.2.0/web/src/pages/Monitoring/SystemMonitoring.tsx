/**
 * System Monitoring Page v3.0
 * Real-time system performance and AI processing monitoring
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  LinearProgress,
  Alert,
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

interface SystemMetrics {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  memory_used_gb: number;
  memory_total_gb: number;
  disk_usage_percent: number;
  disk_free_gb: number;
  network_io_bytes: number;
  process_count: number;
  load_average: number[];
}

interface AIMetrics {
  timestamp: string;
  model_name: string;
  processing_time: number;
  tokens_processed: number;
  cache_hits: number;
  cache_misses: number;
  memory_usage_mb: number;
  gpu_usage_percent: number;
  gpu_memory_mb: number;
  success: boolean;
  error_message?: string;
}

interface SystemStatus {
  system_health: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    status: 'healthy' | 'degraded' | 'unhealthy';
  };
  ai_performance: {
    avg_processing_time: number;
    success_rate: number;
    status: 'healthy' | 'degraded' | 'unhealthy';
  };
  cache_performance: {
    hit_rate: number;
    memory_usage_mb: number;
    total_entries: number;
    status: 'healthy' | 'degraded' | 'unhealthy';
  };
  alerts: {
    critical: number;
    warning: number;
    total: number;
  };
  timestamp: string;
}

const SystemMonitoring: React.FC = () => {
  const [isMonitoring, setIsMonitoring] = useState(true);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics[]>([]);
  const [aiMetrics, setAiMetrics] = useState<AIMetrics[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Sample data for demonstration
  const generateSampleSystemMetrics = (): SystemMetrics[] => {
    const data: SystemMetrics[] = [];
    const now = new Date();
    
    for (let i = 23; i >= 0; i--) {
      const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000);
      data.push({
        timestamp: timestamp.toISOString(),
        cpu_percent: Math.random() * 40 + 20, // 20-60%
        memory_percent: Math.random() * 30 + 40, // 40-70%
        memory_used_gb: Math.random() * 4 + 6, // 6-10 GB
        memory_total_gb: 16,
        disk_usage_percent: Math.random() * 20 + 60, // 60-80%
        disk_free_gb: Math.random() * 100 + 200, // 200-300 GB
        network_io_bytes: Math.random() * 1000000 + 500000,
        process_count: Math.floor(Math.random() * 50 + 100),
        load_average: [Math.random() * 2, Math.random() * 2, Math.random() * 2]
      });
    }
    return data;
  };

  const generateSampleAIMetrics = (): AIMetrics[] => {
    const data: AIMetrics[] = [];
    const now = new Date();
    const models = ['llama3.1:8b', 'llama3.1:70b', 'nomic-embed-text'];
    
    for (let i = 11; i >= 0; i--) {
      const timestamp = new Date(now.getTime() - i * 2 * 60 * 60 * 1000);
      data.push({
        timestamp: timestamp.toISOString(),
        model_name: models[Math.floor(Math.random() * models.length)],
        processing_time: Math.random() * 10 + 1, // 1-11 seconds
        tokens_processed: Math.floor(Math.random() * 1000 + 100),
        cache_hits: Math.floor(Math.random() * 50 + 20),
        cache_misses: Math.floor(Math.random() * 20 + 5),
        memory_usage_mb: Math.random() * 2000 + 1000, // 1-3 GB
        gpu_usage_percent: Math.random() * 80 + 10, // 10-90%
        gpu_memory_mb: Math.random() * 8000 + 2000, // 2-10 GB
        success: Math.random() > 0.1, // 90% success rate
        error_message: Math.random() > 0.9 ? 'Model timeout' : undefined
      });
    }
    return data;
  };

  const [sampleSystemStatus] = useState<SystemStatus>({
    system_health: {
      cpu_usage: 45.2,
      memory_usage: 62.8,
      disk_usage: 73.5,
      status: 'healthy'
    },
    ai_performance: {
      avg_processing_time: 3.2,
      success_rate: 0.94,
      status: 'healthy'
    },
    cache_performance: {
      hit_rate: 0.82,
      memory_usage_mb: 245.6,
      total_entries: 1247,
      status: 'healthy'
    },
    alerts: {
      critical: 0,
      warning: 2,
      total: 2
    },
    timestamp: new Date().toISOString()
  });

  const [sampleAlerts] = useState([
    {
      level: 'warning',
      type: 'memory',
      message: 'Memory usage is approaching threshold: 62.8%',
      timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString()
    },
    {
      level: 'warning',
      type: 'processing_time',
      message: 'Average processing time is high: 3.2s',
      timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString()
    }
  ]);

  useEffect(() => {
    setSystemMetrics(generateSampleSystemMetrics());
    setAiMetrics(generateSampleAIMetrics());
    setSystemStatus(sampleSystemStatus);
    setAlerts(sampleAlerts);
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    setSystemStatus(sampleSystemStatus);
    setIsRefreshing(false);
  };

  const handleMonitoringToggle = () => {
    setIsMonitoring(!isMonitoring);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'unhealthy': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon color="success" />;
      case 'degraded': return <WarningIcon color="warning" />;
      case 'unhealthy': return <ErrorIcon color="error" />;
      default: return <InfoIcon />;
    }
  };

  const getAlertIcon = (level: string) => {
    switch (level) {
      case 'critical': return <ErrorIcon color="error" />;
      case 'warning': return <WarningIcon color="warning" />;
      default: return <InfoIcon />;
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h4" component="h1">
            System Monitoring
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControlLabel
              control={
                <Switch
                  checked={isMonitoring}
                  onChange={handleMonitoringToggle}
                  color="primary"
                />
              }
              label="Live Monitoring"
            />
            <Button
              variant="outlined"
              onClick={handleRefresh}
              disabled={isRefreshing}
              startIcon={<RefreshIcon />}
            >
              {isRefreshing ? 'Refreshing...' : 'Refresh'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
            >
              Export Data
            </Button>
          </Box>
        </Box>
        <Typography variant="body1" color="text.secondary">
          Real-time monitoring of system performance and AI processing metrics.
        </Typography>
      </Box>

      {/* System Status Overview */}
      {systemStatus && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <SpeedIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">System Health</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  {getStatusIcon(systemStatus.system_health.status)}
                  <Typography variant="h6" sx={{ ml: 1, textTransform: 'capitalize' }}>
                    {systemStatus.system_health.status}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  CPU: {systemStatus.system_health.cpu_usage.toFixed(1)}% | 
                  Memory: {systemStatus.system_health.memory_usage.toFixed(1)}% | 
                  Disk: {systemStatus.system_health.disk_usage.toFixed(1)}%
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <PsychologyIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">AI Performance</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  {getStatusIcon(systemStatus.ai_performance.status)}
                  <Typography variant="h6" sx={{ ml: 1, textTransform: 'capitalize' }}>
                    {systemStatus.ai_performance.status}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Avg Time: {systemStatus.ai_performance.avg_processing_time.toFixed(1)}s | 
                  Success: {(systemStatus.ai_performance.success_rate * 100).toFixed(1)}%
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <MemoryIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">Cache Performance</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  {getStatusIcon(systemStatus.cache_performance.status)}
                  <Typography variant="h6" sx={{ ml: 1, textTransform: 'capitalize' }}>
                    {systemStatus.cache_performance.status}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Hit Rate: {(systemStatus.cache_performance.hit_rate * 100).toFixed(1)}% | 
                  Entries: {systemStatus.cache_performance.total_entries}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <WarningIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">Alerts</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Typography variant="h6" color="error">
                    {systemStatus.alerts.critical}
                  </Typography>
                  <Typography variant="body2" sx={{ ml: 1 }}>
                    Critical
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Warnings: {systemStatus.alerts.warning} | 
                  Total: {systemStatus.alerts.total}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* System Metrics Charts */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                CPU & Memory Usage (24h)
              </Typography>
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={systemMetrics}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="timestamp" 
                      tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                    />
                    <YAxis />
                    <RechartsTooltip 
                      labelFormatter={(value) => new Date(value).toLocaleString()}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="cpu_percent" 
                      stackId="1"
                      stroke="#8884d8" 
                      fill="#8884d8" 
                      name="CPU %"
                    />
                    <Area 
                      type="monotone" 
                      dataKey="memory_percent" 
                      stackId="2"
                      stroke="#82ca9d" 
                      fill="#82ca9d" 
                      name="Memory %"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                AI Processing Performance (24h)
              </Typography>
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={aiMetrics}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="timestamp" 
                      tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                    />
                    <YAxis />
                    <RechartsTooltip 
                      labelFormatter={(value) => new Date(value).toLocaleString()}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="processing_time" 
                      stroke="#8884d8" 
                      strokeWidth={2}
                      name="Processing Time (s)"
                    />
                    <Line 
                      type="monotone" 
                      dataKey="memory_usage_mb" 
                      stroke="#82ca9d" 
                      strokeWidth={2}
                      name="Memory Usage (MB)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Alerts */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Alerts
              </Typography>
              {alerts.length > 0 ? (
                <List>
                  {alerts.map((alert, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        {getAlertIcon(alert.level)}
                      </ListItemIcon>
                      <ListItemText
                        primary={alert.message}
                        secondary={
                          <Box>
                            <Typography variant="caption" color="text.secondary">
                              {alert.type.toUpperCase()} • {formatTimestamp(alert.timestamp)}
                            </Typography>
                          </Box>
                        }
                      />
                      <Chip
                        label={alert.level.toUpperCase()}
                        color={alert.level === 'critical' ? 'error' : 'warning'}
                        size="small"
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <CheckCircleIcon color="success" sx={{ fontSize: 48, mb: 2 }} />
                  <Typography variant="body1" color="text.secondary">
                    No recent alerts
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Resources
              </Typography>
              
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">CPU Usage</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {systemStatus?.system_health.cpu_usage.toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={systemStatus?.system_health.cpu_usage || 0}
                  color={systemStatus?.system_health.cpu_usage && systemStatus.system_health.cpu_usage > 80 ? 'error' : 'primary'}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>

              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Memory Usage</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {systemStatus?.system_health.memory_usage.toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={systemStatus?.system_health.memory_usage || 0}
                  color={systemStatus?.system_health.memory_usage && systemStatus.system_health.memory_usage > 80 ? 'error' : 'primary'}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>

              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Disk Usage</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {systemStatus?.system_health.disk_usage.toFixed(1)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={systemStatus?.system_health.disk_usage || 0}
                  color={systemStatus?.system_health.disk_usage && systemStatus.system_health.disk_usage > 90 ? 'error' : 'primary'}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Cache Performance
                </Typography>
                <Typography variant="h6" color="primary">
                  {(systemStatus?.cache_performance.hit_rate || 0) * 100}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Hit Rate
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SystemMonitoring;


