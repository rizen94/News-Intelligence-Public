import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  Backdrop,
  LinearProgress
} from '@mui/material';

const LoadingOverlay = ({ 
  loading, 
  message = 'Loading...', 
  progress = null,
  overlay = true 
}) => {
  if (!loading) return null;

  if (overlay) {
    return (
      <Backdrop
        sx={{ 
          color: '#fff', 
          zIndex: (theme) => theme.zIndex.drawer + 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 2
        }}
        open={loading}
      >
        <CircularProgress color="inherit" size={60} />
        <Typography variant="h6">{message}</Typography>
        {progress !== null && (
          <Box sx={{ width: 300 }}>
            <LinearProgress 
              variant="determinate" 
              value={progress} 
              sx={{ mb: 1 }}
            />
            <Typography variant="body2" textAlign="center">
              {Math.round(progress)}%
            </Typography>
          </Box>
        )}
      </Backdrop>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 200,
        gap: 2
      }}
    >
      <CircularProgress />
      <Typography variant="body1" color="text.secondary">
        {message}
      </Typography>
      {progress !== null && (
        <Box sx={{ width: 200 }}>
          <LinearProgress 
            variant="determinate" 
            value={progress} 
            sx={{ mb: 1 }}
          />
          <Typography variant="body2" textAlign="center">
            {Math.round(progress)}%
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default LoadingOverlay;
