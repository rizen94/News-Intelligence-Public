/**
 * Hero status bar — system health, quick stats, last update.
 * Product notes: docs/archive/planning_incubator/WEB_PRODUCT_DISPLAY_PLAN.md
 */
import React from 'react';
import { Box, Typography, Chip } from '@mui/material';
import { heroBarEventsStoredCount } from '../services/api/contextCentric';
import APIConnectionStatus from '../components/APIConnectionStatus/APIConnectionStatus';
import { useShellStatus } from '../contexts/ShellStatusContext';

export const HeroStatusBar: React.FC = () => {
  const { health, orchStatus, ctxStatus, lastFetch } = useShellStatus();

  const systemHealthy = health?.status === 'healthy';
  const sourcesCount = orchStatus?.collection_sources?.length ?? 0;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 2,
        px: 2,
        py: 1.5,
        bgcolor: 'background.paper',
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <APIConnectionStatus showDetails={false} />
        <Box
          sx={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            bgcolor: systemHealthy ? 'success.main' : health ? 'warning.main' : 'grey.400',
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {systemHealthy ? 'System healthy' : health ? 'Degraded' : 'Checking…'}
        </Typography>
        {sourcesCount > 0 && (
          <Chip size="small" label={`${sourcesCount} sources`} variant="outlined" />
        )}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        {ctxStatus && (
          <>
            <Typography variant="body2" color="text.secondary">
              Contexts: <strong>{ctxStatus.contexts.toLocaleString()}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Entity Profiles: <strong>{ctxStatus.entity_profiles.toLocaleString()}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Events:{' '}
              <strong>
                {heroBarEventsStoredCount(ctxStatus).toLocaleString()}
              </strong>
            </Typography>
          </>
        )}
      </Box>

      <Typography variant="caption" color="text.secondary">
        {lastFetch ? `Updated ${Math.round((Date.now() - lastFetch.getTime()) / 1000)}s ago` : 'Loading…'}
      </Typography>
    </Box>
  );
};
