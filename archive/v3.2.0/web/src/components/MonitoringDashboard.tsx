import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Paper,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  Tabs,
  Tab,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import {
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  Article as ArticleIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon
} from '@mui/icons-material';
import { format, subDays, parseISO } from 'date-fns';

interface ChartData {
  timestamps: string[];
  [key: string]: any;
}

interface MonitoringData {
  system_resources: ChartData;
  article_processing: ChartData;
  article_volume: ChartData;
  database_performance: ChartData;
  last_updated: string;
}

const MonitoringDashboard: React.FC = () => {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const fetchData = async () => {
    try {
      setRefreshing(true);
      const response = await fetch('http://localhost:8000/api/metrics/charts/summary');
      const result = await response.json();
      
      if (result.success) {
        setData(result.data);
        setError(null);
      } else {
        setError(result.message || 'Failed to fetch monitoring data');
      }
    } catch (err) {
      setError('Network error: ' + (err as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTimestamp = (timestamp: string) => {
    try {
      return format(parseISO(timestamp), 'MMM dd HH:mm');
    } catch {
      return timestamp;
    }
  };

  const getSystemHealthColor = () => {
    if (!data?.system_resources) return 'default';
    const latest = data.system_resources.cpu_percent?.slice(-1)[0] || 0;
    if (latest > 80) return 'error';
    if (latest > 60) return 'warning';
    return 'success';
  };

  const getProcessingHealthColor = () => {
    if (!data?.article_processing) return 'default';
    const latest = data.article_processing.processing_success_rate?.slice(-1)[0] || 0;
    if (latest < 80) return 'error';
    if (latest < 90) return 'warning';
    return 'success';
  };

  const renderSystemResourcesChart = () => {
    if (!data?.system_resources) return null;

    const chartData = data.system_resources.timestamps.map((timestamp, index) => ({
      time: formatTimestamp(timestamp),
      cpu: data.system_resources.cpu_percent[index] || 0,
      memory: data.system_resources.memory_percent[index] || 0,
      disk: data.system_resources.disk_percent[index] || 0,
      load: data.system_resources.load_avg_1m[index] || 0
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <RechartsTooltip />
          <Line type="monotone" dataKey="cpu" stroke="#8884d8" strokeWidth={2} name="CPU %" />
          <Line type="monotone" dataKey="memory" stroke="#82ca9d" strokeWidth={2} name="Memory %" />
          <Line type="monotone" dataKey="disk" stroke="#ffc658" strokeWidth={2} name="Disk %" />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const renderArticleProcessingChart = () => {
    if (!data?.article_processing) return null;

    const chartData = data.article_processing.timestamps.map((timestamp, index) => ({
      time: formatTimestamp(timestamp),
      processed: data.article_processing.articles_processed[index] || 0,
      failed: data.article_processing.articles_failed[index] || 0,
      queue: data.article_processing.queue_size[index] || 0,
      workers: data.article_processing.active_workers[index] || 0
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <RechartsTooltip />
          <Area type="monotone" dataKey="processed" stackId="1" stroke="#8884d8" fill="#8884d8" name="Processed" />
          <Area type="monotone" dataKey="failed" stackId="1" stroke="#ff7300" fill="#ff7300" name="Failed" />
        </AreaChart>
      </ResponsiveContainer>
    );
  };

  const renderArticleVolumeChart = () => {
    if (!data?.article_volume) return null;

    const chartData = data.article_volume.timestamps.map((timestamp, index) => ({
      time: formatTimestamp(timestamp),
      total: data.article_volume.total_articles[index] || 0,
      hourly: data.article_volume.new_articles_last_hour[index] || 0,
      daily: data.article_volume.new_articles_last_day[index] || 0
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <RechartsTooltip />
          <Bar dataKey="hourly" fill="#8884d8" name="New Articles (Hour)" />
          <Bar dataKey="daily" fill="#82ca9d" name="New Articles (Day)" />
        </BarChart>
      </ResponsiveContainer>
    );
  };

  const renderDatabasePerformanceChart = () => {
    if (!data?.database_performance) return null;

    const chartData = data.database_performance.timestamps.map((timestamp, index) => ({
      time: formatTimestamp(timestamp),
      connections: data.database_performance.connection_count[index] || 0,
      active_queries: data.database_performance.active_queries[index] || 0,
      slow_queries: data.database_performance.slow_queries[index] || 0,
      size_mb: data.database_performance.database_size_mb[index] || 0
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <RechartsTooltip />
          <Line type="monotone" dataKey="connections" stroke="#8884d8" strokeWidth={2} name="Connections" />
          <Line type="monotone" dataKey="active_queries" stroke="#82ca9d" strokeWidth={2} name="Active Queries" />
          <Line type="monotone" dataKey="slow_queries" stroke="#ff7300" strokeWidth={2} name="Slow Queries" />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const getLatestValue = (values: number[]) => {
    return values?.slice(-1)[0] || 0;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <IconButton color="inherit" size="small" onClick={fetchData}>
          <RefreshIcon />
        </IconButton>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          System Monitoring Dashboard
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            icon={<CheckCircleIcon />}
            label="Last 7 Days"
            color="primary"
            variant="outlined"
          />
          <Tooltip title="Refresh Data">
            <IconButton onClick={fetchData} disabled={refreshing}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Key Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <MemoryIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">System Health</Typography>
              </Box>
              <Chip
                label={getSystemHealthColor() === 'success' ? 'Healthy' : 'Warning'}
                color={getSystemHealthColor()}
                size="small"
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                CPU: {getLatestValue(data?.system_resources?.cpu_percent || [])}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ArticleIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Processing</Typography>
              </Box>
              <Chip
                label={getProcessingHealthColor() === 'success' ? 'Active' : 'Issues'}
                color={getProcessingHealthColor()}
                size="small"
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Queue: {getLatestValue(data?.article_processing?.queue_size || [])}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUpIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Articles</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {getLatestValue(data?.article_volume?.total_articles || [])}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Articles
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <SpeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Performance</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {getLatestValue(data?.article_processing?.avg_processing_time_ms || [])}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Avg Processing Time
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts */}
      <Paper sx={{ p: 3 }}>
        <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)} sx={{ mb: 3 }}>
          <Tab label="System Resources" />
          <Tab label="Article Processing" />
          <Tab label="Article Volume" />
          <Tab label="Database Performance" />
        </Tabs>

        {activeTab === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              System Resources (CPU, Memory, Disk)
            </Typography>
            {renderSystemResourcesChart()}
          </Box>
        )}

        {activeTab === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Article Processing (Processed vs Failed)
            </Typography>
            {renderArticleProcessingChart()}
          </Box>
        )}

        {activeTab === 2 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Article Volume (New Articles Over Time)
            </Typography>
            {renderArticleVolumeChart()}
          </Box>
        )}

        {activeTab === 3 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Database Performance (Connections, Queries)
            </Typography>
            {renderDatabasePerformanceChart()}
          </Box>
        )}
      </Paper>

      {refreshing && (
        <Box sx={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999 }}>
          <LinearProgress />
        </Box>
      )}
    </Box>
  );
};

export default MonitoringDashboard;
