import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  LinearProgress,
} from '@mui/material';
import {
  Info as InfoIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useNewsSystem } from '../../contexts/NewsSystemContext';

export default function Monitoring() {
  const { state } = useNewsSystem();
  const { monitoring, systemStatus } = state;

  const getLogIcon = (level) => {
    switch (level) {
      case 'info': return <InfoIcon color="info" />;
      case 'warning': return <WarningIcon color="warning" />;
      case 'error': return <ErrorIcon color="error" />;
      case 'success': return <SuccessIcon color="success" />;
      default: return <InfoIcon color="info" />;
    }
  };

  const getLogColor = (level) => {
    switch (level) {
      case 'info': return 'info';
      case 'warning': return 'warning';
      case 'error': return 'error';
      case 'success': return 'success';
      default: return 'default';
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 3 }}>
        System Monitoring
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Status
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2">Status: {systemStatus.status}</Typography>
                <Typography variant="body2">Version: {systemStatus.version}</Typography>
                <Typography variant="body2">Uptime: {systemStatus.uptime}</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Logs
              </Typography>
              <List dense>
                {monitoring.logs.slice(-5).map((log, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      {getLogIcon(log.level)}
                    </ListItemIcon>
                    <ListItemText
                      primary={log.message}
                      secondary={new Date(log.timestamp).toLocaleString()}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Errors
              </Typography>
              <List dense>
                {monitoring.errors.slice(-10).map((error, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <ErrorIcon color="error" />
                    </ListItemIcon>
                    <ListItemText
                      primary={error.message}
                      secondary={error.error}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
