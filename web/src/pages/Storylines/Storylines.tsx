import React from 'react';
import { Box, Typography, Card, CardContent, Alert } from '@mui/material';

const Storylines: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Storylines
      </Typography>
      <Card>
        <CardContent>
          <Alert severity="info">
            Storylines feature is coming soon. This will integrate with the story_timelines and story_consolidations tables.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Storylines;
