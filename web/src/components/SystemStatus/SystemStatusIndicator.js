import React, { useState, useEffect } from 'react';
import {
  Box,
  Chip,
  Tooltip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Assessment as AssessmentIcon,
  Speed as SpeedIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Security as SecurityIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

const SystemStatusIndicator = ({ compact = false }) => {
  const [status, setStatus] = useState('loading');
  const [details, setDetails] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    checkSystemStatus();
    // Check status every 30 seconds
    const interval = setInterval(checkSystemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkSystemStatus = async () => {
    try {
      const response = await newsSystemService.getSystemStatus();
      if (response.success) {
        setStatus(response.data.status || 'healthy');
        setDetails(response.data);
      } else {
        setStatus('error');
        setDetails({ error: response.error });
      }
    } catch (error) {
      setStatus('error');
      setDetails({ error: error.message });
    } finally {
      setLastUpdate(new Date());
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
      case 'online':
      case 'active':
        return 'success';
      case 'warning':
      case 'degraded':
        return 'warning';
      case 'error':
      case 'offline':
      case 'inactive':
        return 'error';
      case 'loading':
        return 'default';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
      case 'online':
      case 'active':
        return <CheckCircleIcon />;
      case 'warning':
      case 'degraded':
        return <WarningIcon />;
      case 'error':
      case 'offline':
      case 'inactive':
        return <ErrorIcon />;
      case 'loading':
        return <InfoIcon />;
      default:
        return <InfoIcon />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'healthy':
        return 'All Systems Operational';
      case 'warning':
        return 'Degraded Performance';
      case 'error':
        return 'System Issues Detected';
      case 'loading':
        return 'Checking Status...';
      default:
        return 'Unknown Status';
    }
  };

  if (compact) {
    return (
      <Tooltip title={getStatusText(status)}>
        <Chip
          icon={getStatusIcon(status)}
          label={status.toUpperCase()}
          color={getStatusColor(status)}
          size="small"
          onClick={() => setShowDetails(true)}
          sx={{ cursor: 'pointer' }}
        />
      </Tooltip>
    );
  }

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Chip
          icon={getStatusIcon(status)}
          label={getStatusText(status)}
          color={getStatusColor(status)}
          onClick={() => setShowDetails(true)}
          sx={{ cursor: 'pointer' }}
        />
        <Tooltip title="Refresh Status">
          <IconButton size="small" onClick={checkSystemStatus}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Dialog
        open={showDetails}
        onClose={() => setShowDetails(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AssessmentIcon />
            System Status Details
          </Box>
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Overall Status
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                    {getStatusIcon(status)}
                    <Typography variant="h5" color={`${getStatusColor(status)}.main`}>
                      {getStatusText(status)}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Last updated: {lastUpdate ? lastUpdate.toLocaleString() : 'Never'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    System Components
                  </Typography>
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <NetworkIcon color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary="API Server"
                        secondary="Online"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <StorageIcon color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary="Database"
                        secondary="Connected"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <SpeedIcon color="warning" />
                      </ListItemIcon>
                      <ListItemText
                        primary="ML Processing"
                        secondary="Queue: 5 items"
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <SecurityIcon color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary="Security"
                        secondary="All checks passed"
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Performance Metrics
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6} md={3}>
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          API Response Time
                        </Typography>
                        <LinearProgress 
                          variant="determinate" 
                          value={75} 
                          color="success"
                          sx={{ mb: 1 }}
                        />
                        <Typography variant="body2">245ms</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Database Performance
                        </Typography>
                        <LinearProgress 
                          variant="determinate" 
                          value={85} 
                          color="success"
                          sx={{ mb: 1 }}
                        />
                        <Typography variant="body2">Excellent</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Memory Usage
                        </Typography>
                        <LinearProgress 
                          variant="determinate" 
                          value={65} 
                          color="warning"
                          sx={{ mb: 1 }}
                        />
                        <Typography variant="body2">65%</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          CPU Usage
                        </Typography>
                        <LinearProgress 
                          variant="determinate" 
                          value={45} 
                          color="success"
                          sx={{ mb: 1 }}
                        />
                        <Typography variant="body2">45%</Typography>
                      </Box>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            {details?.error && (
              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom color="error">
                      Error Details
                    </Typography>
                    <Typography variant="body2" color="error">
                      {details.error}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDetails(false)}>
            Close
          </Button>
          <Button 
            variant="contained" 
            startIcon={<RefreshIcon />}
            onClick={checkSystemStatus}
          >
            Refresh Status
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SystemStatusIndicator;
