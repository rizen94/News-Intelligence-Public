import React from 'react';
import { Box, Typography, Card, CardContent, Alert } from '@mui/material';

const Settings: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Settings
      </Typography>
      <Card>
        <CardContent>
          <Alert severity="info">
            Settings feature is coming soon. This will allow configuration of the system.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Settings;
