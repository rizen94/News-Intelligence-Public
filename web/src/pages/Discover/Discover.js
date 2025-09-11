import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';

const Discover = () => {
  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Discover
      </Typography>
      
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <SearchIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" color="text.secondary">
          Content Discovery
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Advanced search and discovery features coming soon...
        </Typography>
      </Paper>
    </Box>
  );
};

export default Discover;