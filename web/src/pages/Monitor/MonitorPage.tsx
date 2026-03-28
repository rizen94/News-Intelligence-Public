/**
 * Monitor — System health, connection status, live activity, and pipeline visibility.
 * Shows API/DB/webserver status, current & recent activity, collection/quality,
 * pipeline status, phase timeline (last run / next due), decision log, and optional phase trigger.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
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
  FormControlLabel,
  Checkbox,
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
import NightsStayIcon from '@mui/icons-material/NightsStay';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import apiService from '@/services/apiService';
import { contextCentricApi } from '@/services/api/contextCentric';
import { safeServiceCall } from '@/utils/safeServiceCall';
import { getDefaultDomainKey, getDomainKeysList } from '@/utils/domainHelper';

const POLL_INTERVAL_MS = 4500;
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

type PhaseRow = {
  name: string;
  last_run: string | null;
  enabled?: boolean;
  phase?: number;
  phase_group_label?: string;
  parallel_group?: string;
  stage_order?: number;
  queued_tasks?: number;
  running_tasks?: number;
  runs_last_60m?: number;
};
type DecisionEntry = {
  decision?: string;
  outcome?: string;
  factors?: Record<string, unknown>;
  timestamp?: string;
};
type DbSession = {
  pid: number;
  user?: string;
  application_name?: string;
  client_addr?: string;
  state?: string;
  wait_event_type?: string | null;
  wait_event?: string | null;
  query_text?: string;
  open_seconds?: number;
  long_running?: boolean;
};

type BacklogPerHourSource =
  | 'avg_4d'
  | 'measured_1h'
  | 'measured_24h'
  | 'measured_2h'
  | 'estimated';

function throughputSourceLabel(src?: BacklogPerHourSource): string {
  switch (src) {
    case 'avg_4d':
      return '4-day workload avg';
    case 'measured_1h':
      return 'measured 1h';
    case 'measured_24h':
      return 'measured 24h';
    case 'measured_2h':
      return 'measured 2h';
    case 'estimated':
      return 'no recent data (estimate)';
    default:
      return '';
  }
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
  const [orchDashboard, setOrchDashboard] = useState<{
    status?: Record<string, unknown>;
    decision_log?: { entries?: DecisionEntry[] };
  } | null>(null);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [pipeline, setPipeline] = useState<{
    success?: boolean;
    data?: Record<string, unknown>;
  } | null>(null);
  const [automation, setAutomation] = useState<{
    success?: boolean;
    data?: {
      phases?: PhaseRow[];
      queue_size?: number;
      is_running?: boolean;
      active_workers?: number;
      phase_workers_configured?: number;
      max_concurrent_tasks?: number;
      automation_background_tasks_active?: number;
      document_pipeline?: {
        pending_extraction?: number;
        extracted_last_24h?: number;
        permanent_failed_total?: number;
        error?: string | null;
      };
      work_balancer?: {
        enabled?: boolean;
        base_cooldown_seconds?: number;
        effective_cooldown_seconds?: Record<string, number>;
        phases?: string[];
        error?: string;
      };
      resource_router?: {
        enabled?: boolean;
        headroom?: {
          cpu_percent?: number | null;
          gpu_percent?: number | null;
          cpu_headroom?: number;
          gpu_headroom?: number;
          db_headroom?: number;
        };
      };
      queued_tasks_by_lane?: Record<string, number>;
      active_tasks_by_lane?: Record<string, number>;
      runs_last_60m_by_lane?: Record<string, number>;
    };
  } | null>(null);
  // Stabilize the Phase timeline list:
  // - keep a fixed ordering of phase names once we have a non-empty payload
  // - keep showing the last known phase metrics if the next poll returns an empty/failed payload
  const [phaseTimelineOrder, setPhaseTimelineOrder] = useState<string[]>([]);
  const [lastNonEmptyPhases, setLastNonEmptyPhases] = useState<PhaseRow[]>([]);
  const [sourcesCollected, setSourcesCollected] = useState<{
    success?: boolean;
    data?: {
      window_minutes?: number;
      rss_feeds?: Array<{
        feed_name: string;
        feed_url: string;
        domain: string;
        last_fetched_at: string;
      }>;
      orchestrator_sources?: Array<{
        source_id: string;
        last_collected_at: string;
      }>;
      pipeline_stages?: Array<{ stage: string; last_run_at: string }>;
      summary?: string[];
    };
  } | null>(null);
  const [runSummary, setRunSummary] = useState<{
    success?: boolean;
    data?: {
      window_hours?: number;
      phases_run_recently?: Array<{
        name: string;
        last_run: string | null;
        interval_seconds?: number;
      }>;
      phases_not_run_recently?: Array<{
        name: string;
        last_run: string | null;
        interval_seconds?: number;
      }>;
      pipeline_checkpoints_recent?: Array<{
        stage: string;
        status: string;
        timestamp: string;
      }>;
      recent_activity?: Array<{
        timestamp?: string;
        component?: string;
        event_type?: string;
        status?: string;
        message?: string;
      }>;
    };
  } | null>(null);
  const [backlogStatus, setBacklogStatus] = useState<{
    success?: boolean;
    data?: {
      workload_window_days?: number;
      steady_state?: {
        ok: boolean;
        checks?: Record<string, boolean>;
        reasons?: string[];
      };
      articles?: {
        backlog: number;
        per_hour: number;
        per_hour_source?: BacklogPerHourSource;
        processed_last_4d?: number;
        enriched_last_1h?: number;
        enriched_last_24h?: number;
        per_day?: number;
        eta_hours: number;
        eta_utc: string | null;
        created_last_24h?: number;
        short_created_last_24h?: number;
        net_per_day?: number;
        backlog_trend?: string;
      };
      documents?: {
        backlog: number;
        per_hour: number;
        per_hour_source?: BacklogPerHourSource;
        processed_last_4d?: number;
        eta_hours: number;
        eta_utc: string | null;
        processed_last_1h?: number;
        processed_last_24h?: number;
        attempted_last_1h?: number;
        attempted_last_24h?: number;
        failed_last_1h?: number;
        failed_last_24h?: number;
        permanent_failed_total?: number;
        top_failure_reasons_24h?: Array<{ reason: string; count: number }>;
      };
      contexts?: {
        backlog: number;
        per_hour?: number;
        per_hour_source?: BacklogPerHourSource;
        processed_last_4d?: number;
        processed_last_1h?: number;
        total?: number;
        eta_hours?: number;
        iterations_to_baseline?: number;
      };
      entity_profiles?: {
        backlog: number;
        per_hour?: number;
        per_hour_source?: BacklogPerHourSource;
        /** Backlog /hr uses rows updated with non-empty `sections` only (LLM materialization), not catalog sync touches. */
        throughput_scope?: string;
        any_updated_last_1h?: number;
        any_updated_last_24h?: number;
        any_updated_last_4d?: number;
        processed_last_4d?: number;
        processed_last_24h?: number;
        processed_last_1h?: number;
        total?: number;
        eta_hours?: number;
        iterations_to_baseline?: number;
      };
      storylines?: {
        backlog: number;
        per_hour: number;
        per_hour_source?: BacklogPerHourSource;
        processed_last_4d?: number;
        eta_hours: number;
        eta_utc: string | null;
        synthesis_per_domain_last_4d?: Record<string, number>;
      };
      overall_eta_hours?: number;
      overall_eta_utc?: string | null;
      overall_iterations_to_baseline?: number;
      nightly_catchup?: {
        error?: string;
        window?: {
          timezone?: string;
          window_label?: string;
          all_day_catchup?: boolean;
          exclusive_other_phases?: boolean;
          nightly_ingest_exclusive_automation?: boolean;
          enrichment_context_subwindow_local?: string;
          in_unified_window?: boolean;
          window_ends_local?: string | null;
          next_window_starts_local?: string | null;
        };
        drain_phases_backlog?: Record<string, number>;
        sequential_phases_with_backlog?: Array<{ phase: string; count: number }>;
        nightly_drain_idle?: boolean;
        recent_unified_runs?: Array<{
          phase_name?: string;
          started_at?: string | null;
          finished_at?: string | null;
          success?: boolean | null;
          error_snippet?: string | null;
        }>;
        recent_run_summary?: {
          listed?: number;
          success?: number;
          failure?: number;
        };
      };
    };
    error?: string;
  } | null>(null);
  const [dbConnections, setDbConnections] = useState<{
    success?: boolean;
    data?: {
      total_sessions?: number;
      long_running_threshold_seconds?: number;
      long_running_sessions?: number;
      state_counts?: Record<string, number>;
      sessions?: DbSession[];
    };
    error?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  /** True while backlog / process_run_summary / DB sessions are loading after the first parallel batch. */
  const [heavyMonitorPending, setHeavyMonitorPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggerPhaseName, setTriggerPhaseName] = useState<string>('');
  const [forceNightlyUnifiedPipeline, setForceNightlyUnifiedPipeline] =
    useState(false);
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
    let pollTick = 0;
    let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;
    const svc = apiService as unknown as Record<string, unknown>;

    const load = async () => {
      setLoading(true);
      setHeavyMonitorPending(false);
      setError(null);
      try {
        // Capped concurrency: avoids stampedes (browser connection limits, nginx limit_req,
        // API/DB pool contention) especially right after restart when many routes are cold.
        const w1 = await runPoolLimit(
          [
            () => apiService.getMonitoringOverview(),
            () =>
              safeServiceCall<{
                status?: Record<string, unknown>;
                decision_log?: { entries?: DecisionEntry[] };
              }>(svc, 'getOrchestratorDashboard', [{ decision_log_limit: 25 }]),
            () => contextCentricApi.getQuality().catch(() => null),
            () =>
              safeServiceCall<{
                success?: boolean;
                data?: Record<string, unknown>;
              }>(svc, 'getPipelineStatus'),
            () =>
              safeServiceCall<{
                success?: boolean;
                data?: { phases?: PhaseRow[] };
              }>(svc, 'getAutomationStatus'),
            () =>
              safeServiceCall<typeof sourcesCollected>(
                svc,
                'getSourcesCollected',
                [30]
              ),
          ],
          MONITOR_FETCH_CONCURRENCY
        );
        const [ov, o, q, pipe, auto, sources] = w1;
        if (cancelled) return;
        setOverview(ov ?? null);
        setOrchDashboard(o ?? null);
        setQuality(q ?? null);
        setPipeline(pipe ?? null);
        setAutomation(auto ?? null);
        setSourcesCollected(sources ?? null);
        if (!cancelled) setLoading(false);
        if (!cancelled) setHeavyMonitorPending(true);

        // Heavy DB-backed endpoints: one at a time to reduce pool / lock contention.
        const w2 = await runPoolLimit(
          [
            () =>
              safeServiceCall<typeof runSummary>(
                svc,
                'getProcessRunSummary',
                [24, 60]
              ),
            () => safeServiceCall<typeof backlogStatus>(svc, 'getBacklogStatus'),
            () =>
              safeServiceCall<typeof dbConnections>(
                svc,
                'getDatabaseConnections',
                [{ limit: 80, long_running_seconds: 60 }]
              ),
          ],
          1
        );
        const [summary, backlog, dbConns] = w2;
        if (cancelled) return;
        setRunSummary(summary ?? null);
        setBacklogStatus(backlog ?? null);
        setDbConnections(dbConns ?? null);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) {
          setLoading(false);
          setHeavyMonitorPending(false);
        }
      }
    };

    /**
     * Poll must not overlap: setInterval + slow API used to stack 6+ concurrent requests
     * every 4.5s, colliding with proxies (limit_req) and DB UI pool checkouts.
     */
    const runPollTick = async () => {
      if (cancelled) return;
      pollTick += 1;
      const heavyPoll = pollTick % 3 === 0;
      try {
        await loadOverview();
        if (cancelled) return;
        const [autoR, pipeR] = await runPoolLimit(
          [
            () => safeServiceCall(svc, 'getAutomationStatus'),
            () => safeServiceCall(svc, 'getPipelineStatus'),
          ],
          MONITOR_FETCH_CONCURRENCY
        );
        if (!cancelled && autoR)
          setAutomation(autoR as typeof automation);
        if (!cancelled && pipeR) setPipeline(pipeR as typeof pipeline);
        const [orchR, srcR] = await runPoolLimit(
          [
            () =>
              safeServiceCall(svc, 'getOrchestratorDashboard', [
                { decision_log_limit: 25 },
              ]),
            () => safeServiceCall(svc, 'getSourcesCollected', [30]),
          ],
          MONITOR_FETCH_CONCURRENCY
        );
        if (!cancelled && orchR)
          setOrchDashboard(orchR as typeof orchDashboard);
        if (!cancelled && srcR)
          setSourcesCollected(srcR as typeof sourcesCollected);
        const sumR = await safeServiceCall(
          svc,
          'getProcessRunSummary',
          [24, 60]
        );
        if (!cancelled && sumR) setRunSummary(sumR as typeof runSummary);
        if (heavyPoll) {
          const [blR, dbR] = await runPoolLimit(
            [
              () => safeServiceCall(svc, 'getBacklogStatus'),
              () =>
                safeServiceCall(svc, 'getDatabaseConnections', [
                  { limit: 80, long_running_seconds: 60 },
                ]),
            ],
            1
          );
          if (!cancelled && blR)
            setBacklogStatus(blR as typeof backlogStatus);
          if (!cancelled && dbR)
            setDbConnections(dbR as typeof dbConnections);
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

    void (async () => {
      await load();
      if (!cancelled) scheduleNextPoll();
    })();

    return () => {
      cancelled = true;
      if (pollTimeoutId !== null) clearTimeout(pollTimeoutId);
    };
  }, [loadOverview]);

  // Stabilize the phase timeline ordering + cached metrics:
  // - keep a fixed ordering once we first get a non-empty payload
  // - if a later poll returns empty, the timeline continues to use cached metrics
  useEffect(() => {
    const incoming = (automation?.data?.phases ?? []) as PhaseRow[];
    if (!incoming || incoming.length === 0) return;

    setLastNonEmptyPhases(incoming);
    setPhaseTimelineOrder(prev => {
      const incomingNames = incoming
        .filter(p => p.enabled !== false)
        .map(p => p.name);
      if (prev.length === 0) return incomingNames;
      const prevSet = new Set(prev);
      const appended = incomingNames.filter(n => !prevSet.has(n));
      return [...prev, ...appended];
    });
  }, [automation?.data?.phases]);

  const handleTriggerPhase = async () => {
    if (!triggerPhaseName || !apiService.triggerPhase) return;
    setTriggering(true);
    setTriggerResult(null);
    try {
      const result = (await apiService.triggerPhase(triggerPhaseName, {
        force_nightly_unified_pipeline:
          triggerPhaseName === 'nightly_enrichment_context'
            ? forceNightlyUnifiedPipeline
            : undefined,
      })) as {
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
        setForceNightlyUnifiedPipeline(false);
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

  const orchStatus = orchDashboard?.status ?? {};
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

  const lastTimes =
    (orchStatus?.last_collection_times as Record<string, string> | undefined) ??
    {};
  const byDomain = quality?.by_domain as
    | Record<
        string,
        { context_coverage_pct?: number; entity_coverage_pct?: number }
      >
    | undefined;
  const decisionLog = orchDashboard?.decision_log as
    | { entries?: DecisionEntry[] }
    | undefined;
  const decisionEntries = decisionLog?.entries ?? [];
  const dbSessions = dbConnections?.data?.sessions ?? [];
  const dbLongRunning = dbConnections?.data?.long_running_sessions ?? 0;
  const dbTotalSessions =
    dbConnections?.data?.total_sessions ?? dbSessions.length;
  const dbLongThreshold =
    dbConnections?.data?.long_running_threshold_seconds ?? 60;
  const pipelineData = pipeline?.data ?? {};
  const pipelineStatus = pipelineData?.pipeline_status as string | undefined;
  const phasesLatest: PhaseRow[] =
    automation?.data?.phases && automation.data.phases.length > 0
      ? (automation.data.phases as PhaseRow[])
      : lastNonEmptyPhases;
  const phases: PhaseRow[] = phaseTimelineOrder.length
    ? phaseTimelineOrder.map(name => {
        const found = phasesLatest.find(p => p.name === name);
        return found ?? ({ name, last_run: null, enabled: true } as PhaseRow);
      })
    : phasesLatest;
  const queueSize = automation?.data?.queue_size as number | undefined;
  const automationRunning = automation?.data?.is_running as boolean | undefined;
  const docPipeline = automation?.data?.document_pipeline;
  const workBalancer = automation?.data?.work_balancer;
  const resourceRouter = automation?.data?.resource_router;

  const workBalancerSummary = (): string => {
    const wb = workBalancer;
    if (!wb || wb.error) return wb?.error ? `Unavailable (${wb.error})` : '—';
    if (!wb.enabled) return `Off — workload-driven phases use fixed ${wb.base_cooldown_seconds ?? 10}s cooldown`;
    const base = wb.base_cooldown_seconds ?? 10;
    const eff = wb.effective_cooldown_seconds ?? {};
    const adjusted = Object.entries(eff).filter(([, v]) => v !== base);
    if (adjusted.length === 0)
      return `On — pending queues shallow; effective cooldown ${base}s for balanced phases`;
    const parts = adjusted
      .sort((a, b) => a[1] - b[1])
      .slice(0, 8)
      .map(([k, v]) => `${k} ${v}s`);
    return `On — base ${base}s · faster/slower now: ${parts.join(', ')}`;
  };

  const resourceRouterSummary = (): string => {
    const rr = resourceRouter;
    if (!rr || !rr.enabled) return 'Off';
    const h = rr.headroom ?? {};
    const cpu = h.cpu_percent;
    const gpu = h.gpu_percent;
    const db = h.db_headroom;
    const q = automation?.data?.queued_tasks_by_lane ?? {};
    const a = automation?.data?.active_tasks_by_lane ?? {};
    const runs = automation?.data?.runs_last_60m_by_lane ?? {};
    const dbPct =
      typeof db === 'number' && Number.isFinite(db)
        ? `${Math.round(db * 100)}%`
        : 'n/a';
    return `CPU ${cpu ?? 'n/a'}% · GPU ${gpu ?? 'n/a'}% · DB headroom ${dbPct} · queued cpu/gpu ${q.cpu ?? 0}/${q.gpu ?? 0} · running ${a.cpu ?? 0}/${a.gpu ?? 0} · runs60m ${runs.cpu ?? 0}/${runs.gpu ?? 0}`;
  };

  const statusChip = (status: string | undefined, label: string) => {
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

      {/* Connection status */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        System health & connection status
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Card variant='outlined' sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <ApiIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {loading && !overview ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(
                  apiStatus ?? (overview?.success ? 'ok' : undefined),
                  'API'
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
              {loading && !overview ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(dbStatus, 'Database')
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
              {loading && !overview ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(wsStatus, 'Web server')
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
          {loading && currentActivities.length === 0 ? (
            <Skeleton
              variant='rectangular'
              height={60}
              sx={{ borderRadius: 1 }}
            />
          ) : currentActivities.length === 0 ? (
            <Typography color='text.secondary' variant='body2'>
              No background tasks running right now. The system will show items
              like &quot;Running RSS collection&quot; or &quot;Processing
              storyline X&quot; when work is in progress.
            </Typography>
          ) : (
            <List dense disablePadding>
              {currentActivities.map((a, i) => (
                <ListItem
                  key={(a.id as string) || i}
                  disablePadding
                  sx={{ py: 0.5 }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    <RefreshIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={(a.message as string) || 'Working…'}
                    secondary={
                      a.started_at ? timeAgo(a.started_at as string) : null
                    }
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItem>
              ))}
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

      {/* Data sources collected (last 30m) */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Sources collected (last 30 min)
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {sourcesCollected?.data &&
          (sourcesCollected.data.rss_feeds?.length ?? 0) +
            (sourcesCollected.data.orchestrator_sources?.length ?? 0) +
            (sourcesCollected.data.pipeline_stages?.length ?? 0) >
            0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {sourcesCollected.data.rss_feeds &&
                sourcesCollected.data.rss_feeds.length > 0 && (
                  <Box>
                    <Typography
                      variant='caption'
                      color='text.secondary'
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      RSS feeds
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 0.75,
                        alignItems: 'center',
                      }}
                    >
                      {sourcesCollected.data.rss_feeds
                        .slice(0, 12)
                        .map((f, i) => (
                          <Box
                            key={i}
                            sx={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 0.5,
                            }}
                          >
                            <Chip
                              size='small'
                              variant='outlined'
                              label={
                                f.feed_name.length > 28
                                  ? `${f.feed_name.slice(0, 26)}…`
                                  : f.feed_name
                              }
                              title={f.feed_name}
                              sx={{ maxWidth: 200 }}
                            />
                            <Typography
                              component='span'
                              variant='caption'
                              color='text.secondary'
                            >
                              {f.last_fetched_at
                                ? timeAgo(f.last_fetched_at)
                                : '—'}
                            </Typography>
                          </Box>
                        ))}
                      {sourcesCollected.data.rss_feeds.length > 12 && (
                        <Chip
                          size='small'
                          variant='outlined'
                          label={`+${
                            sourcesCollected.data.rss_feeds.length - 12
                          } more`}
                        />
                      )}
                    </Box>
                  </Box>
                )}
              {sourcesCollected.data.orchestrator_sources &&
                sourcesCollected.data.orchestrator_sources.length > 0 && (
                  <Box>
                    <Typography
                      variant='caption'
                      color='text.secondary'
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Other sources
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 0.75,
                        alignItems: 'center',
                      }}
                    >
                      {sourcesCollected.data.orchestrator_sources.map(
                        (s, i) => (
                          <Box
                            key={i}
                            sx={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 0.5,
                            }}
                          >
                            <Chip
                              size='small'
                              color='primary'
                              variant='outlined'
                              label={s.source_id}
                            />
                            <Typography
                              component='span'
                              variant='caption'
                              color='text.secondary'
                            >
                              {s.last_collected_at
                                ? timeAgo(s.last_collected_at)
                                : '—'}
                            </Typography>
                          </Box>
                        )
                      )}
                    </Box>
                  </Box>
                )}
              {sourcesCollected.data.pipeline_stages &&
                sourcesCollected.data.pipeline_stages.length > 0 && (
                  <Box>
                    <Typography
                      variant='caption'
                      color='text.secondary'
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Pipeline stages
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 0.75,
                        alignItems: 'center',
                      }}
                    >
                      {sourcesCollected.data.pipeline_stages.map((s, i) => (
                        <Box
                          key={i}
                          sx={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 0.5,
                          }}
                        >
                          <Chip
                            size='small'
                            variant='outlined'
                            label={s.stage.replace(/_/g, ' ')}
                          />
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                          >
                            {s.last_run_at ? timeAgo(s.last_run_at) : '—'}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                )}
            </Box>
          ) : (
            <Typography color='text.secondary' variant='body2'>
              No sources in the last{' '}
              {sourcesCollected?.data?.window_minutes ?? 30} minutes.
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Process run summary: what has run vs not triggered recently */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Process run summary (last 24h)
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {runSummary?.data ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 2,
                  alignItems: 'center',
                }}
              >
                <Typography variant='body2'>
                  <strong>Phases run:</strong>{' '}
                  {runSummary.data.phases_run_recently?.length ?? 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  <strong>Not run / never:</strong>{' '}
                  {runSummary.data.phases_not_run_recently?.length ?? 0}
                </Typography>
                {runSummary.data.pipeline_checkpoints_recent?.length != null &&
                  runSummary.data.pipeline_checkpoints_recent.length > 0 && (
                    <Typography variant='body2' color='text.secondary'>
                      <strong>Pipeline checkpoints:</strong>{' '}
                      {runSummary.data.pipeline_checkpoints_recent.length}
                    </Typography>
                  )}
              </Box>
              {runSummary.data.phases_not_run_recently &&
                runSummary.data.phases_not_run_recently.length > 0 && (
                  <Box>
                    <Typography
                      variant='caption'
                      color='text.secondary'
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Phases not run in last 24h (or never)
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {runSummary.data.phases_not_run_recently
                        .slice(0, 20)
                        .map((p, i) => (
                          <Chip
                            key={i}
                            size='small'
                            variant='outlined'
                            label={p.name}
                            title={
                              p.last_run
                                ? `Last run: ${p.last_run}`
                                : 'Never run'
                            }
                          />
                        ))}
                      {runSummary.data.phases_not_run_recently.length > 20 && (
                        <Chip
                          size='small'
                          variant='outlined'
                          label={`+${
                            runSummary.data.phases_not_run_recently.length - 20
                          } more`}
                        />
                      )}
                    </Box>
                  </Box>
                )}
              {runSummary.data.recent_activity &&
                runSummary.data.recent_activity.length > 0 && (
                  <Box>
                    <Typography
                      variant='caption'
                      color='text.secondary'
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Recent activity (from logs)
                    </Typography>
                    <List
                      dense
                      disablePadding
                      sx={{ maxHeight: 180, overflow: 'auto' }}
                    >
                      {runSummary.data.recent_activity
                        .slice(-12)
                        .reverse()
                        .map((a, i) => (
                          <ListItem key={i} disablePadding sx={{ py: 0.25 }}>
                            <ListItemText
                              primary={
                                a.message ||
                                `${a.component || ''} ${a.event_type || ''} ${
                                  a.status || ''
                                }`.trim() ||
                                '—'
                              }
                              secondary={
                                a.timestamp ? timeAgo(a.timestamp) : null
                              }
                              primaryTypographyProps={{ variant: 'caption' }}
                              secondaryTypographyProps={{ variant: 'caption' }}
                            />
                          </ListItem>
                        ))}
                    </List>
                  </Box>
                )}
            </Box>
          ) : (loading || heavyMonitorPending) && runSummary == null ? (
            <Skeleton variant='rectangular' height={72} sx={{ borderRadius: 1 }} />
          ) : (
            <Typography color='text.secondary' variant='body2'>
              Run summary not available. Check automation is running and logs
              exist.
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Backlog status progression */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 0.5 }}>
        Backlog status progression
      </Typography>
      <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
        ETAs use a rolling average over the last{' '}
        {backlogStatus?.data?.workload_window_days ?? 4} days when enough work
        was completed in that window; otherwise recent 1h/24h measurements or a
        conservative estimate. “Steady state” requires automation backlogs within
        one batch each, empty monitor queues, non-growing article trend, and
        catch-up iterations at baseline.
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {backlogStatus?.success && backlogStatus.data ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {backlogStatus.data.steady_state && (
                <Alert
                  severity={
                    backlogStatus.data.steady_state.ok ? 'success' : 'warning'
                  }
                  icon={
                    backlogStatus.data.steady_state.ok ? (
                      <CheckCircleOutlineIcon />
                    ) : (
                      <ErrorOutlineIcon />
                    )
                  }
                >
                  <Typography variant='subtitle2' fontWeight={600}>
                    Steady state:{' '}
                    {backlogStatus.data.steady_state.ok ? 'Yes' : 'Not yet'}
                  </Typography>
                  {backlogStatus.data.steady_state.ok ? (
                    <Typography variant='body2' color='text.secondary'>
                      Automation queues are within one batch depth, SQL monitor
                      backlogs are clear, article inflow is not outpacing
                      throughput, and overall catch-up is at baseline (≤1
                      two-hour iteration).
                    </Typography>
                  ) : (
                    <Typography variant='body2' color='text.secondary'>
                      {(backlogStatus.data.steady_state.reasons ?? []).join(
                        ' '
                      ) || 'See backlog rows and automation status.'}
                    </Typography>
                  )}
                  {backlogStatus.data.steady_state.checks &&
                    !backlogStatus.data.steady_state.ok && (
                      <Typography
                        variant='caption'
                        color='text.secondary'
                        display='block'
                        sx={{ mt: 0.5 }}
                      >
                        {Object.entries(backlogStatus.data.steady_state.checks)
                          .map(([k, v]) => `${k}: ${v ? 'pass' : 'fail'}`)
                          .join(' · ')}
                      </Typography>
                    )}
                </Alert>
              )}
              {backlogStatus.data.nightly_catchup && (
                <Alert
                  severity={
                    backlogStatus.data.nightly_catchup.error
                      ? 'warning'
                      : backlogStatus.data.nightly_catchup.nightly_drain_idle
                        ? 'success'
                        : 'info'
                  }
                  icon={<NightsStayIcon fontSize='inherit' />}
                >
                  <Typography variant='subtitle2' fontWeight={600} gutterBottom>
                    Nightly catch-up (unified pipeline)
                  </Typography>
                  {backlogStatus.data.nightly_catchup.error ? (
                    <Typography variant='body2' color='text.secondary'>
                      {backlogStatus.data.nightly_catchup.error}
                    </Typography>
                  ) : (
                    <>
                      <Typography variant='body2' color='text.secondary'>
                        {backlogStatus.data.nightly_catchup.window
                          ?.in_unified_window
                          ? 'Inside nightly window'
                          : 'Outside nightly window'}
                        {backlogStatus.data.nightly_catchup.window
                          ?.all_day_catchup
                          ? ' · 24/7 catch-up (NIGHTLY_PIPELINE_ALL_DAY)'
                          : ''}
                        {backlogStatus.data.nightly_catchup.window?.window_label
                          ? ` · ${backlogStatus.data.nightly_catchup.window.window_label}`
                          : ''}
                        {backlogStatus.data.nightly_catchup.window?.timezone
                          ? ` · ${backlogStatus.data.nightly_catchup.window.timezone}`
                          : ''}
                      </Typography>
                      {!backlogStatus.data.nightly_catchup.window
                        ?.all_day_catchup && (
                        <Typography
                          variant='caption'
                          color='text.secondary'
                          display='block'
                          sx={{ mt: 0.5 }}
                        >
                          {backlogStatus.data.nightly_catchup.window
                            ?.in_unified_window &&
                          backlogStatus.data.nightly_catchup.window
                            ?.window_ends_local
                            ? `Window ends (local): ${backlogStatus.data.nightly_catchup.window.window_ends_local}`
                            : null}
                          {!backlogStatus.data.nightly_catchup.window
                            ?.in_unified_window &&
                          backlogStatus.data.nightly_catchup.window
                            ?.next_window_starts_local
                            ? `Next window starts (local): ${backlogStatus.data.nightly_catchup.window.next_window_starts_local}`
                            : null}
                        </Typography>
                      )}
                      <Typography
                        variant='body2'
                        color='text.secondary'
                        sx={{ mt: 0.75 }}
                      >
                        Nightly drain idle (enrichment + context + refinement +
                        sequential phases):{' '}
                        <strong>
                          {backlogStatus.data.nightly_catchup.nightly_drain_idle
                            ? 'yes'
                            : 'no'}
                        </strong>
                        {backlogStatus.data.nightly_catchup
                          .drain_phases_backlog && (
                          <span>
                            {' '}
                            · CE{' '}
                            {(
                              backlogStatus.data.nightly_catchup
                                .drain_phases_backlog.content_enrichment ?? 0
                            ).toLocaleString()}
                            , ctx{' '}
                            {(
                              backlogStatus.data.nightly_catchup
                                .drain_phases_backlog.context_sync ?? 0
                            ).toLocaleString()}
                            , refinement{' '}
                            {(
                              backlogStatus.data.nightly_catchup
                                .drain_phases_backlog
                                .content_refinement_queue ?? 0
                            ).toLocaleString()}
                          </span>
                        )}
                      </Typography>
                      {(backlogStatus.data.nightly_catchup
                        .sequential_phases_with_backlog?.length ?? 0) > 0 && (
                        <Typography
                          variant='caption'
                          color='text.secondary'
                          display='block'
                          sx={{ mt: 0.5 }}
                        >
                          Sequential phases with backlog:{' '}
                          {backlogStatus.data.nightly_catchup.sequential_phases_with_backlog
                            ?.map(p => `${p.phase} (${p.count})`)
                            .join(', ')}
                        </Typography>
                      )}
                      {(backlogStatus.data.nightly_catchup.recent_unified_runs
                        ?.length ?? 0) > 0 && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant='caption' fontWeight={600}>
                            Recent{' '}
                            <code>nightly_enrichment_context</code> runs (newest
                            first)
                            {backlogStatus.data.nightly_catchup
                              .recent_run_summary && (
                              <span>
                                {' '}
                                — ok{' '}
                                {
                                  backlogStatus.data.nightly_catchup
                                    .recent_run_summary.success ?? 0
                                }
                                , fail{' '}
                                {
                                  backlogStatus.data.nightly_catchup
                                    .recent_run_summary.failure ?? 0
                                }{' '}
                                of{' '}
                                {
                                  backlogStatus.data.nightly_catchup
                                    .recent_run_summary.listed ?? 0
                                }{' '}
                                listed
                              </span>
                            )}
                          </Typography>
                          <List dense disablePadding sx={{ mt: 0.5 }}>
                            {backlogStatus.data.nightly_catchup.recent_unified_runs?.map(
                              (r, i) => (
                                <ListItem key={i} disableGutters sx={{ py: 0 }}>
                                  <ListItemText
                                    primary={
                                      <Box
                                        component='span'
                                        sx={{
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: 0.5,
                                          flexWrap: 'wrap',
                                        }}
                                      >
                                        <Chip
                                          size='small'
                                          label={
                                            r.success === true
                                              ? 'ok'
                                              : r.success === false
                                                ? 'fail'
                                                : '—'
                                          }
                                          color={
                                            r.success === true
                                              ? 'success'
                                              : r.success === false
                                                ? 'error'
                                                : 'default'
                                          }
                                          variant='outlined'
                                          sx={{ height: 20 }}
                                        />
                                        <Typography
                                          component='span'
                                          variant='caption'
                                          title={
                                            r.finished_at ?? r.started_at ?? ''
                                          }
                                        >
                                          {r.finished_at
                                            ? `${timeAgo(r.finished_at)} · ${shortLocalDateTime(r.finished_at)}`
                                            : r.started_at
                                              ? `started ${timeAgo(r.started_at)} · ${shortLocalDateTime(r.started_at)}`
                                              : '—'}
                                        </Typography>
                                      </Box>
                                    }
                                    secondary={
                                      r.error_snippet || undefined
                                    }
                                    primaryTypographyProps={{
                                      variant: 'caption',
                                    }}
                                    secondaryTypographyProps={{
                                      variant: 'caption',
                                    }}
                                  />
                                </ListItem>
                              )
                            )}
                          </List>
                        </Box>
                      )}
                    </>
                  )}
                </Alert>
              )}
              <Table size='small'>
                <TableHead>
                  <TableRow>
                    <TableCell>Queue</TableCell>
                    <TableCell align='right'>Remaining</TableCell>
                    <TableCell align='right'>Throughput</TableCell>
                    <TableCell>ETA</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>Articles (enrich)</TableCell>
                    <TableCell align='right'>
                      {(
                        backlogStatus.data.articles?.backlog ?? 0
                      ).toLocaleString()}
                    </TableCell>
                    <TableCell align='right'>
                      ~{backlogStatus.data.articles?.per_hour ?? 0}/hr
                      {backlogStatus.data.articles?.per_hour_source && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          (
                          {throughputSourceLabel(
                            backlogStatus.data.articles.per_hour_source
                          )}
                          )
                        </Typography>
                      )}
                      {(backlogStatus.data.articles?.processed_last_4d ?? 0) >
                        0 && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          {(
                            backlogStatus.data.articles?.processed_last_4d ?? 0
                          ).toLocaleString()}{' '}
                          enriched in last{' '}
                          {backlogStatus.data.workload_window_days ?? 4}d
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {(backlogStatus.data.articles?.backlog ?? 0) > 0
                        ? `~${backlogStatus.data.articles?.eta_hours ?? 0}h (${
                            backlogStatus.data.articles?.eta_utc
                              ? new Date(
                                  backlogStatus.data.articles.eta_utc
                                ).toLocaleString()
                              : '—'
                          })`
                        : '—'}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Documents (extract)</TableCell>
                    <TableCell align='right'>
                      {(
                        backlogStatus.data.documents?.backlog ?? 0
                      ).toLocaleString()}
                    </TableCell>
                    <TableCell align='right'>
                      ~{backlogStatus.data.documents?.per_hour ?? 0}/hr
                      {backlogStatus.data.documents?.per_hour_source && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          (
                          {throughputSourceLabel(
                            backlogStatus.data.documents.per_hour_source
                          )}
                          )
                        </Typography>
                      )}
                      {(backlogStatus.data.documents?.processed_last_4d ?? 0) >
                        0 && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          {(
                            backlogStatus.data.documents?.processed_last_4d ??
                            0
                          ).toLocaleString()}{' '}
                          extracted in last{' '}
                          {backlogStatus.data.workload_window_days ?? 4}d
                        </Typography>
                      )}
                      {(backlogStatus.data.documents?.processed_last_1h ?? 0) >=
                        0 && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          (success:{' '}
                          {backlogStatus.data.documents?.processed_last_1h ?? 0}{' '}
                          last 1h
                          {(backlogStatus.data.documents?.attempted_last_1h ??
                            0) > 0 ||
                          (backlogStatus.data.documents?.failed_last_1h ?? 0) >
                            0
                            ? ` · attempts: ${
                                backlogStatus.data.documents
                                  ?.attempted_last_1h ?? 0
                              } · failed: ${
                                backlogStatus.data.documents?.failed_last_1h ??
                                0
                              }`
                            : ''}
                          )
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {(backlogStatus.data.documents?.backlog ?? 0) > 0
                        ? `~${backlogStatus.data.documents?.eta_hours ?? 0}h (${
                            backlogStatus.data.documents?.eta_utc
                              ? new Date(
                                  backlogStatus.data.documents.eta_utc
                                ).toLocaleString()
                              : '—'
                          })${
                            (
                              backlogStatus.data.documents as {
                                iterations_to_baseline?: number;
                              }
                            )?.iterations_to_baseline != null
                              ? ` · ${
                                  (
                                    backlogStatus.data.documents as {
                                      iterations_to_baseline: number;
                                    }
                                  ).iterations_to_baseline
                                } iters`
                              : ''
                          }`
                        : '—'}
                    </TableCell>
                  </TableRow>
                  {backlogStatus.data.contexts && (
                    <TableRow>
                      <TableCell>Contexts (claims)</TableCell>
                      <TableCell align='right'>
                        {(
                          backlogStatus.data.contexts.backlog ?? 0
                        ).toLocaleString()}{' '}
                        /{' '}
                        {(
                          backlogStatus.data.contexts.total ?? 0
                        ).toLocaleString()}
                      </TableCell>
                      <TableCell align='right'>
                        ~{backlogStatus.data.contexts.per_hour ?? 0}/hr
                        {backlogStatus.data.contexts.per_hour_source && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            (
                            {throughputSourceLabel(
                              backlogStatus.data.contexts.per_hour_source
                            )}
                            )
                          </Typography>
                        )}
                        {(backlogStatus.data.contexts.processed_last_4d ?? 0) >
                          0 && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            {(
                              backlogStatus.data.contexts.processed_last_4d ?? 0
                            ).toLocaleString()}{' '}
                            contexts w/ claims in last{' '}
                            {backlogStatus.data.workload_window_days ?? 4}d
                          </Typography>
                        )}
                        {(backlogStatus.data.contexts.processed_last_1h ?? 0) >
                          0 && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            (
                            {backlogStatus.data.contexts.processed_last_1h ?? 0}{' '}
                            last 1h)
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {(backlogStatus.data.contexts.backlog ?? 0) > 0
                          ? `~${
                              backlogStatus.data.contexts.eta_hours ?? 0
                            }h · ${
                              backlogStatus.data.contexts
                                .iterations_to_baseline ?? '—'
                            } iters`
                          : '—'}
                      </TableCell>
                    </TableRow>
                  )}
                  {backlogStatus.data.entity_profiles && (
                    <TableRow>
                      <TableCell>Entity profiles</TableCell>
                      <TableCell align='right'>
                        {(
                          backlogStatus.data.entity_profiles.backlog ?? 0
                        ).toLocaleString()}{' '}
                        /{' '}
                        {(
                          backlogStatus.data.entity_profiles.total ?? 0
                        ).toLocaleString()}
                      </TableCell>
                      <TableCell align='right'>
                        ~{backlogStatus.data.entity_profiles.per_hour ?? 0}/hr
                        {backlogStatus.data.entity_profiles
                          .per_hour_source && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            (
                            {throughputSourceLabel(
                              backlogStatus.data.entity_profiles.per_hour_source
                            )}
                            )
                          </Typography>
                        )}
                        {(backlogStatus.data.entity_profiles
                          .processed_last_4d ?? 0) > 0 && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            {(
                              backlogStatus.data.entity_profiles
                                .processed_last_4d ?? 0
                            ).toLocaleString()}{' '}
                            sections filled in last{' '}
                            {backlogStatus.data.workload_window_days ?? 4}d
                          </Typography>
                        )}
                        {(backlogStatus.data.entity_profiles
                          .any_updated_last_24h ?? 0) > 0 && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            {(
                              backlogStatus.data.entity_profiles
                                .any_updated_last_24h ?? 0
                            ).toLocaleString()}{' '}
                            row updates (incl. sync) in 24h
                          </Typography>
                        )}
                        {(backlogStatus.data.entity_profiles
                          .processed_last_1h ?? 0) > 0 && (
                          <Typography
                            component='span'
                            variant='caption'
                            color='text.secondary'
                            sx={{ display: 'block' }}
                          >
                            (
                            {backlogStatus.data.entity_profiles
                              .processed_last_1h ?? 0}{' '}
                            sections filled last 1h)
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {(backlogStatus.data.entity_profiles.backlog ?? 0) > 0
                          ? `~${
                              backlogStatus.data.entity_profiles.eta_hours ?? 0
                            }h · ${
                              backlogStatus.data.entity_profiles
                                .iterations_to_baseline ?? '—'
                            } iters`
                          : '—'}
                      </TableCell>
                    </TableRow>
                  )}
                  <TableRow>
                    <TableCell>Storylines (synthesis)</TableCell>
                    <TableCell align='right'>
                      {(
                        backlogStatus.data.storylines?.backlog ?? 0
                      ).toLocaleString()}
                    </TableCell>
                    <TableCell align='right'>
                      ~{backlogStatus.data.storylines?.per_hour ?? 0}/hr
                      {backlogStatus.data.storylines?.per_hour_source && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          (
                          {throughputSourceLabel(
                            backlogStatus.data.storylines.per_hour_source
                          )}
                          )
                        </Typography>
                      )}
                      {(backlogStatus.data.storylines?.processed_last_4d ?? 0) >
                        0 && (
                        <Typography
                          component='span'
                          variant='caption'
                          color='text.secondary'
                          sx={{ display: 'block' }}
                        >
                          {(
                            backlogStatus.data.storylines?.processed_last_4d ??
                            0
                          ).toLocaleString()}{' '}
                          synthesized in last{' '}
                          {backlogStatus.data.workload_window_days ?? 4}d
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {(backlogStatus.data.storylines?.backlog ?? 0) > 0
                        ? `~${
                            backlogStatus.data.storylines?.eta_hours ?? 0
                          }h (${
                            backlogStatus.data.storylines?.eta_utc
                              ? new Date(
                                  backlogStatus.data.storylines.eta_utc
                                ).toLocaleString()
                              : '—'
                          })${
                            (
                              backlogStatus.data.storylines as {
                                iterations_to_baseline?: number;
                              }
                            )?.iterations_to_baseline != null
                              ? ` · ${
                                  (
                                    backlogStatus.data.storylines as {
                                      iterations_to_baseline: number;
                                    }
                                  ).iterations_to_baseline
                                } iters`
                              : ''
                          }`
                        : '—'}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              {(
                backlogStatus.data.storylines as {
                  synthesis_per_domain_last_1h?: Record<string, number>;
                }
              )?.synthesis_per_domain_last_1h && (
                <Typography
                  variant='caption'
                  color='text.secondary'
                  display='block'
                  sx={{ mt: 0.5 }}
                >
                  Synthesis last 1h by domain:{' '}
                  {Object.entries(
                    (
                      backlogStatus.data.storylines as {
                        synthesis_per_domain_last_1h: Record<string, number>;
                      }
                    ).synthesis_per_domain_last_1h
                  )
                    .map(([d, n]) => `${d}: ${n}`)
                    .join(', ')}
                </Typography>
              )}
              {(
                backlogStatus.data.storylines as {
                  synthesis_per_domain_last_4d?: Record<string, number>;
                }
              )?.synthesis_per_domain_last_4d &&
                Object.values(
                  (
                    backlogStatus.data.storylines as {
                      synthesis_per_domain_last_4d: Record<string, number>;
                    }
                  ).synthesis_per_domain_last_4d
                ).some(n => n > 0) && (
                  <Typography
                    variant='caption'
                    color='text.secondary'
                    display='block'
                    sx={{ mt: 0.25 }}
                  >
                    Synthesis last {backlogStatus.data.workload_window_days ?? 4}
                    d by domain:{' '}
                    {Object.entries(
                      (
                        backlogStatus.data.storylines as {
                          synthesis_per_domain_last_4d: Record<string, number>;
                        }
                      ).synthesis_per_domain_last_4d
                    )
                      .map(([d, n]) => `${d}: ${n}`)
                      .join(', ')}
                  </Typography>
                )}
              {(backlogStatus.data.documents?.permanent_failed_total ?? 0) >
                0 && (
                <Typography
                  variant='caption'
                  color='warning.main'
                  display='block'
                  sx={{ mt: 0.5 }}
                >
                  Documents excluded from retries (permanent failure):{' '}
                  {(
                    backlogStatus.data.documents?.permanent_failed_total ?? 0
                  ).toLocaleString()}
                </Typography>
              )}
              {(backlogStatus.data.documents?.top_failure_reasons_24h?.length ??
                0) > 0 && (
                <Typography
                  variant='caption'
                  color='text.secondary'
                  display='block'
                  sx={{ mt: 0.5 }}
                >
                  Top document failures (24h):{' '}
                  {(backlogStatus.data.documents?.top_failure_reasons_24h ?? [])
                    .map(x => `${x.reason}: ${x.count}`)
                    .join(' · ')}
                </Typography>
              )}
              {backlogStatus.data.overall_eta_utc != null &&
                (backlogStatus.data.articles?.backlog ?? 0) +
                  (backlogStatus.data.documents?.backlog ?? 0) +
                  (backlogStatus.data.storylines?.backlog ?? 0) +
                  (backlogStatus.data.contexts?.backlog ?? 0) +
                  (backlogStatus.data.entity_profiles?.backlog ?? 0) >
                  0 && (
                  <Typography variant='body2' color='text.secondary'>
                    Overall catch-up: ~
                    {backlogStatus.data.overall_eta_hours ?? 0}h →{' '}
                    {new Date(
                      backlogStatus.data.overall_eta_utc!
                    ).toLocaleString()}
                    {(
                      backlogStatus.data as {
                        overall_iterations_to_baseline?: number;
                      }
                    ).overall_iterations_to_baseline != null && (
                      <>
                        {' '}
                        ·{' '}
                        {
                          (
                            backlogStatus.data as {
                              overall_iterations_to_baseline: number;
                            }
                          ).overall_iterations_to_baseline
                        }{' '}
                        iterations (2h cycles)
                      </>
                    )}
                  </Typography>
                )}
              {(backlogStatus.data.articles?.backlog ?? 0) +
                (backlogStatus.data.documents?.backlog ?? 0) +
                (backlogStatus.data.storylines?.backlog ?? 0) +
                (backlogStatus.data.contexts?.backlog ?? 0) +
                (backlogStatus.data.entity_profiles?.backlog ?? 0) ===
                0 && (
                <Typography variant='body2' color='success.main'>
                  No monitor SQL backlog — all listed queues current. Use
                  “Steady state” above for full pipeline + automation health.
                </Typography>
              )}
              {backlogStatus.data.articles &&
                (backlogStatus.data.articles.created_last_24h != null ||
                  backlogStatus.data.articles.backlog_trend) && (
                  <Box
                    sx={{
                      mt: 1.5,
                      pt: 1.5,
                      borderTop: 1,
                      borderColor: 'divider',
                    }}
                  >
                    <Typography
                      variant='caption'
                      color='text.secondary'
                      display='block'
                    >
                      Inflow vs outflow (articles, same 24h window)
                    </Typography>
                    <Typography variant='body2'>
                      In last 24h:{' '}
                      {backlogStatus.data.articles.created_last_24h?.toLocaleString() ??
                        '—'}{' '}
                      created,{' '}
                      {(
                        backlogStatus.data.articles.short_created_last_24h ?? 0
                      ).toLocaleString()}{' '}
                      of those still need enrichment · Enriched (completed):{' '}
                      {backlogStatus.data.articles.enriched_last_24h ?? 0} /
                      24h
                      {(backlogStatus.data.articles.enriched_last_1h != null ||
                        backlogStatus.data.articles.enriched_last_24h !=
                          null) && (
                        <>
                          {' '}
                          ({backlogStatus.data.articles.enriched_last_1h ?? 0}{' '}
                          last 1h)
                        </>
                      )}
                      {' '}
                      · ETA model ~{' '}
                      {Math.round(
                        backlogStatus.data.articles.per_day ?? 0
                      ).toLocaleString()}
                      /day (
                      {backlogStatus.data.articles.per_hour_source ?? '—'})
                      {' · '}
                      <Typography
                        component='span'
                        variant='body2'
                        fontWeight={600}
                        color={
                          backlogStatus.data.articles.backlog_trend ===
                          'growing'
                            ? 'warning.main'
                            : backlogStatus.data.articles.backlog_trend ===
                              'shrinking'
                            ? 'success.main'
                            : 'text.secondary'
                        }
                      >
                        Backlog{' '}
                        {backlogStatus.data.articles.backlog_trend ?? '—'}
                      </Typography>
                    </Typography>
                  </Box>
                )}
            </Box>
          ) : backlogStatus?.error ? (
            <Typography color='text.secondary' variant='body2'>
              {String(backlogStatus.error).toLowerCase().includes('timeout')
                ? 'Backlog status unavailable: the request timed out (database may be busy). Retry in a moment.'
                : `Backlog status unavailable: ${backlogStatus.error}`}
            </Typography>
          ) : (loading || heavyMonitorPending) && backlogStatus === null ? (
            <Skeleton
              variant='rectangular'
              height={100}
              sx={{ borderRadius: 1 }}
            />
          ) : (
            <Typography color='text.secondary' variant='body2'>
              Backlog status not available. Check API and database.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Database connections
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5, overflowX: 'auto' }}>
          {(loading || heavyMonitorPending) && dbConnections === null ? (
            <Skeleton variant='rectangular' height={120} />
          ) : dbConnections?.success === false ? (
            <Typography color='text.secondary' variant='body2'>
              Database connection view unavailable:{' '}
              {dbConnections?.error ?? 'Unknown error'}
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  flexWrap: 'wrap',
                }}
              >
                <Chip size='small' label={`Sessions: ${dbTotalSessions}`} />
                <Chip
                  size='small'
                  color={dbLongRunning > 0 ? 'warning' : 'success'}
                  label={`Long-running (>${dbLongThreshold}s): ${dbLongRunning}`}
                />
              </Box>
              {dbSessions.length === 0 ? (
                <Typography color='text.secondary' variant='body2'>
                  No active DB sessions.
                </Typography>
              ) : (
                <Table size='small'>
                  <TableHead>
                    <TableRow>
                      <TableCell>PID</TableCell>
                      <TableCell>State</TableCell>
                      <TableCell>Open</TableCell>
                      <TableCell>User/App</TableCell>
                      <TableCell>Wait</TableCell>
                      <TableCell>Query (preview)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dbSessions.slice(0, 50).map(s => (
                      <TableRow
                        key={s.pid}
                        sx={
                          s.long_running ? { bgcolor: 'warning.50' } : undefined
                        }
                      >
                        <TableCell sx={{ fontFamily: 'monospace' }}>
                          {s.pid}
                        </TableCell>
                        <TableCell>{s.state ?? '—'}</TableCell>
                        <TableCell>
                          {s.open_seconds != null ? `${s.open_seconds}s` : '—'}
                        </TableCell>
                        <TableCell>
                          <Typography
                            variant='caption'
                            sx={{ display: 'block' }}
                          >
                            {s.user ?? '—'}
                          </Typography>
                          <Typography variant='caption' color='text.secondary'>
                            {s.application_name || s.client_addr || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          {s.wait_event_type || s.wait_event
                            ? `${s.wait_event_type ?? ''}${
                                s.wait_event ? `/${s.wait_event}` : ''
                              }`
                            : '—'}
                        </TableCell>
                        <TableCell sx={{ maxWidth: 500 }}>
                          <Typography
                            variant='caption'
                            sx={{
                              fontFamily: 'monospace',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              display: 'block',
                            }}
                          >
                            {(s.query_text || '').replace(/\s+/g, ' ').trim() ||
                              '—'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      <Divider sx={{ my: 2 }} />

      {/* Pipeline status */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Pipeline & automation
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader
            title='Pipeline status'
            subheader='Traces and processing'
            avatar={<ScheduleIcon />}
          />
          <CardContent>
            {loading && !pipeline?.data ? (
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
                  Articles processed: {pipelineData?.articles_processed ?? '—'}{' '}
                  · Analyzed: {pipelineData?.articles_analyzed ?? '—'} · Recent
                  (1h): {pipelineData?.recent_articles ?? '—'}
                </Typography>
                {pipelineData?.active_traces != null &&
                  Number(pipelineData.active_traces) > 0 && (
                    <Typography variant='caption' color='info.main'>
                      Active traces: {pipelineData.active_traces}
                    </Typography>
                  )}
              </Box>
            )}
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader
            title='Automation manager'
            subheader='Queue and workers'
          />
          <CardContent>
            {loading && automation?.data === undefined ? (
              <Skeleton variant='rectangular' height={60} />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    size='small'
                    color={automationRunning ? 'success' : 'default'}
                    label={automationRunning ? 'Running' : 'Stopped'}
                  />
                  <Typography variant='body2'>
                    In-memory queue: {queueSize ?? 0}
                  </Typography>
                  {automation?.data?.active_workers != null && (
                    <Typography variant='caption' color='text.secondary'>
                      Phase workers: {automation.data.active_workers}
                      {typeof automation.data.phase_workers_configured === 'number'
                        ? ` / ${automation.data.phase_workers_configured} configured`
                        : ''}
                    </Typography>
                  )}
                </Box>
                {typeof automation?.data?.message === 'string' &&
                  automation.data.message.length > 0 && (
                    <Typography variant='caption' color='warning.main'>
                      {automation.data.message}
                    </Typography>
                  )}
                {!automationRunning && (
                  <Typography variant='caption' color='text.secondary' display='block'>
                    &quot;Stopped&quot; means the automation scheduler loop is not
                    running on this API worker. Backlog status above counts{' '}
                    <strong>database</strong> pending rows (e.g. ml queue) — those
                    can stay high while this shows 0. If phases completed 0 in 24h,
                    restart the API host process and check logs for automation startup
                    errors.
                  </Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader
            title='Domain synthesis & enrichment'
            subheader='Config and pipelines'
          />
          <CardContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Typography variant='body2'>
                <strong>Domain configs:</strong>{' '}
                {getDomainKeysList().join(', ') || '—'}
              </Typography>
              <Typography variant='body2'>
                <strong>GDELT enrichment:</strong>{' '}
                <Chip
                  size='small'
                  color='success'
                  label='Active'
                  variant='outlined'
                  sx={{ verticalAlign: 'middle' }}
                />
              </Typography>
              <Typography variant='body2'>
                <strong>Claims→facts:</strong>{' '}
                {(() => {
                  const cf = phases.find(p => p.name === 'claims_to_facts');
                  return cf?.last_run ? timeAgo(cf.last_run) : 'scheduled';
                })()}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Documents + backlog-aware scheduler (PDF path + work balancer) */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 0.5 }}>
        Documents &amp; backlog-aware scheduling
      </Typography>
      <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
        PDF queue snapshot from `processed_documents`; work balancer adjusts workload-driven
        cooldown for backfill phases when pending depth exceeds ~one batch (see{' '}
        <code>WORKLOAD_BALANCER_*</code> env).
      </Typography>
      <Card variant='outlined' sx={{ mb: 2 }}>
        <CardContent sx={{ py: 1.25 }}>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              alignItems: 'center',
            }}
          >
            <Chip
              size='small'
              variant='outlined'
              color={
                (docPipeline?.pending_extraction ?? 0) > 20
                  ? 'warning'
                  : 'default'
              }
              label={`Docs pending: ${(docPipeline?.pending_extraction ?? 0).toLocaleString()}`}
            />
            <Chip
              size='small'
              variant='outlined'
              label={`Extracted 24h: ${(docPipeline?.extracted_last_24h ?? 0).toLocaleString()}`}
            />
            <Chip
              size='small'
              variant='outlined'
              color={
                (docPipeline?.permanent_failed_total ?? 0) > 0
                  ? 'error'
                  : 'default'
              }
              label={`Failed (permanent): ${(docPipeline?.permanent_failed_total ?? 0).toLocaleString()}`}
            />
            {docPipeline?.error && (
              <Typography variant='caption' color='error'>
                {docPipeline.error}
              </Typography>
            )}
          </Box>
          <Divider sx={{ my: 1.25 }} />
          <Typography variant='body2' color='text.secondary'>
            <strong>Work balancer:</strong> {workBalancerSummary()}
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            <strong>Resource router:</strong> {resourceRouterSummary()}
          </Typography>
        </CardContent>
      </Card>

      {/* Phase timeline — grouped by related processes, sequential order */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Phase timeline (grouped by stage, last run / workload)
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5, overflowX: 'auto' }}>
          {loading && phases.length === 0 ? (
            <Skeleton variant='rectangular' height={120} />
          ) : phases.length === 0 ? (
            <Typography color='text.secondary' variant='body2'>
              No phase data. Automation may not be running.
            </Typography>
          ) : (
            (() => {
              const enabled = phases.filter(p => p.enabled !== false);
              const byGroup = enabled.reduce<
                { label: string; stageOrder: number; rows: PhaseRow[] }[]
              >((acc, p) => {
                const label = p.phase_group_label ?? `Phase ${p.phase ?? 0}`;
                const stageOrder = p.stage_order ?? 99;
                const existing = acc.find(g => g.label === label);
                if (existing) {
                  existing.rows.push(p);
                  existing.stageOrder = Math.min(
                    existing.stageOrder,
                    stageOrder
                  );
                } else {
                  acc.push({ label, stageOrder, rows: [p] });
                }
                return acc;
              }, []);
              byGroup.sort((a, b) => a.stageOrder - b.stageOrder);
              return (
                <Box>
                  {byGroup.map(({ label, rows }) => (
                    <Box key={label} sx={{ mb: 2 }}>
                      <Typography
                        variant='caption'
                        sx={{
                          fontWeight: 600,
                          color: 'text.secondary',
                          display: 'block',
                          mb: 0.5,
                        }}
                      >
                        {label}
                      </Typography>
                      <Table size='small'>
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ width: '40%' }}>Task</TableCell>
                            <TableCell>Last run</TableCell>
                            <TableCell>Running</TableCell>
                            <TableCell>Queued</TableCell>
                            <TableCell>Runs / 60m</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {rows.map(p => (
                            <TableRow key={p.name}>
                              <TableCell
                                sx={{
                                  fontFamily: 'monospace',
                                  fontSize: '0.8rem',
                                }}
                              >
                                {p.name}
                                {p.parallel_group && (
                                  <Typography
                                    component='span'
                                    variant='caption'
                                    color='text.secondary'
                                    sx={{ ml: 0.5 }}
                                  >
                                    (parallel)
                                  </Typography>
                                )}
                              </TableCell>
                              <TableCell>
                                {p.last_run ? timeAgo(p.last_run) : 'never'}
                              </TableCell>
                              <TableCell>{p.running_tasks ?? 0}</TableCell>
                              <TableCell>{p.queued_tasks ?? 0}</TableCell>
                              <TableCell>{p.runs_last_60m ?? 0}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </Box>
                  ))}
                </Box>
              );
            })()
          )}
        </CardContent>
      </Card>

      {/* Decision log */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Coordinator decision log
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {loading && decisionEntries.length === 0 ? (
            <Skeleton variant='rectangular' height={80} />
          ) : decisionEntries.length === 0 ? (
            <Typography color='text.secondary' variant='body2'>
              No decisions yet. The coordinator logs collect_rss, process_phase,
              idle, etc.
            </Typography>
          ) : (
            <List dense disablePadding>
              {decisionEntries.slice(0, 20).map((e, i) => (
                <ListItem key={i} disablePadding sx={{ py: 0.3 }}>
                  <ListItemText
                    primary={
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Typography
                          component='span'
                          variant='body2'
                          sx={{ fontFamily: 'monospace' }}
                        >
                          {e.decision ?? '—'}
                        </Typography>
                        <Chip
                          size='small'
                          variant='outlined'
                          label={e.outcome ?? '—'}
                        />
                      </Box>
                    }
                    secondary={e.timestamp ? timeAgo(e.timestamp) : null}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

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
                    onChange={e => {
                      setTriggerPhaseName(e.target.value);
                      setForceNightlyUnifiedPipeline(false);
                    }}
                  >
                    <MenuItem value=''>Select…</MenuItem>
                    {(phases.length > 0
                      ? phases.map(p => p.name)
                      : [
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
                          'nightly_enrichment_context',
                        ]
                    ).map(name => (
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
                {triggerPhaseName === 'nightly_enrichment_context' && (
                  <FormControlLabel
                    control={
                      <Checkbox
                        size='small'
                        checked={forceNightlyUnifiedPipeline}
                        onChange={e =>
                          setForceNightlyUnifiedPipeline(e.target.checked)
                        }
                      />
                    }
                    label='Outside night window (force unified drain)'
                  />
                )}
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

      <Divider sx={{ my: 2 }} />

      {/* Collection status & quality */}
      <Typography variant='subtitle1' sx={{ fontWeight: 600, mb: 1 }}>
        Collection & quality
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
        <Card sx={{ minWidth: 280 }}>
          <CardHeader
            title='Collection status'
            subheader='Orchestrator last run'
          />
          <CardContent>
            {loading ? (
              <Skeleton variant='rectangular' height={80} />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {Object.entries(lastTimes).map(([source, time]) => (
                  <Box
                    key={source}
                    sx={{ display: 'flex', justifyContent: 'space-between' }}
                  >
                    <Typography variant='body2'>{source}</Typography>
                    <Typography variant='caption' color='text.secondary'>
                      {time ? new Date(time).toLocaleString() : '—'}
                    </Typography>
                  </Box>
                ))}
                {Object.keys(lastTimes).length === 0 && (
                  <Typography color='text.secondary'>
                    No collection data yet.
                  </Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 280 }}>
          <CardHeader
            title='Quality metrics'
            subheader='Context & entity coverage'
          />
          <CardContent>
            {loading ? (
              <Skeleton variant='rectangular' height={80} />
            ) : byDomain ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {Object.entries(byDomain).map(([d, row]) => (
                  <Box
                    key={d}
                    sx={{ display: 'flex', gap: 1, alignItems: 'center' }}
                  >
                    <Typography variant='body2'>{d}</Typography>
                    {row.context_coverage_pct != null && (
                      <Chip
                        size='small'
                        label={`Context: ${row.context_coverage_pct}%`}
                      />
                    )}
                    {row.entity_coverage_pct != null && (
                      <Chip
                        size='small'
                        label={`Entity: ${row.entity_coverage_pct}%`}
                      />
                    )}
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography color='text.secondary'>No quality data.</Typography>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
