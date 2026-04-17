/**
 * Domain Indicator Component
 * Prominent domain display for pages
 */

import React from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { useDomain } from '../../../contexts/DomainContext';

interface DomainIndicatorProps {
  variant?: 'badge' | 'banner' | 'inline';
  showLabel?: boolean;
}

const DomainIndicator: React.FC<DomainIndicatorProps> = ({
  variant = 'badge',
  showLabel = true,
}) => {
  const { domainName, domain } = useDomain();

  const getDomainConfig = () => {
    switch (domain) {
      case 'politics':
        return {
          color: '#1976d2',
          bg: '#e3f2fd',
          icon: '🏛️',
          name: 'Politics',
        };
      case 'finance':
        return {
          color: '#2e7d32',
          bg: '#e8f5e9',
          icon: '💰',
          name: 'Finance',
        };
      case 'artificial-intelligence':
        return {
          color: '#7b1fa2',
          bg: '#f3e5f5',
          icon: '🤖',
          name: 'Artificial Intelligence',
        };
      case 'medicine':
        return {
          color: '#c62828',
          bg: '#ffebee',
          icon: '🏥',
          name: 'Medicine',
        };
      case 'environment-climate':
        return {
          color: '#00695c',
          bg: '#e0f2f1',
          icon: '🌍',
          name: 'Environment & Climate',
        };
      case 'legal':
        return {
          color: '#455a64',
          bg: '#eceff1',
          icon: '⚖️',
          name: 'Legal',
        };
      default:
        return {
          color: '#616161',
          bg: '#f5f5f5',
          icon: '📰',
          name: domainName,
        };
    }
  };

  const config = getDomainConfig();

  if (variant === 'banner') {
    return (
      <Box
        sx={{
          backgroundColor: config.bg,
          borderLeft: `4px solid ${config.color}`,
          padding: 2,
          mb: 3,
          borderRadius: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant='h6' sx={{ fontSize: '1.5rem' }}>
            {config.icon}
          </Typography>
          <Box>
            <Typography
              variant='caption'
              color='text.secondary'
              sx={{ display: 'block' }}
            >
              Current Domain
            </Typography>
            <Typography
              variant='h6'
              sx={{ color: config.color, fontWeight: 600 }}
            >
              {config.name}
            </Typography>
          </Box>
        </Box>
      </Box>
    );
  }

  if (variant === 'inline') {
    return (
      <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
        <Typography variant='body2' component='span'>
          {config.icon}
        </Typography>
        {showLabel && (
          <Chip
            label={config.name}
            size='small'
            sx={{
              backgroundColor: config.bg,
              color: config.color,
              fontWeight: 600,
              border: `1px solid ${config.color}`,
            }}
          />
        )}
      </Box>
    );
  }

  // Default: badge variant
  return (
    <Chip
      icon={<span>{config.icon}</span>}
      label={showLabel ? config.name : ''}
      sx={{
        backgroundColor: config.bg,
        color: config.color,
        fontWeight: 600,
        border: `1px solid ${config.color}`,
      }}
    />
  );
};

export default DomainIndicator;
