import React from 'react';
import {
  Box,
  Skeleton,
  useTheme,
  useMediaQuery,
  Typography,
  CircularProgress,
  LinearProgress
} from '@mui/material';

interface ResponsiveLoadingProps {
  type?: 'skeleton' | 'spinner' | 'linear' | 'dots';
  message?: string;
  height?: number | string;
  count?: number;
  variant?: 'text' | 'rectangular' | 'circular';
  animation?: 'pulse' | 'wave' | false;
}

const ResponsiveLoading: React.FC<ResponsiveLoadingProps> = ({
  type = 'skeleton',
  message,
  height = 200,
  count = 3,
  variant = 'rectangular',
  animation = 'wave'
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const renderSkeleton = () => (
    <Box sx={{ width: '100%' }}>
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton
          key={index}
          variant={variant}
          height={height}
          animation={animation}
          sx={{
            mb: 2,
            borderRadius: 1,
            ...(isMobile && {
              height: typeof height === 'number' ? height * 0.8 : height,
            }),
          }}
        />
      ))}
    </Box>
  );

  const renderSpinner = () => (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: height,
        gap: 2,
      }}
    >
      <CircularProgress size={isMobile ? 32 : 40} />
      {message && (
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      )}
    </Box>
  );

  const renderLinear = () => (
    <Box sx={{ width: '100%' }}>
      <LinearProgress />
      {message && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 1, textAlign: 'center' }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );

  const renderDots = () => (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: height,
        gap: 1,
      }}
    >
      {Array.from({ length: 3 }).map((_, index) => (
        <Box
          key={index}
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: theme.palette.primary.main,
            animation: 'pulse 1.4s ease-in-out infinite both',
            animationDelay: `${index * 0.16}s`,
            '@keyframes pulse': {
              '0%, 80%, 100%': {
                transform: 'scale(0)',
                opacity: 0.5,
              },
              '40%': {
                transform: 'scale(1)',
                opacity: 1,
              },
            },
          }}
        />
      ))}
      {message && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ ml: 2 }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );

  switch (type) {
    case 'spinner':
      return renderSpinner();
    case 'linear':
      return renderLinear();
    case 'dots':
      return renderDots();
    default:
      return renderSkeleton();
  }
};

export default ResponsiveLoading;

