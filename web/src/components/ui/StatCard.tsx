import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { uiTokens } from './tokens';

export type StatCardProps = {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'success' | 'warning' | 'error';
};

const toneColor = {
  default: 'text.primary',
  success: 'success.main',
  warning: 'warning.main',
  error: 'error.main',
} as const;

export function StatCard({ label, value, hint, tone = 'default' }: StatCardProps) {
  return (
    <Paper
      variant='outlined'
      sx={{
        p: 2,
        minWidth: uiTokens.statCard.minWidth,
        borderRadius: 2,
        flex: '1 1 140px',
      }}
    >
      <Typography variant='caption' color='text.secondary' textTransform='uppercase' letterSpacing={0.5}>
        {label}
      </Typography>
      <Typography variant='h5' fontWeight={700} color={toneColor[tone]} sx={{ mt: 0.5 }}>
        {value}
      </Typography>
      {hint && (
        <Typography variant='caption' color='text.secondary' display='block' sx={{ mt: 0.5 }}>
          {hint}
        </Typography>
      )}
    </Paper>
  );
}

export function StatCardRow({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>{children}</Box>
  );
}
