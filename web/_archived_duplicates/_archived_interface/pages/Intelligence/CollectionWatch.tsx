/**
 * Collection & pipeline watch — orchestrators run with the API; start the API and watch stats here.
 * Orchestrator Coordinator (RSS, finance collection) and Automation Manager (context sync, claims, events)
 * start automatically on API startup. This page shows their status and live context-centric counts.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import PlayArrow as PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ExpandMore as ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RssFeed as RssFeedIcon from '@mui/icons-material/RssFeed';
import Refresh as RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircle as CheckCircleIcon from '@mui/icons-material/CheckCircle';
import Warning as WarningIcon from '@mui/icons-material/Warning';
import { useDomain } from '../../contexts/DomainContext';
import apiService from '../../services/apiService';
import { contextCentricApi, type ContextCentricStatus } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const POLL_INTERVAL_MS = 5000;

interface OrchestratorStatus {
  running?: boolean;
  current_cycle?: number;
  last_collection_times?: Record<string, string>;
  loop_interval_seconds?: number;
  updated_at?: string;
  error?: string;
}

const CollectionWatch: React.FC = () => {
  const { domain } = useDomain();
  const [orchestratorStatus, setOrchestratorStatus] = useState<OrchestratorStatus | null>(null);
  const [contextStatus, setContextStatus] = useState<ContextCentricStatus | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<Record<string, unknown> | null>(null);
  const [liveRefresh, setLiveRefresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<'idle' | 'rss' | 'pipeline'>('idle');
  const [lastRssResult, setLastRssResult] = useState<{ articles_added?: number } | null>(null);
  const [lastPipelineResult, setLastPipelineResult] = useState<Record<string, unknown> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const [dashboard, ctx, pipe] = await Promise.all([
        apiService.getOrchestratorDashboard({ decision_log_limit: 5 }).catch(() => null),
        contextCentricApi.getStatus().catch(() => null),
        apiService.getPipelineStatus().then((r: any) => (r?.success !== false ? r : null)).catch(() => null),
      ]);
      if (dashboard?.status) setOrchestratorStatus(dashboard.status as OrchestratorStatus);
      else if (dashboard?.error) setOrchestratorStatus({ running: false, error: dashboard.error });
      else setOrchestratorStatus(null);
      if (ctx) setContextStatus(ctx);
      if (pipe) setPipelineStatus(pipe);
      setError(null);
    } catch (e) {
      Logger.apiError('Collection watch fetch failed', e as Error);
      setError((e as Error).message ?? 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    if (!liveRefresh) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(fetchStats, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [liveRefresh, fetchStats]);

  const handleCollectRss = async () => {
    setAction('rss');
    setError(null);
    setLastRssResult(null);
    try {
      const res = await apiService.updateRSSFeeds(domain || 'politics');
      setLastRssResult(res || null);
      await fetchStats();
    } catch (e) {
      Logger.apiError('RSS collection failed', e as Error);
      setError((e as Error).message ?? 'RSS collection failed');
    } finally {
      setAction('idle');
    }
  };

  const handleRunPipeline = async () => {
    setAction('pipeline');
    setError(null);
    setLastPipelineResult(null);
    try {
      const res = await apiService.triggerPipeline();
      setLastPipelineResult(res || null);
      await fetchStats();
    } catch (e) {
      Logger.apiError('Pipeline trigger failed', e as Error);
      setError((e as Error).message ?? 'Pipeline trigger failed');
    } finally {
      setAction('idle');
    }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }} component="h1">
        <PlayArrowIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Collection & pipeline
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>Orchestrators run automatically when the API is running.</strong> Start the API (e.g. <code>./start_system.sh</code> or <code>uvicorn</code>). The Orchestrator Coordinator runs RSS and finance collection on a loop; the Automation Manager runs context sync, entity profiles, claims, and event tracking on schedule. Watch the stats below — they refresh every 5s when live refresh is on.
      </Alert>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={fetchStats} disabled={loading}>
          Refresh stats
        </Button>
        <FormControlLabel
          control={<Switch checked={liveRefresh} onChange={(e) => setLiveRefresh(e.target.checked)} />}
          label="Live refresh (5s)"
        />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Orchestrator coordinator
              </Typography>
              {orchestratorStatus === null ? (
                <Typography variant="body2" color="text.secondary">Loading…</Typography>
              ) : orchestratorStatus.error ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <WarningIcon color="warning" fontSize="small" />
                  <Typography variant="body2" color="text.secondary">{orchestratorStatus.error}</Typography>
                </Box>
              ) : (
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    {orchestratorStatus.running ? (
                      <CheckCircleIcon color="success" fontSize="small" />
                    ) : (
                      <WarningIcon color="warning" fontSize="small" />
                    )}
                    <Typography variant="body2">
                      {orchestratorStatus.running ? 'Running' : 'Not running'}
                    </Typography>
                  </Box>
                  {orchestratorStatus.current_cycle != null && (
                    <Typography variant="caption" display="block" color="text.secondary">
                      Cycle: {orchestratorStatus.current_cycle}
                      {orchestratorStatus.loop_interval_seconds != null &&
                        ` · interval ${orchestratorStatus.loop_interval_seconds}s`}
                    </Typography>
                  )}
                  {orchestratorStatus.last_collection_times && Object.keys(orchestratorStatus.last_collection_times).length > 0 && (
                    <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                      Last collection: {Object.entries(orchestratorStatus.last_collection_times).map(([k, v]) => `${k}: ${v}`).join(', ')}
                    </Typography>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Context-centric pipeline
              </Typography>
              {contextStatus ? (
                <Grid container spacing={1} sx={{ mt: 0.5 }}>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Contexts</Typography>
                    <Typography variant="h6">{contextStatus.contexts}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Article→Context</Typography>
                    <Typography variant="h6">{contextStatus.article_to_context_links}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Entity profiles</Typography>
                    <Typography variant="h6">{contextStatus.entity_profiles}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Claims</Typography>
                    <Typography variant="h6">{contextStatus.extracted_claims}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Events</Typography>
                    <Typography variant="h6">{contextStatus.tracked_events}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="text.secondary">Patterns</Typography>
                    <Typography variant="h6">{contextStatus.pattern_discoveries}</Typography>
                  </Grid>
                </Grid>
              ) : (
                <Typography variant="body2" color="text.secondary">Loading…</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Pipeline status
              </Typography>
              {pipelineStatus && (pipelineStatus as any).pipeline_status != null ? (
                <Box>
                  <Typography variant="body2">
                    Status: <strong>{(pipelineStatus as any).pipeline_status}</strong>
                  </Typography>
                  {(pipelineStatus as any).current_stage && (
                    <Typography variant="body2" color="text.secondary">
                      Stage: {(pipelineStatus as any).current_stage}
                    </Typography>
                  )}
                </Box>
              ) : pipelineStatus && (pipelineStatus as any).success === false ? (
                <Typography variant="body2" color="text.secondary">Pipeline status unavailable</Typography>
              ) : (
                <Typography variant="body2" color="text.secondary">Loading…</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Accordion sx={{ mt: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2">Manual override (run collection or full pipeline now)</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <Button
              variant="outlined"
              startIcon={action === 'rss' ? <CircularProgress size={18} /> : <RssFeedIcon />}
              onClick={handleCollectRss}
              disabled={action !== 'idle'}
            >
              Collect RSS now
            </Button>
            <Button
              variant="outlined"
              startIcon={action === 'pipeline' ? <CircularProgress size={18} /> : <PlayArrowIcon />}
              onClick={handleRunPipeline}
              disabled={action !== 'idle'}
            >
              Run full pipeline
            </Button>
          </Box>
          {lastRssResult != null && (
            <Alert severity="success" sx={{ mt: 2 }}>
              RSS collection completed. Articles added: {lastRssResult.articles_added ?? '—'}
            </Alert>
          )}
          {lastPipelineResult != null && (lastPipelineResult as any).message && (
            <Alert severity="info" sx={{ mt: 2 }}>
              {(lastPipelineResult as any).message}
            </Alert>
          )}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default CollectionWatch;
