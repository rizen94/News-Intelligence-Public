import React from 'react';
import { Box, Typography, Card, CardContent, Alert } from '@mui/material';

const AIAnalysis: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        AI Analysis
      </Typography>
      <Card>
        <CardContent>
          <Alert severity="info">
            AI Analysis feature is coming soon. This will integrate with the ai_analysis table.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AIAnalysis;
