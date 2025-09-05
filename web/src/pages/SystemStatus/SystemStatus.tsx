import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  LinearProgress,
  Chip,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Divider,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Storage as StorageIcon,
  Memory as MemoryIcon,
  Speed as SpeedIcon,
  NetworkCheck as NetworkIcon,
} from '@mui/icons-material';

// Import services
import { dashboardService } from '../../services/dashboardService';

interface SystemStatus {
  overall: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  uptime_seconds: number;
  services: {
    [key: string]: {
      status: 'healthy' | 'unhealthy';
      message: string;
      last_check: string;
      response_time_ms: number;
      [key: string]: any;
    };
  };
}

const SystemStatus: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSystemStatus = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await dashboardService.getSystemStatus();
      
      if (response.success) {
        setStatus(response.data);
      } else {
        setError('Failed to load system status');
      }
    } catch (err) {
      setError('Failed to load system status');
      console.error('System status error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSystemStatus();
    // Refresh every 30 seconds
    const interval = setInterval(fetchSystemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon color="success" />;
      case 'unhealthy':
        return <ErrorIcon color="error" />;
      case 'degraded':
        return <WarningIcon color="warning" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'unhealthy':
        return 'error';
      case 'degraded':
        return 'warning';
      default:
        return 'info';
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) {
      return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  const formatResponseTime = (ms: number) => {
    if (ms < 1000) {
      return `${ms.toFixed(1)}ms`;
    } else {
      return `${(ms / 1000).toFixed(2)}s`;
    }
  };

  if (loading && !status) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={fetchSystemStatus}>
            Retry
          </Button>
        }>
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          System Status
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={fetchSystemStatus}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Overall Status */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" component="h2">
              Overall System Status
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {getStatusIcon(status?.overall || 'unknown')}
              <Chip
                label={status?.overall?.toUpperCase() || 'UNKNOWN'}
                color={getStatusColor(status?.overall || 'unknown')}
                variant="filled"
              />
            </Box>
          </Box>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="textSecondary">
                Version
              </Typography>
              <Typography variant="h6">
                {status?.version || 'Unknown'}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="textSecondary">
                Uptime
              </Typography>
              <Typography variant="h6">
                {status?.uptime_seconds ? formatUptime(status.uptime_seconds) : 'Unknown'}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="textSecondary">
                Last Check
              </Typography>
              <Typography variant="h6">
                {status?.timestamp ? new Date(status.timestamp).toLocaleTimeString() : 'Unknown'}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="textSecondary">
                Services
              </Typography>
              <Typography variant="h6">
                {status?.services ? Object.keys(status.services).length : 0}
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Service Status */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
            Service Status
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Service</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Response Time</TableCell>
                  <TableCell>Last Check</TableCell>
                  <TableCell>Message</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {status?.services && Object.entries(status.services).map(([serviceName, service]) => (
                  <TableRow key={serviceName}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {serviceName === 'database' && <StorageIcon />}
                        {serviceName === 'ml_pipeline' && <MemoryIcon />}
                        {serviceName === 'monitoring' && <SpeedIcon />}
                        {serviceName === 'rss_collection' && <NetworkIcon />}
                        <Typography variant="subtitle2" sx={{ textTransform: 'capitalize' }}>
                          {serviceName.replace('_', ' ')}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getStatusIcon(service.status)}
                        <Chip
                          label={service.status.toUpperCase()}
                          color={getStatusColor(service.status)}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {formatResponseTime(service.response_time_ms)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="textSecondary">
                        {new Date(service.last_check).toLocaleTimeString()}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="textSecondary">
                        {service.message}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* System Metrics */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
                System Health Overview
              </Typography>
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Healthy Services</Typography>
                  <Typography variant="body2">
                    {status?.services ? Object.values(status.services).filter(s => s.status === 'healthy').length : 0} / {status?.services ? Object.keys(status.services).length : 0}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={status?.services ? (Object.values(status.services).filter(s => s.status === 'healthy').length / Object.keys(status.services).length) * 100 : 0}
                  color="success"
                />
              </Box>
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Average Response Time</Typography>
                  <Typography variant="body2">
                    {status?.services ? formatResponseTime(Object.values(status.services).reduce((acc, s) => acc + s.response_time_ms, 0) / Object.values(status.services).length) : 'N/A'}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, (status?.services ? Object.values(status.services).reduce((acc, s) => acc + s.response_time_ms, 0) / Object.values(status.services).length : 0) / 10)}
                  color="primary"
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  onClick={fetchSystemStatus}
                  disabled={loading}
                >
                  Refresh Status
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<StorageIcon />}
                  disabled
                >
                  Database Maintenance
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<MemoryIcon />}
                  disabled
                >
                  ML Pipeline Status
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<NetworkIcon />}
                  disabled
                >
                  Test RSS Feeds
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Auto-refresh indicator */}
      <Box sx={{ mt: 3, textAlign: 'center' }}>
        <Typography variant="caption" color="textSecondary">
          Status updates automatically every 30 seconds
        </Typography>
      </Box>
    </Box>
  );
};

export default SystemStatus;

