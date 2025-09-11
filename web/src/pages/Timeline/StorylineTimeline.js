import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { Timeline as TimelineIcon } from '@mui/icons-material';

const StorylineTimeline = () => {
  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Storyline Timeline
      </Typography>
      
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <TimelineIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" color="text.secondary">
          Timeline View
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Interactive timeline visualization coming soon...
        </Typography>
      </Paper>
    </Box>
  );
};

export default StorylineTimeline;