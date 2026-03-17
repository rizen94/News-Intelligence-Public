/**
 * Hero status bar — system health, quick stats, last update.
 * Aligned with WEB_PRODUCT_DISPLAY_PLAN (Intelligence Dashboard).
 */
import React, { useEffect, useState } from 'react';
import { Box, Typography, Chip } from '@mui/material';
import { contextCentricApi, type ContextCentricStatus } from '../services/api/contextCentric';
import apiService from '../services/apiService';
import { useDomain } from '../contexts/DomainContext';
import APIConnectionStatus from '../components/APIConnectionStatus/APIConnectionStatus';

export const HeroStatusBar: React.FC = () => {
  const { domain } = useDomain();
  const [health, setHealth] = useState<{ status?: string; services?: Record<string, string> } | null>(null);
  const [orchStatus, setOrchStatus] = useState<{
    running?: boolean;
    last_collection_times?: Record<string, string>;
    collection_sources?: string[];
  } | null>(null);
  const [ctxStatus, setCtxStatus] = useState<ContextCentricStatus | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        const [h, o, c] = await Promise.all([
          apiService.getHealth().catch(() => null),
          apiService.getOrchestratorDashboard?.({ decision_log_limit: 1 }).then((d: any) => d?.status).catch(() => null),
          contextCentricApi.getStatus().catch(() => null),
        ]);
        if (cancelled) return;
        if (h && typeof h === 'object') setHealth(h);
        if (o && typeof o === 'object') setOrchStatus(o);
        if (c && typeof c === 'object') setCtxStatus(c);
        setLastFetch(new Date());
      } catch {
        if (!cancelled) setLastFetch(new Date());
      }
    };
    fetchAll();
    const t = setInterval(fetchAll, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

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
              Events: <strong>{ctxStatus.tracked_events.toLocaleString()}</strong>
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
