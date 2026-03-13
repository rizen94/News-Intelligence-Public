/**
 * Standardized Empty State Component
 * Consistent empty state messages across all pages
 */

import React from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import { Inbox as InboxIcon } from '@mui/icons-material';

interface EmptyStateProps {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  message,
  actionLabel,
  onAction,
  icon,
}) => {
  return (
    <Paper
      sx={{
        p: 4,
        textAlign: 'center',
        backgroundColor: 'background.default',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
        }}
      >
        {icon || (
          <InboxIcon
            sx={{
              fontSize: 64,
              color: 'text.secondary',
              opacity: 0.5,
            }}
          />
        )}
        <Typography variant='h6' color='text.primary'>
          {title}
        </Typography>
        <Typography variant='body2' color='text.secondary' sx={{ maxWidth: 400 }}>
          {message}
        </Typography>
        {actionLabel && onAction && (
          <Button
            variant='contained'
            color='primary'
            onClick={onAction}
            sx={{ mt: 1 }}
          >
            {actionLabel}
          </Button>
        )}
      </Box>
    </Paper>
  );
};

export default EmptyState;

