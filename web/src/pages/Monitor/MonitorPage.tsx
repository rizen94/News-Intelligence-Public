/**
 * Monitor — System health, connection status, live activity, processing pulse, pipeline status.
 * Heavy DB-backed panels (backlog ETAs, run summary, phase timeline, DB sessions, etc.) were
 * removed from this page to keep loads fast while the pipeline is busy.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
  Paper,
  Stack,
  Chip,
  Skeleton,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Link,
  TextField,
} from '@mui/material';
import PushPinIcon from '@mui/icons-material/PushPin';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import ApiIcon from '@mui/icons-material/Api';
import StorageIcon from '@mui/icons-material/Storage';
import PublicIcon from '@mui/icons-material/Public';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import apiService from '@/services/apiService';
import {
  contextCentricApi,
  heroBarEventsStoredCount,
  type ContextCentricStatus,
} from '@/services/api/contextCentric';
import { getDefaultDomainKey, getDomainKeysList } from '@/utils/domainHelper';
import { usePinnedThreads } from '@/hooks/usePinnedThreads';

/** Poll interval for full Monitor refresh (overview + pipeline + processing pulse together). */
const POLL_INTERVAL_MS = 15000;

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Wall-clock label so multiple runs are not all identical when timeAgo buckets to \"3d ago\". */
function shortLocalDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

/** Format remaining / typical phase duration for Current activity (from overview API). */
function activityRunEstimateSecondary(a: Record<string, unknown>): string | null {
  const typicalSec = a.typical_run_duration_seconds;
  const typicalMin = a.typical_run_duration_minutes;
  const remMin = a.estimated_remaining_minutes;
  const exceeded = a.exceeded_typical_run === true;
  if (typeof typicalSec !== 'number' || typicalSec <= 0) return null;
  const typMin =
    typeof typicalMin === 'number' ? typicalMin : Math.round(typicalSec / 60);
  if (exceeded) {
    return `past typical run (~${typMin}m)`;
  }
  if (typeof remMin === 'number' && remMin >= 0) {
    const r = remMin < 0.1 && remMin > 0 ? '<0.1' : String(remMin);
    return `~${r}m remaining · typical ~${typMin}m`;
  }
  return `typical ~${typMin}m`;
}

type ProcessingPulseDimension = {
  id?: string;
  label?: string;
  backlog?: number | null;
  last_1h?: number;
  last_24h?: number;
  last_7d?: number;
};

type ProcessingPulsePhase = {
  phase_name?: string;
  /** DB-backed count of records not yet processed for this phase (pending queue). */
  pending_records?: number;
  /** ceil(unprocessed ÷ rows_per_run); null if no row-batch model. How many phase runs to drain the queue. */
  batches_to_drain?: number | null;
  /** Modeled rows consumed per scheduled run (not measured from history). */
  estimated_batch_per_run?: number;
  runs_1h?: number;
  runs_24h?: number;
  runs_7d?: number;
  successes_24h?: number;
  failures_24h?: number;
  successes_7d?: number;
  failures_7d?: number;
  /** % of automation_run_history rows in window with success=true */
  pass_rate_24h?: number | null;
  pass_rate_7d?: number | null;
  avg_duration_sec_24h?: number | null;
};

function formatPulseCount(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 100000) return `${Math.round(n / 1000)}k`;
  if (n >= 10000) {
    const k = n / 1000;
    return Number.isInteger(k) ? `${k}k` : `${k.toFixed(1)}k`;
  }
  return `${n}`;
}

/**
 * Heuristic only: compare the latest hour to a baseline that avoids double-counting that hour
 * inside the 24h total. Baseline = mean completions over the other 23 hours in the rolling window;
 * if those are too sparse, fall back to mean over full 24h (still a rough rate, not a formal test).
 */
function pulseTrendSymbol(
  last1h: number,
  last24h: number
): { sym: string; title: string } {
  const prev23 = Math.max(0, last24h - last1h);
  const baselineFromPrior23 = prev23 / 23;
  const baselineFrom24 = last24h / 24;
  const usePrior23 = prev23 >= 12;
  const baseline = usePrior23 ? baselineFromPrior23 : baselineFrom24;

  if (last24h < 12)
    return { sym: '·', title: 'Low 24h volume — comparison not meaningful' };

  if (baseline <= 0)
    return { sym: '·', title: 'No baseline rate for hourly comparison' };

  const baselineLabel = usePrior23
    ? 'avg over other 23h in window'
    : 'avg over full 24h (fallback when rest of window sparse)';

  if (last1h > baseline * 1.25)
    return {
      sym: '▲',
      title: `Last hour above ${baselineLabel} (+25% band) — heuristic, not significance-tested`,
    };
  if (last1h < baseline * 0.75)
    return {
      sym: '▼',
      title: `Last hour below ${baselineLabel} (−25% band) — heuristic, not significance-tested`,
    };
  return {
    sym: '■',
    title: `Within ±25% of ${baselineLabel}`,
  };
}

