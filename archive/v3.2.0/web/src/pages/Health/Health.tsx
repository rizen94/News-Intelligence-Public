import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Chip,
  CircularProgress,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  HealthAndSafety as HealthIcon
} from '@mui/icons-material';
import { apiService } from '../../services/apiService';

interface HealthState {
  systemHealth: any;
  databaseHealth: any;
  readiness: any;
  liveness: any;
  loading: boolean;
  error: string | null;
}

const Health: React.FC = () => {
  const [state, setState] = useState<HealthState>({
    systemHealth: null,
    databaseHealth: null,
    readiness: null,
    liveness: null,
    loading: true,
    error: null
  });

  useEffect(() => {
    loadHealthData();
  }, []);

  const loadHealthData = async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      const [systemResponse, databaseResponse, readinessResponse, livenessResponse] = await Promise.all([
        apiService.getSystemHealth(),
        apiService.getDatabaseHealth(),
        apiService.getReadinessStatus(),
        apiService.getLivenessStatus()
      ]);

      setState(prev => ({
        ...prev,
        systemHealth: systemResponse.data,
        databaseHealth: databaseResponse.data,
        readiness: readinessResponse.data,
        liveness: livenessResponse.data,
        loading: false
      }));
    } catch (error) {
      console.error('Error loading health data:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load health data'
      }));
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckIcon color="success" />;
      case 'degraded':
        return <WarningIcon color="warning" />;
      case 'unhealthy':
        return <ErrorIcon color="error" />;
      default:
        return <HealthIcon color="default" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'degraded':
        return 'warning';
      case 'unhealthy':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          System Health
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={loadHealthData}
          disabled={state.loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Error Alert */}
      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {state.error}
        </Alert>
      )}

      {/* Loading Indicator */}
      {state.loading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Health Status Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <HealthIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">System Health</Typography>
              </Box>
              {state.systemHealth ? (
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    {getStatusIcon(state.systemHealth.status)}
                    <Chip
                      label={state.systemHealth.status}
                      color={getStatusColor(state.systemHealth.status)}
                    />
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Last checked: {formatTimestamp(state.systemHealth.timestamp)}
                  </Typography>
                </Box>
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <CheckIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Database Health</Typography>
              </Box>
              {state.databaseHealth ? (
                <Box>
                  <Chip
                    label={state.databaseHealth.status || 'Unknown'}
                    color={state.databaseHealth.status === 'healthy' ? 'success' : 'warning'}
                    sx={{ mb: 1 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    Connection: {state.databaseHealth.connection_status || 'Unknown'}
                  </Typography>
                </Box>
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <CheckIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Readiness</Typography>
              </Box>
              {state.readiness ? (
                <Chip
                  label={state.readiness.ready ? 'Ready' : 'Not Ready'}
                  color={state.readiness.ready ? 'success' : 'error'}
                />
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <HealthIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Liveness</Typography>
              </Box>
              {state.liveness ? (
                <Chip
                  label={state.liveness.live ? 'Live' : 'Not Live'}
                  color={state.liveness.live ? 'success' : 'error'}
                />
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Service Status Table */}
      {state.systemHealth?.services && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Service Status
            </Typography>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Service</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Details</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {Object.entries(state.systemHealth.services).map(([service, status]) => (
                    <TableRow key={service}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {service}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {getStatusIcon(status as string)}
                          <Chip
                            label={status as string}
                            color={getStatusColor(status as string)}
                            size="small"
                          />
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {state.systemHealth.details?.[service] || 'No details available'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default Health;
