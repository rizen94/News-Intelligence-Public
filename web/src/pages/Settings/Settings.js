import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
} from '@mui/material';
import React from 'react';
// import { useNewsSystem } from '../../contexts/NewsSystemContext';

export default function Settings() {
  // const { state, actions } = useNewsSystem();
  // const { ui } = state;

  // Mock data for demonstration
  const ui = {
    language: 'en',
    notifications: true,
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 3 }}>
        Settings
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                User Interface
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Interface customization options will be available here
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Language: {ui.language}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Configuration
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                System settings and configuration options
              </Typography>
              <Button variant="outlined" fullWidth>
                Export Configuration
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
