// News Intelligence System v3.1.0 - RSS Feed Status Indicator
// Visual status indicator for RSS feeds

import React from 'react';
import { Box, Chip, Tooltip, IconButton, LinearProgress, Typography } from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  Pause as PauseIcon,
  PlayArrow as PlayIcon
} from '@mui/icons-material';

const FeedStatusIndicator = ({ 
  feed, 
  onRefresh, 
  onToggle, 
  onTest,
  loading = false 
}) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
      case 'active':
        return 'success';
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      case 'inactive':
        return 'default';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
      case 'active':
        return <CheckIcon sx={{ fontSize: 16 }} />;
      case 'error':
        return <ErrorIcon sx={{ fontSize: 16 }} />;
      case 'warning':
        return <WarningIcon sx={{ fontSize: 16 }} />;
      default:
        return <PauseIcon sx={{ fontSize: 16 }} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'healthy':
        return 'Healthy';
      case 'active':
        return 'Active';
      case 'error':
        return 'Error';
      case 'warning':
        return 'Warning';
      case 'inactive':
        return 'Inactive';
      default:
        return 'Unknown';
    }
  };

  const getLastCheckText = (lastChecked) => {
    if (!lastChecked) return 'Never checked';
    
    const now = new Date();
    const lastCheck = new Date(lastChecked);
    const diff = now - lastCheck;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 60) {
      return `Checked ${minutes}m ago`;
    } else if (hours < 24) {
      return `Checked ${hours}h ago`;
    } else {
      return `Checked ${days}d ago`;
    }
  };

  const getHealthScore = (feed) => {
    let score = 0;
    if (feed.is_active) score += 25;
    if (feed.last_success) score += 25;
    if (feed.failure_count === 0) score += 25;
    if (feed.article_count > 0) score += 25;
    return score;
  };

  const healthScore = getHealthScore(feed);

  return (
    <Box sx={{ 
      p: 2, 
      border: '1px solid #e0e0e0', 
      borderRadius: 2, 
      backgroundColor: 'white',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 500 }}>
            {feed.name}
          </Typography>
          <Typography variant="body2" color="textSecondary" sx={{ wordBreak: 'break-all' }}>
            {feed.url}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Test Feed">
            <IconButton size="small" onClick={() => onTest(feed.id)} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title={feed.is_active ? 'Pause Feed' : 'Activate Feed'}>
            <IconButton size="small" onClick={() => onToggle(feed.id)} disabled={loading}>
              {feed.is_active ? <PauseIcon /> : <PlayIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Status */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Chip
          icon={getStatusIcon(feed.status || (feed.is_active ? 'active' : 'inactive'))}
          label={getStatusText(feed.status || (feed.is_active ? 'active' : 'inactive'))}
          color={getStatusColor(feed.status || (feed.is_active ? 'active' : 'inactive'))}
          size="small"
        />
        {feed.category && (
          <Chip
            label={feed.category}
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {/* Health Score */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2">Health Score</Typography>
          <Typography variant="body2">{healthScore}%</Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={healthScore}
          color={healthScore > 75 ? 'success' : healthScore > 50 ? 'warning' : 'error'}
          sx={{ height: 8, borderRadius: 4 }}
        />
      </Box>

      {/* Stats */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant="body2" color="textSecondary">
            Articles: {feed.article_count || 0}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Failures: {feed.failure_count || 0}
          </Typography>
        </Box>
        <Box>
          <Typography variant="body2" color="textSecondary">
            Last Check: {getLastCheckText(feed.last_checked)}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Last Success: {feed.last_success ? getLastCheckText(feed.last_success) : 'Never'}
          </Typography>
        </Box>
      </Box>

      {/* Error Message */}
      {feed.error_message && (
        <Box sx={{ 
          p: 1, 
          backgroundColor: 'error.light', 
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'error.main'
        }}>
          <Typography variant="caption" color="error">
            {feed.error_message}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default FeedStatusIndicator;
