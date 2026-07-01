import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';

export function LoadingState({ message = 'Loading…' }: { message?: string }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6, gap: 2 }}>
      <CircularProgress size={32} />
      <Typography variant='body2' color='text.secondary'>
        {message}
      </Typography>
    </Box>
  );
}
