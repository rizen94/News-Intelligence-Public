import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  Divider,
} from '@mui/material';
import { useNewsSystem } from '../../contexts/NewsSystemContext';

export default function Settings() {
  const { state, actions } = useNewsSystem();
  const { ui } = state;

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
              <FormControlLabel
                control={
                  <Switch
                    checked={ui.theme === 'dark'}
                    onChange={() => actions.setTheme(ui.theme === 'light' ? 'dark' : 'light')}
                  />
                }
                label="Dark Mode"
              />
              <Divider sx={{ my: 2 }} />
              <Typography variant="body2" color="text.secondary">
                Customize the appearance of the application
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
