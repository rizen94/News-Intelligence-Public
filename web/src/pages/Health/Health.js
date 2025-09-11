import React from 'react';
import { Box, Typography, Paper, Chip, Grid, Card, CardContent } from '@mui/material';
import { HealthAndSafety as HealthIcon, CheckCircle as CheckCircleIcon, Error as ErrorIcon } from '@mui/icons-material';

const Health = ({ systemHealth }) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon color="success" />;
      default:
        return <ErrorIcon color="error" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'success';
      default:
        return 'error';
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        System Health
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Overall Status
              </Typography>
              {systemHealth ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  {getStatusIcon(systemHealth.data?.status)}
                  <Chip
                    label={systemHealth.data?.status?.toUpperCase() || 'UNKNOWN'}
                    color={getStatusColor(systemHealth.data?.status)}
                    variant="outlined"
                  />
                  <Typography variant="body2" color="text.secondary">
                    {systemHealth.message || 'System operational'}
                  </Typography>
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Loading system status...
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Information
              </Typography>
              <Typography variant="body2" color="text.secondary">
                News Intelligence System v3.3.0
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Schema-driven architecture
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Unified production system
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Health;
