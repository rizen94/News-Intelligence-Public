import React from 'react';
import { Grid, GridProps, useTheme, useMediaQuery } from '@mui/material';

interface ResponsiveGridProps extends Omit<GridProps, 'container' | 'item'> {
  children: React.ReactNode;
  spacing?: number;
  xs?: number;
  sm?: number;
  md?: number;
  lg?: number;
  xl?: number;
  autoFit?: boolean;
  minWidth?: number;
}

const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  spacing = 2,
  xs = 12,
  sm = 6,
  md = 4,
  lg = 3,
  xl = 2,
  autoFit = false,
  minWidth = 300,
  sx = {},
  ...props
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));
  const isDesktop = useMediaQuery(theme.breakpoints.down('lg'));

  if (autoFit) {
    return (
      <Grid
        container
        spacing={spacing}
        sx={{
          display: 'grid',
          gridTemplateColumns: `repeat(auto-fit, minmax(${minWidth}px, 1fr))`,
          gap: theme.spacing(spacing),
          ...sx
        }}
        {...props}
      >
        {React.Children.map(children, (child, index) => (
          <Grid item key={index} sx={{ minWidth: 0 }}>
            {child}
          </Grid>
        ))}
      </Grid>
    );
  }

  return (
    <Grid
      container
      spacing={spacing}
      sx={sx}
      {...props}
    >
      {React.Children.map(children, (child, index) => (
        <Grid
          item
          key={index}
          xs={xs}
          sm={sm}
          md={md}
          lg={lg}
          xl={xl}
        >
          {child}
        </Grid>
      ))}
    </Grid>
  );
};

// Specialized grid components for common layouts
export const DashboardGrid: React.FC<ResponsiveGridProps> = (props) => (
  <ResponsiveGrid
    xs={12}
    sm={6}
    md={4}
    lg={3}
    xl={2}
    spacing={2}
    {...props}
  />
);

export const ArticleGrid: React.FC<ResponsiveGridProps> = (props) => (
  <ResponsiveGrid
    xs={12}
    sm={6}
    md={4}
    lg={4}
    xl={3}
    spacing={3}
    {...props}
  />
);

export const CardGrid: React.FC<ResponsiveGridProps> = (props) => (
  <ResponsiveGrid
    xs={12}
    sm={12}
    md={6}
    lg={6}
    xl={4}
    spacing={2}
    {...props}
  />
);

export const StatsGrid: React.FC<ResponsiveGridProps> = (props) => (
  <ResponsiveGrid
    xs={6}
    sm={3}
    md={3}
    lg={2}
    xl={2}
    spacing={1}
    {...props}
  />
);

export default ResponsiveGrid;

