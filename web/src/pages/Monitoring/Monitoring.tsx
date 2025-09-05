import React from 'react';
import { Box, Typography, Card, CardContent, Alert } from '@mui/material';

const Monitoring: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Monitoring
      </Typography>
      <Card>
        <CardContent>
          <Alert severity="info">
            Monitoring feature is coming soon. This will integrate with the metrics tables.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Monitoring;
