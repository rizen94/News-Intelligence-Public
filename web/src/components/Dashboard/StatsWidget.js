// News Intelligence System v3.1.0 - Stats Widget Component
// Reusable statistics widget for dashboard

import React from 'react';
import { Box, Typography, LinearProgress, Chip, IconButton, Tooltip } from '@mui/material';
import { TrendingUp, TrendingDown, Refresh, Info } from '@mui/icons-material';

const StatsWidget = ({ 
  title, 
  value, 
  subtitle, 
  trend, 
  trendValue, 
  color = 'primary', 
  icon, 
  loading = false,
  onRefresh,
  tooltip
}) => {
  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp sx={{ fontSize: 16, color: 'success.main' }} />;
    if (trend === 'down') return <TrendingDown sx={{ fontSize: 16, color: 'error.main' }} />;
    return null;
  };

  const getTrendColor = () => {
    if (trend === 'up') return 'success.main';
    if (trend === 'down') return 'error.main';
    return 'text.secondary';
  };

  return (
    <Box sx={{ 
      p: 3, 
      border: '1px solid #e0e0e0', 
      borderRadius: 2, 
      backgroundColor: 'white',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      height: '100%',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {icon}
          <Typography variant="h6" color="textSecondary">
            {title}
          </Typography>
          {tooltip && (
            <Tooltip title={tooltip}>
              <Info sx={{ fontSize: 16, color: 'text.secondary' }} />
            </Tooltip>
          )}
        </Box>
        {onRefresh && (
          <IconButton size="small" onClick={onRefresh} disabled={loading}>
            <Refresh />
          </IconButton>
        )}
      </Box>

      {/* Value */}
      <Typography variant="h3" component="div" sx={{ fontWeight: 600, mb: 1 }}>
        {loading ? '...' : value}
      </Typography>

      {/* Subtitle */}
      {subtitle && (
        <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
          {subtitle}
        </Typography>
      )}

      {/* Trend */}
      {trend && trendValue && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 'auto' }}>
          {getTrendIcon()}
          <Typography variant="body2" color={getTrendColor()}>
            {trendValue}% {trend === 'up' ? 'increase' : 'decrease'}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default StatsWidget;

