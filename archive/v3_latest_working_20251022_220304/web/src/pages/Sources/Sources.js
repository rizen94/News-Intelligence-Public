import {
  RssFeed as Source,
  CheckCircle as HealthyIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  LinearProgress,
  Alert,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import { useNewsSystem } from '../../contexts/NewsSystemContext';

export default function Sources() {
  const { state, actions } = useNewsSystem();
  const { sources } = state;

  useEffect(() => {
    actions.fetchSources();
  }, []);

  const getHealthIcon = (health) => {
    switch (health) {
    case 'excellent': return <HealthyIcon color="success" />;
    case 'good': return <HealthyIcon color="success" />;
    case 'warning': return <WarningIcon color="warning" />;
    case 'error': return <ErrorIcon color="error" />;
    default: return <WarningIcon color="warning" />;
    }
  };

  const getHealthColor = (health) => {
    switch (health) {
    case 'excellent': return 'success';
    case 'good': return 'success';
    case 'warning': return 'warning';
    case 'error': return 'error';
    default: return 'default';
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 3 }}>
        News Sources
      </Typography>

      <Grid container spacing={3}>
        {sources.list.map((source) => (
          <Grid item xs={12} md={6} lg={4} key={source.id}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Typography variant="h6" component="div">
                    {source.name}
                  </Typography>
                  {getHealthIcon(source.health)}
                </Box>

                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {source.url}
                </Typography>

                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip
                    label={source.category}
                    size="small"
                    variant="outlined"
                  />
                  <Chip
                    label={source.health}
                    color={getHealthColor(source.health)}
                    size="small"
                  />
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Articles: {source.articleCount} | Success Rate: {source.successRate}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Last Fetch: {new Date(source.lastFetched).toLocaleString()}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
