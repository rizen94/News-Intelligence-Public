import React from 'react';
import { Box, Typography, LinearProgress, Chip } from '@mui/material';
import { TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';

interface SentimentDisplayProps {
  score?: number;
  label?: string;
  showIcon?: boolean;
  size?: 'small' | 'medium' | 'large';
}

const SentimentDisplay: React.FC<SentimentDisplayProps> = ({
  score = 0,
  label,
  showIcon = true,
  size = 'medium',
}) => {
  const getSentimentColor = (score: number) => {
    if (score > 0.1) return 'success';
    if (score < -0.1) return 'error';
    return 'warning';
  };

  const getSentimentLabel = (score: number) => {
    if (score > 0.1) return 'Positive';
    if (score < -0.1) return 'Negative';
    return 'Neutral';
  };

  const getSentimentIcon = (score: number) => {
    if (score > 0.1) return <TrendingUp />;
    if (score < -0.1) return <TrendingDown />;
    return <TrendingFlat />;
  };

  const getProgressValue = (score: number) => {
    return Math.abs(score) * 100;
  };

  const sizeConfig = {
    small: { fontSize: '0.75rem', height: 4 },
    medium: { fontSize: '0.875rem', height: 6 },
    large: { fontSize: '1rem', height: 8 },
  };

  const config = sizeConfig[size];

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {showIcon && (
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {getSentimentIcon(score)}
        </Box>
      )}
      <Box sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Typography variant="body2" sx={{ fontSize: config.fontSize }}>
            {label || getSentimentLabel(score)}
          </Typography>
          <Typography variant="body2" sx={{ fontSize: config.fontSize, fontWeight: 500 }}>
            {score.toFixed(2)}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={getProgressValue(score)}
          color={getSentimentColor(score)}
          sx={{ height: config.height, borderRadius: 2 }}
        />
      </Box>
      <Chip
        label={getSentimentLabel(score)}
        color={getSentimentColor(score)}
        size="small"
        variant="outlined"
      />
    </Box>
  );
};

export default SentimentDisplay;