export default function MonitorPage() {
  const { domain: routeDomain } = useParams<{ domain: string }>();
  const navDomain = routeDomain ?? getDefaultDomainKey();
  const pinned = usePinnedThreads(navDomain);
  const [pinStorylineInput, setPinStorylineInput] = useState('');
  const [overview, setOverview] = useState<{
    success?: boolean;
    connections?: Record<string, unknown>;
    activities?: {
      current?: Array<Record<string, unknown>>;
      recent?: Array<Record<string, unknown>>;
    };
    error?: string;
  } | null>(null);
  const [pipeline, setPipeline] = useState<{
    success?: boolean;
    data?: Record<string, unknown>;
    error?: string;
  } | null>(null);
  const [gpuMetricHistory, setGpuMetricHistory] = useState<{
    success?: boolean;
    data?: {
      hours?: number;
      hourly?: Array<Record<string, unknown>>;
    };
    error?: string;
  } | null>(null);
  const [processingPulse, setProcessingPulse] = useState<{
    success?: boolean;
    data?: {
      generated_at_utc?: string;
      /** False when API skipped backlog_metrics (faster; phase "Unprocessed rows" are zeros). */
      pending_metrics_included?: boolean;
      reporting_definitions?: Record<string, string>;
      dimensions?: ProcessingPulseDimension[];
      phase_dashboard?: ProcessingPulsePhase[];
      phases?: ProcessingPulsePhase[];
      hourly_phase_ticks?: Array<{
        hour_utc?: string;
        phase_name?: string;
        runs?: number;
        failures?: number;
      }>;
      /** When hourly rows are omitted (default API), server still returns bucket count. */
      hourly_phase_tick_bucket_count?: number | null;
    };
    error?: string;
  } | null>(null);
  /** First full bundle (overview + pipeline + pulse) not yet finished. */
  const [initialLoad, setInitialLoad] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggerPhaseName, setTriggerPhaseName] = useState<string>('');
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{
    success: boolean;
    message: string;
    warning?: string;
  } | null>(null);
  /** Global corpus counters + orchestrator collection times (moved from Dashboard). */
  const [ccStatus, setCcStatus] = useState<ContextCentricStatus | null>(null);
  const [orchCollection, setOrchCollection] = useState<Record<
    string,
    unknown
  > | null>(null);
  /** From GET /api/system_monitoring/automation/status — confirms FIFO vs legacy LIFO batch ordering. */
  const [pipelineArticleSelection, setPipelineArticleSelection] = useState<{
    mode?: string;
    label?: string;
    sql_created_at?: string;
    order_env?: string;
  } | null>(null);

  /** One bundle: health/activity, pipeline card, full processing pulse (incl. unprocessed rows). */
  const refreshMonitor = useCallback(async () => {
    const orchDash = (async () => {
      try {
        const fn = apiService.getOrchestratorDashboard;
        if (typeof fn !== 'function') return null;
        const d = await fn.call(apiService, { decision_log_limit: 1 });
        return (d as { status?: Record<string, unknown> } | null)?.status ?? null;
      } catch {
        return null;
      }
    })();

    const [ov, pipe, pulse, gpuH, stData, orchData, autoEnvelope] = await Promise.all([
      apiService.getMonitoringOverview(),
      apiService.getPipelineStatus(),
      // Real per-phase queue depths require backlog_metrics (slower); nginx allows long reads on /api/system_monitoring/.
      apiService.getProcessingProgress({ includePendingMetrics: true }),
      apiService.getGpuMetricHistory(72),
      contextCentricApi.getStatus(null).catch(() => null),
      orchDash,
      apiService.getAutomationStatus().catch(() => null),
    ]);
    setOverview(ov ?? null);
    setPipeline(pipe ?? null);
    setProcessingPulse(pulse ?? null);
    setGpuMetricHistory(gpuH ?? null);
    setCcStatus(stData ?? null);
    setOrchCollection(orchData ?? null);
    const autoData = (
      autoEnvelope as {
        data?: {
          pipeline_article_selection?: {
            mode?: string;
            label?: string;
            sql_created_at?: string;
            order_env?: string;
          };
        };
      } | null
    )?.data;
    setPipelineArticleSelection(autoData?.pipeline_article_selection ?? null);
  }, []);

  const lastCollectionTimes = useMemo(() => {
    const raw = orchCollection?.last_collection_times as
      | Record<string, string>
      | undefined;
    return raw && typeof raw === 'object' ? raw : {};
  }, [orchCollection]);

  const gpuChartRows = useMemo(() => {
    const hourly = gpuMetricHistory?.data?.hourly;
    if (!Array.isArray(hourly) || hourly.length === 0) return [];
    return hourly.map((row: Record<string, unknown>) => ({
      label: row.hour_utc
        ? shortLocalDateTime(String(row.hour_utc))
        : '—',
      util:
        typeof row.avg_gpu_utilization_percent === 'number'
          ? row.avg_gpu_utilization_percent
          : null,
      vram:
        typeof row.avg_gpu_vram_percent === 'number'
          ? row.avg_gpu_vram_percent
          : null,
      temp:
        typeof row.avg_gpu_temperature_c === 'number'
          ? row.avg_gpu_temperature_c
          : null,
    }));
  }, [gpuMetricHistory]);

  useEffect(() => {
    let cancelled = false;
    let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;

    void (async () => {
      setInitialLoad(true);
      setError(null);
      try {
        await refreshMonitor();
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setInitialLoad(false);
      }
      if (cancelled) return;

      /** Wait for each tick to finish before scheduling the next (no overlapping bundles). */
      const schedulePoll = () => {
        pollTimeoutId = setTimeout(() => {
          void (async () => {
            if (cancelled) return;
            try {
              await refreshMonitor();
            } catch {
              /* monitoring APIs usually return { success: false }; guard anyway */
            }
            if (!cancelled) schedulePoll();
          })();
        }, POLL_INTERVAL_MS);
      };
      schedulePoll();
    })();

    return () => {
      cancelled = true;
      if (pollTimeoutId !== null) clearTimeout(pollTimeoutId);
    };
  }, [refreshMonitor]);

  const handleTriggerPhase = async () => {
    if (!triggerPhaseName || !apiService.triggerPhase) return;
    setTriggering(true);
    setTriggerResult(null);
    try {
      const result = (await apiService.triggerPhase(triggerPhaseName)) as {
        success?: boolean;
        message?: string;
        error?: string;
        warning?: string;
      };
      if (result?.success !== false) {
        setTriggerResult({
          success: true,
          message:
            (result?.message as string) ||
            `Phase "${triggerPhaseName}" requested.`,
          warning: result?.warning as string | undefined,
        });
        setTriggerPhaseName('');
        void refreshMonitor();
        setTimeout(() => void refreshMonitor(), 2500);
        setTimeout(() => void refreshMonitor(), 6000);
      } else {
        setTriggerResult({
          success: false,
          message: (result?.error as string) || 'Request failed.',
        });
      }
      setTimeout(() => setTriggerResult(null), 6000);
    } catch (e) {
      setTriggerResult({ success: false, message: (e as Error).message });
      setTimeout(() => setTriggerResult(null), 6000);
    } finally {
      setTriggering(false);
    }
  };

  const connections = (overview?.connections ?? {}) as Record<string, unknown>;
  const apiStatus = connections?.api as string | undefined;
  const dbStatus = connections?.database as string | undefined;
  const webserver = connections?.webserver as
    | Record<string, unknown>
    | undefined;
  const wsStatus = webserver?.status as string | undefined;
  const currentActivities =
    (overview?.activities as { current?: Array<Record<string, unknown>> })
      ?.current ?? [];
  const recentActivities =
    (overview?.activities as { recent?: Array<Record<string, unknown>> })
      ?.recent ?? [];

  const pipelineData = pipeline?.data ?? {};
  const pipelineStatus = pipelineData?.pipeline_status as string | undefined;

  const RUN_PHASE_FALLBACK = useMemo(
    () => [
      'collection_cycle',
      'context_sync',
      'entity_extraction',
      'entity_profile_sync',
      'claim_extraction',
      'claims_to_facts',
      'event_tracking',
      'event_extraction',
      'topic_clustering',
      'storyline_discovery',
      'storyline_processing',
      'editorial_document_generation',
      'editorial_briefing_generation',
      'digest_generation',
      'daily_briefing_synthesis',
    ],
    []
  );

  const runPhaseOptions = useMemo(() => {
    const rows =
      processingPulse?.data?.phase_dashboard ??
      processingPulse?.data?.phases ??
      [];
    const names = rows
      .map(p => p.phase_name)
      .filter((n): n is string => typeof n === 'string' && n.length > 0);
    const uniq = [...new Set(names)].sort();
    return uniq.length > 0 ? uniq : RUN_PHASE_FALLBACK;
  }, [
    processingPulse?.data?.phase_dashboard,
    processingPulse?.data?.phases,
    RUN_PHASE_FALLBACK,
  ]);

  const overviewLoadFailed =
    !initialLoad && overview != null && overview.success === false;

  const statusChip = (status: string | undefined, label: string) => {
    if (status === 'not_loaded') {
      return (
        <Chip
          size='small'
          variant='outlined'
          label={`${label} (not loaded)`}
          color='default'
          sx={{ mr: 1 }}
        />
      );
    }
    const ok = status === 'ok' || status === 'healthy' || status === 'HEALTHY';
    const unknown = !status || status === 'unknown';
    const color = ok ? 'success' : unknown ? 'default' : 'error';
    const icon = ok ? (
      <CheckCircleOutlineIcon />
    ) : unknown ? undefined : (
      <ErrorOutlineIcon />
    );
    return (
      <Chip
        size='small'
        icon={icon}
        label={unknown ? `${label} (checking…)` : label}
        color={color}
        variant='outlined'
        sx={{ mr: 1 }}
      />
    );
  };

  const pipelineStatusColor =
    pipelineStatus === 'running'
      ? 'info'
      : pipelineStatus === 'error'
      ? 'error'
      : pipelineStatus === 'healthy'
      ? 'success'
      : 'default';

  return (
    <Box>
      <Typography variant='h5' sx={{ mb: 2, fontWeight: 600 }}>
        Monitor
      </Typography>
      <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
        <Link
          component={RouterLink}
          to={`/${navDomain}/monitor/sql-explorer`}
          underline='hover'
        >
          SQL explorer
        </Link>{' '}
        (read-only; enable with <code>NEWS_INTEL_SQL_EXPLORER=true</code> on the
        API)
      </Typography>

      <Paper variant='outlined' sx={{ p: 2, mb: 2 }}>
        <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 0.5 }}>
          Pinned threads
        </Typography>
        <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1.5 }}>
          Stored in this browser per domain — quick links into storylines you care
          about while watching the pipeline. Phase 2: optional API filters on
          processing_progress / backlog.
        </Typography>
        <Stack direction='row' flexWrap='wrap' gap={1} sx={{ mb: 2 }}>
          {[...pinned.pinnedStorylineIds].length === 0 ? (
            <Typography variant='body2' color='text.secondary'>
              No pins yet — add a storyline ID below.
            </Typography>
          ) : (
            [...pinned.pinnedStorylineIds].map(id => (
              <Chip
                key={id}
                icon={<PushPinIcon />}
                label={`Storyline ${id}`}
                component={RouterLink}
                to={`/${navDomain}/storylines/${id}`}
                onDelete={e => {
                  e.preventDefault();
                  pinned.unpinStoryline(id);
                }}
                clickable
                variant='outlined'
              />
            ))
          )}
        </Stack>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }}>
          <TextField
            size='small'
            label='Storyline ID'
            type='number'
            value={pinStorylineInput}
            onChange={e => setPinStorylineInput(e.target.value)}
            sx={{ maxWidth: 200 }}
          />
          <Button
            size='small'
            variant='outlined'
            onClick={() => {
              const n = parseInt(pinStorylineInput, 10);
              if (!Number.isNaN(n) && n > 0) {
                pinned.pinStoryline(n);
                setPinStorylineInput('');
              }
            }}
          >
            Pin storyline
          </Button>
        </Stack>
      </Paper>

      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardHeader
          title='System intelligence'
          subheader='Global corpus status & last collection by source (orchestrator)'
        />
        <CardContent>
          {initialLoad ? (
            <Skeleton variant='rectangular' height={120} />
          ) : (
            <>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {ccStatus && (
                  <>
                    <Chip size='small' label={`Contexts: ${ccStatus.contexts}`} />
                    <Chip
                      size='small'
                      label={`Entity Profiles: ${ccStatus.entity_profiles}`}
                    />
                    <Chip
                      size='small'
                      label={`Events: ${heroBarEventsStoredCount(ccStatus)}`}
                    />
                  </>
                )}
                {pipelineArticleSelection?.mode && (
                  <Chip
                    size='small'
                    color={
                      pipelineArticleSelection.mode === 'lifo'
                        ? 'warning'
                        : 'success'
                    }
                    variant='outlined'
                    title={
                      pipelineArticleSelection.sql_created_at
                        ? `SQL ORDER BY created_at ${pipelineArticleSelection.sql_created_at} (PIPELINE_ARTICLE_SELECTION_ORDER=${pipelineArticleSelection.order_env ?? '—'})`
                        : undefined
                    }
                    label={
                      pipelineArticleSelection.mode === 'lifo'
                        ? 'Batch order: LIFO (newest first)'
                        : 'Batch order: FIFO (oldest first)'
                    }
                  />
                )}
              </Box>
              <Typography variant='body2' color='text.secondary' gutterBottom>
                Collection
              </Typography>
              {Object.keys(lastCollectionTimes).length === 0 ? (
                <Typography variant='caption' color='text.secondary'>
                  No collection times yet.
                </Typography>
              ) : (
                <List dense disablePadding>
                  {Object.entries(lastCollectionTimes).map(([source, time]) => (
                    <ListItemText
                      key={source}
                      primary={source}
                      secondary={
                        time ? new Date(time).toLocaleString() : '—'
                      }
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  ))}
                </List>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {error && (
        <Alert severity='warning' sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {overviewLoadFailed && (overview?.error as string) && (
        <Alert severity='error' sx={{ mb: 2 }}>
          Could not load monitoring overview (health + activity). The API may be down,
          blocked by a proxy, or timing out.{' '}
          <strong>{String((overview?.error as string) || '').slice(0, 200)}</strong>
        </Alert>
      )}

      {/* Connection status */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        System health & connection status
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Card variant='outlined' sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <ApiIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {initialLoad ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(
                  overviewLoadFailed
                    ? 'error'
                    : (apiStatus ?? (overview?.success ? 'ok' : undefined)),
                  overviewLoadFailed ? 'API (no response)' : 'API'
                )
              )}
            </Box>
            <Typography variant='caption' color='text.secondary'>
              Backend API
            </Typography>
          </CardContent>
        </Card>
        <Card variant='outlined' sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <StorageIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {initialLoad ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(
                  overviewLoadFailed ? 'not_loaded' : dbStatus,
                  'Database'
                )
              )}
            </Box>
            <Typography variant='caption' color='text.secondary'>
              PostgreSQL
            </Typography>
          </CardContent>
        </Card>
        <Card variant='outlined' sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <PublicIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {initialLoad ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(
                  overviewLoadFailed ? 'not_loaded' : wsStatus,
                  'Web server'
                )
              )}
            </Box>
            <Typography variant='caption' color='text.secondary'>
              Frontend / proxy
            </Typography>
            {wsStatus !== 'ok' &&
              wsStatus !== 'healthy' &&
              (webserver?.error as string) && (
                <Typography
                  variant='caption'
                  display='block'
                  color='error.main'
                  sx={{ mt: 0.5 }}
                >
                  {(webserver?.error as string).slice(0, 60)}
                </Typography>
              )}
          </CardContent>
        </Card>
      </Box>

      {/* Current activities */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Current activity
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {initialLoad && currentActivities.length === 0 ? (
            <Skeleton
              variant='rectangular'
              height={60}
              sx={{ borderRadius: 1 }}
            />
          ) : overviewLoadFailed ? (
            <Typography color='text.secondary' variant='body2'>
              Current activity could not be loaded — same failure as monitoring
              overview above (often network, CORS, or API URL).
            </Typography>
          ) : currentActivities.length === 0 ? (
            <Typography color='text.secondary' variant='body2'>
              No background tasks running right now. The system will show items
              like &quot;Running RSS collection&quot; or &quot;Processing
              storyline X&quot; when work is in progress.
            </Typography>
          ) : (
            <List dense disablePadding>
              {currentActivities.map((a, i) => {
                const runEst = activityRunEstimateSecondary(a);
                return (
                  <ListItem
                    key={(a.id as string) || i}
                    disablePadding
                    sx={{ py: 0.5 }}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      <RefreshIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 1,
                            width: '100%',
                            pr: 0.5,
                          }}
                        >
                          <Typography
                            variant='body2'
                            component='span'
                            sx={{ minWidth: 0 }}
                          >
                            {(a.message as string) || 'Working…'}
                          </Typography>
                          <Chip
                            size='small'
                            variant='outlined'
                            label={`×${
                              typeof a.running_instances === 'number'
                                ? a.running_instances
                                : 1
                            }`}
                            sx={{
                              flexShrink: 0,
                              height: 22,
                              '& .MuiChip-label': {
                                px: 0.75,
                                py: 0,
                                fontSize: '0.7rem',
                              },
                            }}
                          />
                        </Box>
                      }
                      secondary={
                        <span>
                          {a.started_at ? timeAgo(a.started_at as string) : '—'}
                          {runEst ? (
                            <>
                              {' · '}
                              <Box
                                component='span'
                                sx={{
                                  color: a.exceeded_typical_run
                                    ? 'warning.dark'
                                    : 'text.secondary',
                                }}
                              >
                                {runEst}
                              </Box>
                            </>
                          ) : null}
                        </span>
                      }
                      secondaryTypographyProps={{
                        component: 'div',
                        variant: 'caption',
                      }}
                    />
                  </ListItem>
                );
              })}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Recent activity */}
      {recentActivities.length > 0 && (
        <>
          <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
            Recent activity
          </Typography>
          <Card variant='outlined' sx={{ mb: 3 }}>
            <CardContent sx={{ py: 1.5 }}>
              <List dense disablePadding>
                {recentActivities.slice(0, 10).map((a, i) => (
                  <ListItem
                    key={(a.id as string) || i}
                    disablePadding
                    sx={{ py: 0.5 }}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {(a.success as boolean) !== false ? (
                        <CheckCircleOutlineIcon
                          sx={{ color: 'success.main', fontSize: 20 }}
                        />
                      ) : (
                        <ErrorOutlineIcon
                          sx={{ color: 'error.main', fontSize: 20 }}
                        />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={(a.message as string) || '—'}
                      secondary={
                        a.completed_at
                          ? timeAgo(a.completed_at as string)
                          : null
                      }
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </>
      )}

      {/* Processing pulse: dimension throughput + phase run history (DB + automation_run_history) */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 0.5 }}>
        Processing pulse (7-day window)
      </Typography>
      <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
        <strong>Phase queue (three numbers):</strong> (1){' '}
        <strong>Unprocessed rows</strong> — database records still waiting for that phase. (2){' '}
        <strong>Rows per run (est.)</strong> — how many of those rows each scheduled run is{' '}
        <em>modeled</em> to take from the queue (from backlog_metrics; default 1 for unknown phases via{' '}
        <code style={{ fontSize: '0.85em' }}>BACKLOG_METRICS_DEFAULT_BATCH_SIZE</code>). (3){' '}
        <strong>Runs to clear (est.)</strong> —{' '}
        <code style={{ fontSize: '0.85em' }}>ceil(unprocessed ÷ rows per run)</code>;{' '}
        <strong>&gt; 1</strong> means you need more than one run to drain today&apos;s queue. If rows
        per run is 0 (no row-batch model for that phase), runs to clear shows —. <strong>Runs</strong> count{' '}
        <code style={{ fontSize: '0.85em' }}>automation_run_history</code> rows; for{' '}
        <strong>claim_extraction</strong> with drain, one row is recorded per completed batch (not one per
        scheduler task). <strong>Pass %</strong> ={' '}
        <code style={{ fontSize: '0.85em' }}>100 × successes ÷ completions</code> in the window; SQL
        treats non-TRUE <code style={{ fontSize: '0.85em' }}>success</code> (FALSE or NULL) as not passed —
        a sample proportion, not a confidence interval. Chip arrows compare the last hour to a baseline
        rate (see tooltips; heuristic only). Dimension chips are SQL throughputs, not mutually exclusive
        pipeline stages.
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {processingPulse?.success && processingPulse.data ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {processingPulse.data.pending_metrics_included === false && (
                <Alert severity='info' sx={{ py: 0.5 }}>
                  Per-phase <strong>Unprocessed rows</strong> use a fast path (skips heavy backlog counts
                  so proxies do not close the connection). Throughput chips and run counts still reflect the
                  last 7 days. For queue depths and ETAs, call{' '}
                  <code style={{ fontSize: '0.85em' }}>GET /api/system_monitoring/backlog_status</code>.
                </Alert>
              )}
              <Typography variant='caption' color='text.secondary'>
                Generated{' '}
                {processingPulse.data.generated_at_utc
                  ? shortLocalDateTime(processingPulse.data.generated_at_utc)
                  : '—'}{' '}
                (UTC clock)
              </Typography>
              <Box>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.75 }}>
                  Pipeline throughput ticker
                </Typography>
                <Stack spacing={1} alignItems='stretch'>
                  {(processingPulse.data.dimensions ?? []).map((d, i) => {
                    const t = pulseTrendSymbol(
                      d.last_1h ?? 0,
                      d.last_24h ?? 0
                    );
                    const bl =
                      d.backlog != null ? `backlog ${formatPulseCount(d.backlog)} · ` : '';
                    return (
                      <Chip
                        key={d.id || i}
                        size='small'
                        variant='outlined'
                        sx={{
                          borderColor: 'primary.light',
                          height: 'auto',
                          alignSelf: 'stretch',
                          '& .MuiChip-label': {
                            px: 1,
                            py: 0.75,
                            whiteSpace: 'normal',
                            display: 'block',
                            textAlign: 'left',
                          },
                        }}
                        label={`${t.sym} ${d.label || d.id} · 1h ${formatPulseCount(d.last_1h)} · 24h ${formatPulseCount(d.last_24h)} · 7d ${formatPulseCount(d.last_7d)}`}
                        title={`${t.title}\n${d.label}\n${bl}1h ${d.last_1h ?? '—'} · 24h ${d.last_24h ?? '—'} · 7d ${d.last_7d ?? '—'}`}
                      />
                    );
                  })}
                </Stack>
              </Box>
              <Divider />
              <Box>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.75 }}>
                  Data-plane row backlogs (same SQL family as backlog ETAs)
                </Typography>
                <Table size='small' sx={{ '& td': { py: 0.5 } }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>Queue</TableCell>
                      <TableCell align='right'>Rows waiting</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(processingPulse.data.dimensions ?? [])
                      .filter(d => d.backlog != null && d.backlog > 0)
                      .map(d => (
                        <TableRow key={d.id}>
                          <TableCell>{d.label || d.id}</TableCell>
                          <TableCell align='right'>
                            {formatPulseCount(d.backlog ?? 0)}
                          </TableCell>
                        </TableRow>
                      ))}
                    {(processingPulse.data.dimensions ?? []).every(
                      d => d.backlog == null || d.backlog <= 0
                    ) && (
                      <TableRow>
                        <TableCell colSpan={2}>
                          <Typography variant='body2' color='text.secondary'>
                            No positive dimension backlogs in this snapshot (or all at zero).
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </Box>
              <Divider />
              <Box>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.75 }}>
                  Automation phases — unprocessed DB rows, modeled rows per run, estimated runs to clear the
                  queue; then pass/fail when the phase completes
                </Typography>
                <Table size='small' sx={{ '& td': { py: 0.5 } }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>Phase</TableCell>
                      <TableCell
                        align='right'
                        title='Count of database records not yet processed for this phase (pending queue)'
                      >
                        Unprocessed rows
                      </TableCell>
                      <TableCell
                        align='right'
                        title='Modeled number of queue rows each scheduled run takes (backlog_metrics; not measured from last run)'
                      >
                        Rows/run (est.)
                      </TableCell>
                      <TableCell
                        align='right'
                        title='ceil(unprocessed ÷ rows per run). How many phase runs to drain the queue; >1 means backlog needs multiple runs'
                      >
                        Runs to clear (est.)
                      </TableCell>
                      <TableCell align='right'>Runs 1h</TableCell>
                      <TableCell align='right'>Runs 24h</TableCell>
                      <TableCell align='right'>Runs 7d</TableCell>
                      <TableCell align='right'>Pass 24h</TableCell>
                      <TableCell align='right'>Fail 24h</TableCell>
                      <TableCell align='right'>Pass % 24h</TableCell>
                      <TableCell align='right'>Pass % 7d</TableCell>
                      <TableCell align='right'>Avg s</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(
                      processingPulse.data.phase_dashboard ??
                      processingPulse.data.phases ??
                      []
                    )
                      .slice(0, 40)
                      .map(p => (
                        <TableRow key={p.phase_name}>
                          <TableCell>{p.phase_name}</TableCell>
                          <TableCell align='right'>
                            {formatPulseCount(p.pending_records ?? 0)}
                          </TableCell>
                          <TableCell align='right'>
                            {formatPulseCount(p.estimated_batch_per_run ?? 0)}
                          </TableCell>
                          <TableCell align='right'>
                            {p.batches_to_drain == null ? (
                              '—'
                            ) : (p.batches_to_drain ?? 0) > 1 ? (
                              <Typography
                                component='span'
                                variant='body2'
                                color='warning.main'
                              >
                                {formatPulseCount(p.batches_to_drain)}
                              </Typography>
                            ) : (
                              formatPulseCount(p.batches_to_drain)
                            )}
                          </TableCell>
                          <TableCell align='right'>{p.runs_1h ?? 0}</TableCell>
                          <TableCell align='right'>{p.runs_24h ?? 0}</TableCell>
                          <TableCell align='right'>{p.runs_7d ?? 0}</TableCell>
                          <TableCell align='right'>{p.successes_24h ?? 0}</TableCell>
                          <TableCell align='right'>
                            {(p.failures_24h ?? 0) > 0 ? (
                              <Typography
                                component='span'
                                variant='body2'
                                color='error.main'
                              >
                                {p.failures_24h}
                              </Typography>
                            ) : (
                              '0'
                            )}
                          </TableCell>
                          <TableCell align='right'>
                            {p.pass_rate_24h != null ? `${p.pass_rate_24h}%` : '—'}
                          </TableCell>
                          <TableCell align='right'>
                            {p.pass_rate_7d != null ? `${p.pass_rate_7d}%` : '—'}
                          </TableCell>
                          <TableCell align='right'>
                            {p.avg_duration_sec_24h != null
                              ? Math.round(p.avg_duration_sec_24h)
                              : '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
                {(processingPulse.data.phase_dashboard ?? processingPulse.data.phases ?? [])
                  .length > 40 && (
                  <Typography variant='caption' color='text.secondary' sx={{ mt: 0.5, display: 'block' }}>
                    Showing 40 rows sorted by pending+backlog, then 7d runs.
                  </Typography>
                )}
              </Box>
              <Divider />
              <Box>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.5 }}>
                  Hourly activity (last 72h, sparse — for charts / exports)
                </Typography>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.5 }}>
                  {processingPulse.data.hourly_phase_tick_bucket_count ??
                    (processingPulse.data.hourly_phase_ticks ?? []).length}{' '}
                  bucket rows (72h)
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.75 }}>
                  GPU / VRAM (hourly averages, last 72h)
                </Typography>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 1 }}>
                  Samples from <code style={{ fontSize: '0.85em' }}>nvidia-smi</code> (throttled). History
                  fills as Monitor and health endpoints run. Apply migration{' '}
                  <code style={{ fontSize: '0.85em' }}>209_gpu_metric_samples.sql</code> if the chart stays
                  empty.
                </Typography>
                {gpuMetricHistory?.success === false && (
                  <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
                    {gpuMetricHistory?.error || 'GPU history unavailable.'}
                  </Typography>
                )}
                {gpuChartRows.length > 0 ? (
                  <Box sx={{ width: '100%', height: 280 }}>
                    <ResponsiveContainer>
                      <LineChart
                        data={gpuChartRows}
                        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray='3 3' />
                        <XAxis dataKey='label' tick={{ fontSize: 11 }} interval='preserveStartEnd' />
                        <YAxis
                          yAxisId='pct'
                          domain={[0, 100]}
                          tick={{ fontSize: 11 }}
                          label={{ value: '%', angle: 0, position: 'insideLeft' }}
                        />
                        <YAxis
                          yAxisId='temp'
                          orientation='right'
                          domain={[0, 100]}
                          tick={{ fontSize: 11 }}
                          label={{ value: '°C', angle: 0, position: 'insideRight' }}
                        />
                        <Tooltip />
                        <Legend />
                        <Line
                          yAxisId='pct'
                          type='monotone'
                          dataKey='util'
                          name='GPU util %'
                          stroke='#1976d2'
                          dot={false}
                          strokeWidth={2}
                          connectNulls
                        />
                        <Line
                          yAxisId='pct'
                          type='monotone'
                          dataKey='vram'
                          name='VRAM %'
                          stroke='#ed6c02'
                          dot={false}
                          strokeWidth={2}
                          connectNulls
                        />
                        <Line
                          yAxisId='temp'
                          type='monotone'
                          dataKey='temp'
                          name='Temp °C'
                          stroke='#2e7d32'
                          dot={false}
                          strokeWidth={1}
                          connectNulls
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </Box>
                ) : (
                  <Typography variant='body2' color='text.secondary'>
                    No hourly GPU samples yet — open Monitor for a few minutes after migration 209, or check
                    that <code style={{ fontSize: '0.85em' }}>nvidia-smi</code> works on the API host.
                  </Typography>
                )}
              </Box>
            </Box>
          ) : initialLoad ? (
            <Skeleton variant='rectangular' height={120} sx={{ borderRadius: 1 }} />
          ) : (
            <Typography color='text.secondary' variant='body2'>
              {processingPulse?.error || 'Processing pulse not available.'}
            </Typography>
          )}
        </CardContent>
      </Card>

      <Divider sx={{ my: 2 }} />

      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Pipeline status
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader
            title='Traces and processing'
            subheader='Orchestrator pipeline'
            avatar={<ScheduleIcon />}
          />
          <CardContent>
            {initialLoad && !pipeline?.data ? (
              <Skeleton variant='rectangular' height={80} />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    size='small'
                    color={pipelineStatusColor}
                    label={pipelineStatus ?? '—'}
                  />
                  {typeof pipelineData?.success_rate === 'number' && (
                    <Typography variant='body2' color='text.secondary'>
                      Success rate: {pipelineData.success_rate}%
                    </Typography>
                  )}
                </Box>
                <Typography variant='caption' color='text.secondary'>
                  Articles processed:{' '}
                  {String(pipelineData?.articles_processed ?? '—')} · Analyzed:{' '}
                  {String(pipelineData?.articles_analyzed ?? '—')} · Recent (1h):{' '}
                  {String(pipelineData?.recent_articles ?? '—')}
                </Typography>
                {pipeline?.success === false && pipeline.error && (
                  <Typography variant='caption' color='error' display='block'>
                    {pipeline.error}
                  </Typography>
                )}
                {pipelineData?.active_traces != null &&
                  Number(pipelineData.active_traces) > 0 && (
                    <Typography variant='caption' color='info.main'>
                      Active traces: {String(pipelineData.active_traces)}
                    </Typography>
                  )}
              </Box>
            )}
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader title='Active domains' subheader='Registry / nav' />
          <CardContent>
            <Typography variant='body2'>
              {getDomainKeysList().join(', ') || '—'}
            </Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Run phase (optional) */}
      {apiService.triggerPhase && (
        <Box sx={{ mb: 3 }}>
          <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
            Run phase now
          </Typography>
          <Card variant='outlined'>
            <CardContent sx={{ py: 1.5 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                <FormControl size='small' sx={{ minWidth: 220 }}>
                  <InputLabel>Phase</InputLabel>
                  <Select
                    value={triggerPhaseName}
                    label='Phase'
                    onChange={e => setTriggerPhaseName(e.target.value)}
                  >
                    <MenuItem value=''>Select…</MenuItem>
                    {runPhaseOptions.map(name => (
                      <MenuItem key={name} value={name}>
                        {name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  size='small'
                  variant='contained'
                  startIcon={<PlayArrowIcon />}
                  onClick={handleTriggerPhase}
                  disabled={!triggerPhaseName || triggering}
                >
                  {triggering ? 'Requesting…' : 'Run now'}
                </Button>
              </Box>
              {triggerResult && (
                <Box sx={{ mt: 1.5 }}>
                  <Alert
                    severity={triggerResult.success ? 'success' : 'error'}
                    onClose={() => setTriggerResult(null)}
                  >
                    {triggerResult.message}
                  </Alert>
                  {triggerResult.success && triggerResult.warning && (
                    <Alert
                      severity='warning'
                      sx={{ mt: 1 }}
                      onClose={() => setTriggerResult(null)}
                    >
                      {triggerResult.warning}
                    </Alert>
                  )}
                </Box>
              )}
              <Typography
                variant='caption'
                color='text.secondary'
                sx={{ display: 'block', mt: 1 }}
              >
                Enqueues the phase; it will appear under Current activity when
                it runs. Running phases out of order may process incomplete data
                (e.g. run collection_cycle before analysis phases).
              </Typography>
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
}
