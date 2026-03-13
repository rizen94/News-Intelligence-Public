/**
 * Monitor — Collection watch, source health, quality metrics.
 */
import React, { useEffect, useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
  Chip,
  Skeleton,
  Alert,
} from '@mui/material';
import apiService from '@/services/apiService';
import { contextCentricApi } from '@/services/api/contextCentric';

export default function MonitorPage() {
  const [orch, setOrch] = useState<Record<string, unknown> | null>(null);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [o, q] = await Promise.all([
          apiService.getOrchestratorDashboard?.({ decision_log_limit: 5 }).then((d: any) => d?.status ?? d).catch((e: Error) => {
            setError(e?.message ?? 'Failed to load orchestrator');
            return null;
          }),
          contextCentricApi.getQuality().catch(() => null),
        ]);
        if (cancelled) return;
        setOrch(o ?? null);
        setQuality(q ?? null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const t = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const lastTimes = (orch?.last_collection_times as Record<string, string> | undefined) ?? {};
  const running = orch?.running as boolean | undefined;
  const byDomain = quality?.by_domain as Record<string, { context_coverage_pct?: number; entity_coverage_pct?: number }> | undefined;

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 600 }}>
        Monitor
      </Typography>
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
        <Card sx={{ minWidth: 280 }}>
          <CardHeader title="Collection status" subheader={running ? 'Running' : 'Not running'} />
          <CardContent>
            {loading ? (
              <Skeleton variant="rectangular" height={80} />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {Object.entries(lastTimes).map(([source, time]) => (
                  <Box key={source} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">{source}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {time ? new Date(time).toLocaleString() : '—'}
                    </Typography>
                  </Box>
                ))}
                {Object.keys(lastTimes).length === 0 && (
                  <Typography color="text.secondary">No collection data yet.</Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 280 }}>
          <CardHeader title="Quality metrics" subheader="Context & entity coverage" />
          <CardContent>
            {loading ? (
              <Skeleton variant="rectangular" height={80} />
            ) : byDomain ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {Object.entries(byDomain).map(([d, row]) => (
                  <Box key={d} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Typography variant="body2">{d}</Typography>
                    {row.context_coverage_pct != null && (
                      <Chip size="small" label={`Context: ${row.context_coverage_pct}%`} />
                    )}
                    {row.entity_coverage_pct != null && (
                      <Chip size="small" label={`Entity: ${row.entity_coverage_pct}%`} />
                    )}
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography color="text.secondary">No quality data.</Typography>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
