/**
 * Monitor — live ops console: status, now, pulse, actions.
 * Historical trends / GPU / infra charts live in Homelab Grafana (Open Grafana link).
 * SQL explorer and Work executed stay on separate routes.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Card,
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
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import apiService from '@/services/apiService';
import { heroBarEventsStoredCount } from '@/services/api/contextCentric';
import { getDefaultDomainKey } from '@/utils/domainHelper';
import { useShellStatus } from '@/contexts/ShellStatusContext';
import { getGrafanaOpsUrl } from '@/config/grafanaConfig';

/** Poll interval for live Monitor bits (overview + pulse together). */
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

type ProcessingPulsePhase = {
  phase_name?: string;
  pending_records?: number;
  batches_to_drain?: number | null;
  estimated_batch_per_run?: number;
  runs_1h?: number;
  runs_24h?: number;
  successes_24h?: number;
  failures_24h?: number;
  pass_rate_24h?: number | null;
  avg_duration_sec_24h?: number | null;
};

type ProcessingPulseState = {
  success?: boolean;
  data?: {
    generated_at_utc?: string;
    pending_metrics_included?: boolean;
    pending_metrics_as_of_utc?: string;
    phase_dashboard?: ProcessingPulsePhase[];
    phases?: ProcessingPulsePhase[];
  };
  error?: string;
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

/** Keep backlog_metrics columns when a fast-path poll refreshes throughput/run counts. */
function mergeProcessingPulseWithCachedPending(
  fast: ProcessingPulseState,
  cached: ProcessingPulseState | null
): ProcessingPulseState {
  if (!fast?.data) return fast;
  if (fast.data.pending_metrics_included) return fast;
  if (!cached?.data?.pending_metrics_included) return fast;

  const cachedPhases = cached.data.phase_dashboard ?? cached.data.phases ?? [];
  const cachedByPhase = new Map(
    cachedPhases
      .filter(p => typeof p.phase_name === 'string' && p.phase_name.length > 0)
      .map(p => [p.phase_name as string, p])
  );
  if (cachedByPhase.size === 0) return fast;

  const fastPhases = fast.data.phase_dashboard ?? fast.data.phases ?? [];
  const mergedPhases = fastPhases.map(p => {
    const name = p.phase_name;
    if (!name) return p;
    const c = cachedByPhase.get(name);
    if (!c) return p;
    return {
      ...p,
      pending_records: c.pending_records,
      estimated_batch_per_run: c.estimated_batch_per_run,
      batches_to_drain: c.batches_to_drain,
    };
  });

  return {
    ...fast,
    data: {
      ...fast.data,
      phase_dashboard: mergedPhases,
      phases: mergedPhases,
      pending_metrics_included: true,
      pending_metrics_as_of_utc:
        cached.data.pending_metrics_as_of_utc ?? cached.data.generated_at_utc,
    },
  };
}

export default function MonitorPage() {
  const { domain: routeDomain } = useParams<{ domain: string }>();
  const navDomain = routeDomain ?? getDefaultDomainKey();
  const grafanaUrl = getGrafanaOpsUrl();
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
  const [processingPulse, setProcessingPulse] =
    useState<ProcessingPulseState | null>(null);
  const [initialLoad, setInitialLoad] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggerPhaseName, setTriggerPhaseName] = useState<string>('');
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{
    success: boolean;
    message: string;
    warning?: string;
  } | null>(null);
  const { ctxStatus: ccStatus } = useShellStatus();
  const [pipelineArticleSelection, setPipelineArticleSelection] = useState<{
    mode?: string;
    label?: string;
    sql_created_at?: string;
    order_env?: string;
  } | null>(null);
  const [automationRunning, setAutomationRunning] = useState<boolean | null>(
    null
  );
  const [pendingMetricsLoading, setPendingMetricsLoading] = useState(false);

  const refreshOverview = useCallback(async () => {
    const ov = await apiService.getMonitoringOverview();
    setOverview(ov ?? null);
    return ov;
  }, []);

  const refreshHeavyPanels = useCallback(async () => {
    const results = await Promise.allSettled([
      apiService.getPipelineStatus(),
      apiService.getProcessingProgress({ includePendingMetrics: false }),
      apiService.getAutomationStatus().catch(() => null),
    ]);
    const settledErr = (r: PromiseSettledResult<unknown>, label: string) =>
      r.status === 'rejected'
        ? {
            success: false as const,
            error: `${label}: ${(r.reason as Error)?.message ?? 'failed'}`,
          }
        : null;
    const pipe =
      results[0].status === 'fulfilled'
        ? results[0].value
        : settledErr(results[0], 'pipeline_status');
    const pulse =
      results[1].status === 'fulfilled'
        ? results[1].value
        : settledErr(results[1], 'processing_progress');
    const autoEnvelope = results[2].status === 'fulfilled' ? results[2].value : null;
    setPipeline(pipe ?? null);
    if (pulse && typeof pulse === 'object' && 'success' in pulse) {
      setProcessingPulse(prev =>
        mergeProcessingPulseWithCachedPending(pulse as ProcessingPulseState, prev)
      );
    } else {
      setProcessingPulse(pulse ?? null);
    }
    const autoData = (
      autoEnvelope as {
        data?: {
          running?: boolean;
          is_running?: boolean;
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
    if (autoData) {
      if (typeof autoData.running === 'boolean') {
        setAutomationRunning(autoData.running);
      } else if (typeof autoData.is_running === 'boolean') {
        setAutomationRunning(autoData.is_running);
      } else {
        setAutomationRunning(true);
      }
    }
  }, []);

  const fetchPendingMetrics = useCallback(async () => {
    setPendingMetricsLoading(true);
    try {
      const pulse = await apiService.getProcessingProgress({
        includePendingMetrics: true,
      });
      if (pulse?.success && pulse.data) {
        setProcessingPulse({
          ...pulse,
          data: {
            ...pulse.data,
            pending_metrics_as_of_utc: pulse.data.generated_at_utc,
          },
        });
      }
    } catch {
      /* getProcessingProgress returns { success: false } on failure */
    } finally {
      setPendingMetricsLoading(false);
    }
  }, []);

  const refreshMonitor = useCallback(async () => {
    await refreshOverview();
    void refreshHeavyPanels();
  }, [refreshOverview, refreshHeavyPanels]);

  useEffect(() => {
    let cancelled = false;
    let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;
    let pollTick = 0;

    void (async () => {
      setInitialLoad(true);
      setError(null);
      try {
        const overviewPromise = refreshOverview().finally(() => {
          if (!cancelled) setInitialLoad(false);
        });
        void refreshHeavyPanels();
        await overviewPromise;
        if (!cancelled) void fetchPendingMetrics();
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setInitialLoad(false);
      }
      if (cancelled) return;

      const schedulePoll = () => {
        pollTimeoutId = setTimeout(() => {
          void (async () => {
            if (cancelled) return;
            try {
              await refreshOverview();
              void refreshHeavyPanels();
              pollTick += 1;
              if (pollTick % 4 === 0) void fetchPendingMetrics();
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
  }, [refreshOverview, refreshHeavyPanels, fetchPendingMetrics]);

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
        setTimeout(() => {
          void refreshMonitor();
          void fetchPendingMetrics();
        }, 6000);
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
      />
    );
  };

  const phaseRows =
    processingPulse?.data?.phase_dashboard ??
    processingPulse?.data?.phases ??
    [];

  return (
    <Box>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        alignItems={{ sm: 'baseline' }}
        justifyContent='space-between'
        gap={1}
        sx={{ mb: 1 }}
      >
        <Typography variant='h5' sx={{ fontWeight: 600 }}>
          Monitor
        </Typography>
        <Typography variant='body2' color='text.secondary'>
          Live ops · history in Grafana ·{' '}
          <Link
            component={RouterLink}
            to={`/${navDomain}/monitor/sql-explorer`}
            underline='hover'
          >
            SQL explorer
          </Link>
        </Typography>
      </Stack>

      {error && (
        <Alert severity='warning' sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {overviewLoadFailed && (overview?.error as string) && (
        <Alert severity='error' sx={{ mb: 2 }}>
          Could not load monitoring overview.{' '}
          <strong>
            {String((overview?.error as string) || '').slice(0, 200)}
          </strong>
        </Alert>
      )}

      {/* 1. Status strip */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Status
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
          {initialLoad ? (
            <Skeleton variant='rectangular' height={40} />
          ) : (
            <Stack direction='row' flexWrap='wrap' gap={1} alignItems='center'>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <ApiIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                {statusChip(
                  overviewLoadFailed
                    ? 'error'
                    : (apiStatus ?? (overview?.success ? 'ok' : undefined)),
                  overviewLoadFailed ? 'API (no response)' : 'API'
                )}
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <StorageIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                {statusChip(
                  overviewLoadFailed ? 'not_loaded' : dbStatus,
                  'Database'
                )}
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <PublicIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                {statusChip(
                  overviewLoadFailed ? 'not_loaded' : wsStatus,
                  'Web'
                )}
              </Box>
              <Chip
                size='small'
                variant='outlined'
                color={
                  automationRunning === false
                    ? 'error'
                    : automationRunning === true
                      ? 'success'
                      : 'default'
                }
                label={
                  automationRunning === false
                    ? 'Automation stopped'
                    : automationRunning === true
                      ? 'Automation running'
                      : 'Automation …'
                }
              />
              {pipelineStatus && (
                <Chip
                  size='small'
                  variant='outlined'
                  color={
                    pipelineStatus === 'error'
                      ? 'error'
                      : pipelineStatus === 'running'
                        ? 'info'
                        : pipelineStatus === 'healthy'
                          ? 'success'
                          : 'default'
                  }
                  label={`Pipeline: ${pipelineStatus}`}
                />
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
                      ? `SQL ORDER BY created_at ${pipelineArticleSelection.sql_created_at}`
                      : undefined
                  }
                  label={
                    pipelineArticleSelection.mode === 'lifo'
                      ? 'Batch: LIFO'
                      : 'Batch: FIFO'
                  }
                />
              )}
              {ccStatus && (
                <>
                  <Chip size='small' label={`Contexts ${ccStatus.contexts}`} />
                  <Chip
                    size='small'
                    label={`Entities ${ccStatus.entity_profiles}`}
                  />
                  <Chip
                    size='small'
                    label={`Events ${heroBarEventsStoredCount(ccStatus)}`}
                  />
                </>
              )}
              {wsStatus !== 'ok' &&
                wsStatus !== 'healthy' &&
                (webserver?.error as string) && (
                  <Typography variant='caption' color='error.main'>
                    {(webserver?.error as string).slice(0, 80)}
                  </Typography>
                )}
            </Stack>
          )}
        </CardContent>
      </Card>

      {/* 2. Now */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Now
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          <Typography
            variant='caption'
            color='text.secondary'
            display='block'
            sx={{ mb: 1 }}
          >
            Current activity
          </Typography>
          {initialLoad && currentActivities.length === 0 ? (
            <Skeleton variant='rectangular' height={48} sx={{ borderRadius: 1 }} />
          ) : overviewLoadFailed ? (
            <Typography color='text.secondary' variant='body2'>
              Current activity could not be loaded.
            </Typography>
          ) : currentActivities.length === 0 ? (
            <Typography color='text.secondary' variant='body2'>
              No background tasks running right now.
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
                          }}
                        >
                          <Typography variant='body2' component='span'>
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
                            sx={{ height: 22 }}
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

          {recentActivities.length > 0 && (
            <>
              <Typography
                variant='caption'
                color='text.secondary'
                display='block'
                sx={{ mt: 2, mb: 1 }}
              >
                Recent
              </Typography>
              <List dense disablePadding>
                {recentActivities.slice(0, 8).map((a, i) => (
                  <ListItem
                    key={(a.id as string) || i}
                    disablePadding
                    sx={{ py: 0.25 }}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {(a.success as boolean) !== false ? (
                        <CheckCircleOutlineIcon
                          sx={{ color: 'success.main', fontSize: 18 }}
                        />
                      ) : (
                        <ErrorOutlineIcon
                          sx={{ color: 'error.main', fontSize: 18 }}
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
            </>
          )}
        </CardContent>
      </Card>

      {/* 3. Pulse */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 0.5 }}>
        Pulse
      </Typography>
      <Typography
        variant='caption'
        color='text.secondary'
        display='block'
        sx={{ mb: 1 }}
      >
        Phase queues and recent pass/fail. Highlighted when fails &gt; 0 or runs
        to clear &gt; 1. Trends and GPU history → Grafana.
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {processingPulse?.success && processingPulse.data ? (
            <Box>
              {processingPulse.data.pending_metrics_included === false && (
                <Alert severity='info' sx={{ py: 0.5, mb: 1.5 }}>
                  {pendingMetricsLoading ? (
                    <>Loading unprocessed row counts…</>
                  ) : (
                    <>
                      Queue depths load in the background (~every minute). Run
                      counts still refresh every 15s.
                    </>
                  )}
                </Alert>
              )}
              {processingPulse.data.pending_metrics_as_of_utc && (
                <Typography
                  variant='caption'
                  color='text.secondary'
                  display='block'
                  sx={{ mb: 1 }}
                >
                  Queues as of{' '}
                  {shortLocalDateTime(
                    processingPulse.data.pending_metrics_as_of_utc
                  )}
                </Typography>
              )}
              <Table size='small' sx={{ '& td': { py: 0.5 } }}>
                <TableHead>
                  <TableRow>
                    <TableCell>Phase</TableCell>
                    <TableCell align='right'>Pending</TableCell>
                    <TableCell align='right'>Runs to clear</TableCell>
                    <TableCell align='right'>Fail 24h</TableCell>
                    <TableCell align='right'>Runs 24h</TableCell>
                    <TableCell align='right'>Pass % 24h</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {phaseRows.slice(0, 40).map(p => {
                    const stuck =
                      (p.failures_24h ?? 0) > 0 ||
                      (p.batches_to_drain != null && p.batches_to_drain > 1);
                    return (
                      <TableRow
                        key={p.phase_name}
                        sx={
                          stuck
                            ? { bgcolor: 'action.hover' }
                            : undefined
                        }
                      >
                        <TableCell>{p.phase_name}</TableCell>
                        <TableCell align='right'>
                          {formatPulseCount(p.pending_records ?? 0)}
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
                        <TableCell align='right'>{p.runs_24h ?? 0}</TableCell>
                        <TableCell align='right'>
                          {p.pass_rate_24h != null
                            ? `${p.pass_rate_24h}%`
                            : '—'}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              {phaseRows.length > 40 && (
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ mt: 0.5, display: 'block' }}
                >
                  Showing 40 phases.
                </Typography>
              )}
            </Box>
          ) : initialLoad ? (
            <Skeleton
              variant='rectangular'
              height={120}
              sx={{ borderRadius: 1 }}
            />
          ) : (
            <Typography color='text.secondary' variant='body2'>
              {processingPulse?.error || 'Processing pulse not available.'}
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* 4. Actions */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Actions
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={2}
            alignItems={{ sm: 'center' }}
            flexWrap='wrap'
            useFlexGap
          >
            {apiService.triggerPhase && (
              <>
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
                  {triggering ? 'Requesting…' : 'Run phase now'}
                </Button>
              </>
            )}
            {grafanaUrl ? (
              <Button
                size='small'
                variant='outlined'
                startIcon={<OpenInNewIcon />}
                href={grafanaUrl}
                target='_blank'
                rel='noopener noreferrer'
              >
                Open Grafana
              </Button>
            ) : (
              <Typography variant='caption' color='text.secondary'>
                Set <code>VITE_NEWS_INTEL_GRAFANA_URL</code> (or{' '}
                <code>NEWS_INTEL_GRAFANA_URL</code> in docs) for the Homelab NI
                Ops deep link.
              </Typography>
            )}
          </Stack>
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
            Phase trigger enqueues work on AutomationManager. Running phases out
            of order may process incomplete data.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
