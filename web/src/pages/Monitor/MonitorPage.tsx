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
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import ApiIcon from '@mui/icons-material/Api';
import StorageIcon from '@mui/icons-material/Storage';
import PublicIcon from '@mui/icons-material/Public';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import apiService from '@/services/apiService';
import { safeServiceCall } from '@/utils/safeServiceCall';
import { getDefaultDomainKey, getDomainKeysList } from '@/utils/domainHelper';

const POLL_INTERVAL_MS = 4500;
/**
 * Processing pulse: light polls (no backlog_metrics) every tick for fresh run/pass + dimensions;
 * full polls (unprocessed row counts) every N ticks to limit DB load and proxy timeouts.
 * N × POLL_INTERVAL_MS ≈ 31.5s at defaults.
 */
const PULSE_FULL_PENDING_EVERY_N_POLLS = 7;
/** Max parallel Monitor API calls per wave (browser + reverse-proxy friendly; avoids stampedes). */
const MONITOR_FETCH_CONCURRENCY = 2;

/** Run async tasks in waves of `concurrency` to avoid piling simultaneous connections. */
async function runPoolLimit(
  tasks: Array<() => Promise<unknown>>,
  concurrency: number
): Promise<unknown[]> {
  const results: unknown[] = [];
  for (let i = 0; i < tasks.length; i += concurrency) {
    const chunk = await Promise.all(
      tasks.slice(i, i + concurrency).map(fn => fn())
    );
    results.push(...chunk);
  }
  return results;
}

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
  } | null>(null);
  const [processingPulse, setProcessingPulse] = useState<{
    success?: boolean;
      data?: {
      generated_at_utc?: string;
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
      /** False when API skipped backlog_metrics (Monitor default — avoids proxy 504). */
      pending_metrics_included?: boolean;
    };
    error?: string;
  } | null>(null);
  /** Overview (health + current activity) — independent of pipeline so slow pipeline_status cannot blank the page. */
  const [overviewReady, setOverviewReady] = useState(false);
  const [pipelineReady, setPipelineReady] = useState(false);
  /** True while processing_progress request is in flight. */
  const [heavyMonitorPending, setHeavyMonitorPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggerPhaseName, setTriggerPhaseName] = useState<string>('');
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{
    success: boolean;
    message: string;
    warning?: string;
  } | null>(null);

  const loadOverview = useCallback(async () => {
    try {
      const data = await apiService.getMonitoringOverview();
      setOverview(data ?? null);
    } catch (e) {
      setOverview({ success: false, error: (e as Error).message });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;
    let pollTickIndex = 0;
    const svc = apiService as unknown as Record<string, unknown>;

    const load = () => {
      setOverviewReady(false);
      setPipelineReady(false);
      setHeavyMonitorPending(false);
      setError(null);

      /** Stale-while-revalidate: light pulse first (fast), then full counts (heavy). */
      const runPulse = () => {
        setHeavyMonitorPending(true);
        void (async () => {
          await new Promise<void>(resolve => {
            requestAnimationFrame(() => resolve());
          });
          if (cancelled) return;
          const light = await apiService.getProcessingProgress({
            includePendingMetrics: false,
          });
          if (!cancelled) {
            setProcessingPulse(light ?? null);
            setHeavyMonitorPending(false);
          }
          if (cancelled) return;
          const full = await apiService.getProcessingProgress({
            includePendingMetrics: true,
          });
          if (!cancelled) setProcessingPulse(full ?? null);
        })();
      };

      void (async () => {
        try {
          const ov = await apiService.getMonitoringOverview();
          if (!cancelled) setOverview(ov ?? null);
          runPulse();
        } catch (e) {
          if (!cancelled) {
            setError((e as Error).message);
            setOverview({
              success: false,
              error: (e as Error).message,
            });
          }
          runPulse();
        } finally {
          if (!cancelled) setOverviewReady(true);
        }
      })();

      void (async () => {
        const pipe = await safeServiceCall<{
          success?: boolean;
          data?: Record<string, unknown>;
        }>(svc, 'getPipelineStatus');
        if (!cancelled) setPipeline(pipe ?? null);
        if (!cancelled) setPipelineReady(true);
      })();
    };

    /**
     * Poll must not overlap: sequential ticks avoid stacking requests every 4.5s
     * while the pipeline and DB pool are busy.
     */
    const runPollTick = async () => {
      if (cancelled) return;
      pollTickIndex += 1;
      const pulseFullThisTick =
        pollTickIndex % PULSE_FULL_PENDING_EVERY_N_POLLS === 0;
      try {
        await loadOverview();
        if (cancelled) return;
        const [pipeR, pulseR] = await runPoolLimit(
          [
            () => safeServiceCall(svc, 'getPipelineStatus'),
            () =>
              apiService.getProcessingProgress({
                includePendingMetrics: pulseFullThisTick,
              }),
          ],
          MONITOR_FETCH_CONCURRENCY
        );
        if (!cancelled && pipeR) setPipeline(pipeR as typeof pipeline);
        if (!cancelled && pulseR) {
          const p = pulseR as typeof processingPulse;
          if (pulseFullThisTick) {
            if (p?.success && p.data) {
              setProcessingPulse(p);
            }
            /* On timeout/504, keep existing pulse (often last good full + merged light). */
          } else if (p?.success && p.data) {
            setProcessingPulse(prev => {
              if (
                !prev?.success ||
                !prev.data ||
                prev.data.pending_metrics_included !== true
              ) {
                return p;
              }
              const prevByPhase = new Map(
                (
                  prev.data.phase_dashboard ??
                  prev.data.phases ??
                  []
                ).map(row => [row.phase_name, row])
              );
              const rows = (
                p.data.phase_dashboard ??
                p.data.phases ??
                []
              ).map(row => {
                const phase = row.phase_name;
                const old =
                  phase != null ? prevByPhase.get(phase) : undefined;
                if (!old) return row;
                return {
                  ...row,
                  pending_records: old.pending_records,
                  estimated_batch_per_run: old.estimated_batch_per_run,
                  batches_to_drain: old.batches_to_drain,
                };
              });
              return {
                ...p,
                data: {
                  ...p.data,
                  phase_dashboard: rows,
                  phases: rows,
                  pending_metrics_included: true,
                },
              };
            });
          } else {
            setProcessingPulse(p);
          }
        }
      } catch {
        /* individual safeServiceCall already swallows; loadOverview too */
      }
    };

    const scheduleNextPoll = () => {
      if (cancelled) return;
      pollTimeoutId = setTimeout(() => {
        void (async () => {
          try {
            await runPollTick();
          } finally {
            if (!cancelled) scheduleNextPoll();
          }
        })();
      }, POLL_INTERVAL_MS);
    };

    load();
    if (!cancelled) scheduleNextPoll();

    return () => {
      cancelled = true;
      if (pollTimeoutId !== null) clearTimeout(pollTimeoutId);
    };
  }, [loadOverview]);

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
        loadOverview();
        // Refresh again so Current activity shows "Requested — queued" then "Running..." when the worker starts
        setTimeout(loadOverview, 2500);
        setTimeout(loadOverview, 6000);
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
    overviewReady &&
    overview != null &&
    overview.success === false;

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
              {!overviewReady && !overview ? (
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
              {!overviewReady && !overview ? (
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
              {!overviewReady && !overview ? (
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
          {!overviewReady && currentActivities.length === 0 ? (
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
      <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 0.75 }}>
        Refresh: throughput chips and run/pass columns about every {POLL_INTERVAL_MS / 1000}s;
        <strong> Unprocessed rows</strong> / runs-to-clear about every{' '}
        {(POLL_INTERVAL_MS * PULSE_FULL_PENDING_EVERY_N_POLLS) / 1000}
        s (heavy DB counts), with the last full values kept between those polls.
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
              <Typography variant='caption' color='text.secondary'>
                Generated{' '}
                {processingPulse.data.generated_at_utc
                  ? shortLocalDateTime(processingPulse.data.generated_at_utc)
                  : '—'}{' '}
                (UTC clock)
              </Typography>
              {processingPulse.data.pending_metrics_included === false && (
                <Typography variant='caption' color='text.secondary' display='block'>
                  Per-phase <strong>Unprocessed rows</strong> / <strong>Runs to clear</strong> are not
                  loaded on this view (keeps the request under reverse-proxy timeouts). Runs, pass rates,
                  and ticker chips still update. Full queue SQL is available via{' '}
                  <code style={{ fontSize: '0.85em' }}>GET /api/system_monitoring/backlog_status</code> and
                  automation <strong>pending_counts</strong>.
                </Typography>
              )}
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
            </Box>
          ) : heavyMonitorPending && processingPulse == null ? (
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
            {!pipelineReady && !pipeline?.data ? (
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
