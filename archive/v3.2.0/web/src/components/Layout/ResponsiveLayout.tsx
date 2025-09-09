import React from 'react';
import { Box, Container, useTheme, useMediaQuery } from '@mui/material';
import ResponsiveNavigation from './ResponsiveNavigation';

interface ResponsiveLayoutProps {
  children: React.ReactNode;
  maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | false;
  disableGutters?: boolean;
  sx?: any;
}

const ResponsiveLayout: React.FC<ResponsiveLayoutProps> = ({
  children,
  maxWidth = 'lg',
  disableGutters = false,
  sx = {}
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <ResponsiveNavigation />
      
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: theme.palette.background.default,
          minHeight: 'calc(100vh - 64px)', // Subtract AppBar height
          ...sx
        }}
      >
        <Container
          maxWidth={maxWidth}
          disableGutters={disableGutters}
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            py: isMobile ? 2 : 3,
            px: isMobile ? 1 : 2,
          }}
        >
          {children}
        </Container>
      </Box>
    </Box>
  );
};

export default ResponsiveLayout;

