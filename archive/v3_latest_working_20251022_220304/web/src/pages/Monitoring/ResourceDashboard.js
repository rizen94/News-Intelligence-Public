import {
  Memory,
  Storage,
  Speed,
  Timeline,
  Refresh,
  Warning,
  Error,
  Info,
} from '@mui/icons-material';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';

const ResourceDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(24);
  const [refreshInterval, setRefreshInterval] = useState(30);

  const fetchMetrics = async() => {
    try {
      const response = await fetch(`/api/metrics/history?hours=${timeRange}`);
      if (response.ok) {
        const data = await response.json();
        setMetrics(data.data);
      }
    } catch (error) {
      console.error('Error fetching metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [timeRange, refreshInterval]);

  const getSeverityColor = (value, threshold) => {
    if (value >= threshold) return 'error';
    if (value >= threshold * 0.8) return 'warning';
    return 'success';
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Resource Dashboard
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  if (!metrics) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Resource Dashboard
        </Typography>
        <Typography color="error">
          Failed to load metrics data
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">
          Resource Dashboard
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={timeRange}
              label="Time Range"
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <MenuItem value={1}>1 Hour</MenuItem>
              <MenuItem value={6}>6 Hours</MenuItem>
              <MenuItem value={24}>24 Hours</MenuItem>
              <MenuItem value={168}>1 Week</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Refresh</InputLabel>
            <Select
              value={refreshInterval}
              label="Refresh"
              onChange={(e) => setRefreshInterval(e.target.value)}
            >
              <MenuItem value={15}>15s</MenuItem>
              <MenuItem value={30}>30s</MenuItem>
              <MenuItem value={60}>1m</MenuItem>
              <MenuItem value={300}>5m</MenuItem>
            </Select>
          </FormControl>
          <Tooltip title="Refresh Now">
            <IconButton onClick={fetchMetrics}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* System Resources Overview */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Speed color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">CPU Usage</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {metrics.system?.avg_cpu_percent?.toFixed(1) || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Max: {metrics.system?.max_cpu_percent?.toFixed(1) || 0}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(metrics.system?.avg_cpu_percent || 0, 100)}
                color={getSeverityColor(metrics.system?.avg_cpu_percent || 0, 80)}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Memory color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Memory Usage</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {metrics.system?.avg_memory_percent?.toFixed(1) || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Max: {metrics.system?.max_memory_percent?.toFixed(1) || 0}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(metrics.system?.avg_memory_percent || 0, 100)}
                color={getSeverityColor(metrics.system?.avg_memory_percent || 0, 85)}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Storage color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">GPU Memory</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {formatBytes((metrics.system?.avg_gpu_memory_mb || 0) * 1024 * 1024)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Max: {formatBytes((metrics.system?.max_gpu_memory_mb || 0) * 1024 * 1024)}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min((metrics.system?.avg_gpu_memory_mb || 0) / 32607 * 100, 100)}
                color={getSeverityColor((metrics.system?.avg_gpu_memory_mb || 0) / 32607 * 100, 90)}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Timeline color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">GPU Utilization</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {metrics.system?.avg_gpu_utilization?.toFixed(1) || 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Max: {metrics.system?.max_gpu_utilization?.toFixed(1) || 0}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(metrics.system?.avg_gpu_utilization || 0, 100)}
                color={getSeverityColor(metrics.system?.avg_gpu_utilization || 0, 80)}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Application Activity */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Application Activity (Last {timeRange} hours)
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="h4" color="primary">
                    {metrics.application?.total_requests?.toLocaleString() || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Requests
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="h4" color="primary">
                    {metrics.application?.total_articles?.toLocaleString() || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Articles Processed
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="h4" color="primary">
                    {metrics.application?.total_ml_inferences?.toLocaleString() || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    ML Inferences
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="h4" color="primary">
                    {metrics.application?.total_db_queries?.toLocaleString() || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Database Queries
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Status
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Data Points Collected</Typography>
                  <Chip
                    label={metrics.system?.data_points || 0}
                    color="primary"
                    size="small"
                  />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Error Rate</Typography>
                  <Chip
                    label={`${metrics.application?.total_errors || 0} errors`}
                    color={metrics.application?.total_errors > 0 ? 'error' : 'success'}
                    size="small"
                  />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Monitoring Status</Typography>
                  <Chip
                    label="Active"
                    color="success"
                    size="small"
                    icon={<Info />}
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Performance Summary */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Performance Summary
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            System performance metrics collected over the last {timeRange} hours.
            Data is automatically collected every minute and stored for historical analysis.
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Chip
              icon={<Speed />}
              label={`CPU: ${metrics.system?.avg_cpu_percent?.toFixed(1) || 0}% avg`}
              color={getSeverityColor(metrics.system?.avg_cpu_percent || 0, 80)}
            />
            <Chip
              icon={<Memory />}
              label={`Memory: ${metrics.system?.avg_memory_percent?.toFixed(1) || 0}% avg`}
              color={getSeverityColor(metrics.system?.avg_memory_percent || 0, 85)}
            />
            <Chip
              icon={<Storage />}
              label={`GPU: ${metrics.system?.avg_gpu_utilization?.toFixed(1) || 0}% avg`}
              color={getSeverityColor(metrics.system?.avg_gpu_utilization || 0, 80)}
            />
            <Chip
              icon={<Timeline />}
              label={`Data Points: ${metrics.system?.data_points || 0}`}
              color="primary"
            />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default ResourceDashboard;
