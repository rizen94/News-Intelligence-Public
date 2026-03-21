/**
 * Standardized Loading State Component
 * Consistent loading indicators across all pages
 */

import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  LinearProgress,
} from '@mui/material';

interface LoadingStateProps {
  message?: string;
  fullScreen?: boolean;
  variant?: 'circular' | 'linear';
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading...',
  fullScreen = false,
  variant = 'circular',
}) => {
  const content = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        p: 3,
        ...(fullScreen && {
          minHeight: '400px',
        }),
      }}
    >
      {variant === 'circular' ? (
        <CircularProgress />
      ) : (
        <Box sx={{ width: '100%', maxWidth: 400 }}>
          <LinearProgress />
        </Box>
      )}
      {message && (
        <Typography variant='body2' color='text.secondary'>
          {message}
        </Typography>
      )}
    </Box>
  );

  if (fullScreen) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
        }}
      >
        {content}
      </Box>
    );
  }

  return content;
};

export default LoadingState;
