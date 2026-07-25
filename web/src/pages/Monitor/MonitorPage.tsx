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
  heroBarEventsStoredCount,
} from '@/services/api/contextCentric';
import { getDefaultDomainKey, getDomainKeysList } from '@/utils/domainHelper';
import { useShellStatus } from '@/contexts/ShellStatusContext';
import { usePinnedThreads } from '@/hooks/usePinnedThreads';

/** Poll interval for full Monitor refresh (overview + pipeline + processing pulse together). */
const POLL_INTERVAL_MS = 15000;
/** Snapshot index refreshes server-side every ~15m; allow reuse until then + buffer. */
const PENDING_METRICS_MAX_AGE_MS = 16 * 60 * 1000;

type PhaseRow = {
  phase_name?: string;
  pending_records?: number | null;
  queue_depth?: number | null;
  pending_first_pass?: number | null;
  first_pass_depth?: number | null;
  pending_retry?: number | null;
  retry_depth?: number | null;
  scheduling_backlog?: number | null;
  intake_first_pass?: number | null;
  [key: string]: unknown;
};

function phaseQueueDepth(p: PhaseRow): number {
  return Number(p.queue_depth ?? p.pending_records ?? 0);
}

function phaseFirstPassDepth(p: PhaseRow): number {
  return Number(p.first_pass_depth ?? p.pending_first_pass ?? phaseQueueDepth(p));
}

/** Sort automation phases by first-pass queue (desc), then queue_depth, then name. */
function isMonitorVisiblePhase(p: {
  scheduling_status?: string;
  phase_name?: string;
  monitor_queue_kind?: string;
}): boolean {
  if (p.scheduling_status === 'retired') return false;
  // Hide rotating pools (e.g. storyline_automation) from the primary catch-up table.
  // Missing kind = drainable (backward compatible with older API payloads).
  const kind = p.monitor_queue_kind ?? 'drainable';
  return kind === 'drainable';
}

function filterMonitorPhases<T extends PhaseRow & { scheduling_status?: string }>(
  phases: T[]
): T[] {
  return phases.filter(isMonitorVisiblePhase);
}

function sortPhasesByPending<T extends PhaseRow>(phases: T[]): T[] {
  return [...phases].sort((a, b) => {
    const fa = phaseFirstPassDepth(a);
    const fb = phaseFirstPassDepth(b);
    if (fb !== fa) return fb - fa;
    const pa = phaseQueueDepth(a);
    const pb = phaseQueueDepth(b);
    if (pb !== pa) return pb - pa;
    const na = String(a.phase_name ?? '');
    const nb = String(b.phase_name ?? '');
    return na.localeCompare(nb);
  });
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
  /** Contexts→claims only: terminal no-claim inventory vs actionable queue. */
  backlog_breakdown?: {
    total_no_claims?: number;
    actionable_no_claims?: number;
    passed_no_claims_after_filters?: number;
    text_too_short_no_claims?: number;
  } | null;
  backlog_note?: string;
  last_1h?: number;
  last_24h?: number;
  last_7d?: number;
};

type ProcessingPulsePhase = {
  phase_name?: string;
  phase_key?: string;
  /** DB-backed count of records not yet processed for this phase (pending queue). */
  pending_records?: number;
  queue_depth?: number;
  scheduling_backlog?: number;
  /** Never cleared / first-time work for this phase. */
  pending_first_pass?: number;
  first_pass_depth?: number;
  /** Attempted but needs another pass (retry / reprocess). */
  pending_retry?: number;
  retry_depth?: number;
  /** First-pass items within intake window (fresh RSS backlog). */
  intake_first_pass?: number;
  work_queue_metric_kind?: string;
  /** drainable | rotating_pool | gated — primary table shows drainable only */
  monitor_queue_kind?: string;
  scheduling_status?: 'active' | 'suppressed' | 'retired' | string;
  queue_stale?: boolean;
  /** ceil(unprocessed ÷ rows_per_run); null if no row-batch model. How many phase runs to drain the queue. */
  batches_to_drain?: number | null;
  estimated_phase_runs?: number | null;
  /** ETA driver: measured 24h avg when available, else config batch size. */
  rows_per_run?: number | null;
  measured_rows_per_run_24h?: number | null;
  configured_rows_per_run?: number | null;
  rows_per_run_source?: string;
  rows_per_run_sample_count?: number;
  /** Legacy alias for rows_per_run. */
  estimated_batch_per_run?: number | null;
  estimated_batch_per_run_source?: string;
  runs_1h?: number;
  runs_24h?: number;
  runs_7d?: number;
  successes_24h?: number;
  failures_24h?: number;
  successes_7d?: number;
  failures_7d?: number;
  /** % of automation_run_history rows in window with success=true (not pipeline pass markers). */
  pass_rate_24h?: number | null;
  pass_rate_7d?: number | null;
  run_success_rate_24h?: number | null;
  run_success_rate_7d?: number | null;
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

function phaseRowsPerRunSource(p: ProcessingPulsePhase): string | undefined {
  return p.rows_per_run_source ?? p.estimated_batch_per_run_source;
}

function formatRowsPerRunCell(p: ProcessingPulsePhase): {
  main: string;
  subtitle?: string;
  muted?: boolean;
} {
  const source = phaseRowsPerRunSource(p);
  if (source === 'no_row_batch_model') {
    return { main: '—' };
  }
  const sampleCount = p.rows_per_run_sample_count ?? 0;
  if (source?.startsWith('measured_')) {
    const val = p.measured_rows_per_run_24h ?? p.rows_per_run ?? p.estimated_batch_per_run;
    return {
      main: formatPulseCount(val),
      subtitle: `n=${sampleCount} in 24h`,
    };
  }
  const cfg = p.configured_rows_per_run ?? p.estimated_batch_per_run ?? p.rows_per_run;
  // config_default = static BATCH_SIZE/env; adaptive_persisted = last auto-tuned batch
  const subtitle =
    source === 'adaptive_persisted' ? '(adaptive)' : '(config)';
  return {
    main: formatPulseCount(cfg),
    subtitle,
    muted: true,
  };
}

type QueueAuditPhase = {
  queue_depth?: number;
  monitor_pending?: number;
  matches_automation_sql?: boolean;
  matches_actionable_sql?: boolean;
  note?: string;
  error?: string;
  actionable_unified_intake?: number;
  spine_queue_depth?: number;
  inventory_missing_pass?: number;
  total_missing_unified_pass?: number;
  legacy_backfill_eligible?: number;
  automation_sql_recount?: number;
  actionable_no_claims_broad?: number;
  total_no_claims_inventory?: number;
};

/** UI-only labels for Monitor phase keys (API/DB keys unchanged). */
const MONITOR_PHASE_DISPLAY_LABELS: Record<string, string> = {
  // Chemistry SSOT — mirror api/shared/monitor_run_vocabulary.py CHEMISTRY_PHASE_DISPLAY_LABELS
  collision_sampling: 'Collision sampling (loose bonds)',
  stimulus_rag: 'Stimulus RAG (evidence pull)',
  protein_harden: 'Protein harden (establish edges)',
  embedding_link_candidates: 'Embedding link candidates',
  graph_connection_distillation: 'Graph connection distillation',
  // claim-topic pair
  topic_clustering: 'claim-topic · topic_clustering',
  claim_extraction: 'claim-topic · claim_extraction',
  // remote worker aliases
  unified_intake_extraction: 'uie · unified_intake_extraction',
  storyline_assembly: 'assembly · storyline_assembly',
};

/** Queue-audit labels; prefer MONITOR_PHASE_DISPLAY_LABELS via formatMonitorPhaseLabel. */
const QUEUE_AUDIT_PHASE_LABELS: Record<string, string> = {
  ...MONITOR_PHASE_DISPLAY_LABELS,
  entity_profile_build: 'entity_profile_build',
};

function formatMonitorPhaseLabel(phaseName: string): string {
  return MONITOR_PHASE_DISPLAY_LABELS[phaseName] ?? phaseName;
}

function formatQueueAuditCheck(phase: QueueAuditPhase): string {
  if (phase.error) return phase.error;
  const parts: string[] = [];
  if (phase.spine_queue_depth != null && phase.spine_queue_depth > 0) {
    const actionable =
      phase.actionable_unified_intake ?? phase.queue_depth ?? phase.monitor_pending;
    if (actionable != null && phase.spine_queue_depth !== actionable) {
      parts.push(`spine queue ${formatPulseCount(phase.spine_queue_depth)} (operational only)`);
    }
  }
  if (phase.actionable_unified_intake != null) {
    parts.push(`actionable ${formatPulseCount(phase.actionable_unified_intake)}`);
  }
  if (phase.automation_sql_recount != null) {
    parts.push(`vs automation SQL ${formatPulseCount(phase.automation_sql_recount)}`);
  }
  const inventory =
    phase.inventory_missing_pass ?? phase.total_missing_unified_pass;
  if (inventory != null) {
    parts.push(`inventory ${formatPulseCount(inventory)}`);
  }
  if (phase.legacy_backfill_eligible != null && phase.legacy_backfill_eligible > 0) {
    parts.push(`legacy backfill ${formatPulseCount(phase.legacy_backfill_eligible)}`);
  }
  if (phase.actionable_no_claims_broad != null) {
    parts.push(`broad no-claims ${formatPulseCount(phase.actionable_no_claims_broad)}`);
  }
  if (phase.total_no_claims_inventory != null) {
    parts.push(`all no-claim contexts ${formatPulseCount(phase.total_no_claims_inventory)}`);
  }
  return parts.join(' · ') || '—';
}

/**
 * Heuristic only: compare the latest hour to a baseline that avoids double-counting that hour
 * inside the 24h total. Baseline = mean completions over the other 23 hours in the rolling window;
 * if those are too sparse, fall back to mean over full 24h (still a rough rate, not a formal test).
 */
type ProcessingPulseState = {
  success?: boolean;
  data?: {
    generated_at_utc?: string;
    warming?: boolean;
    degraded?: boolean;
    pending_metrics_included?: boolean;
    dimension_throughput_included?: boolean;
    pending_metrics_as_of_utc?: string;
    intake_window_hours?: number;
    operator_metrics?: Record<string, unknown>;
    queue_audit?: { phases?: Record<string, QueueAuditPhase> };
    unified_intake_breakdown?: {
      actionable_unified_intake?: number;
      inventory_missing_pass?: number;
      legacy_backfill_eligible?: number;
      spine_queue_depth?: number;
    };
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
    hourly_phase_tick_bucket_count?: number | null;
  };
  error?: string;
};

/** Keep backlog_metrics columns when a fast-path poll refreshes throughput/run counts. */
function mergeProcessingPulseWithCachedPending(
  fast: ProcessingPulseState,
  cached: ProcessingPulseState | null
): { pulse: ProcessingPulseState; pendingStale: boolean } {
  if (!fast?.data) return { pulse: fast, pendingStale: false };

  const mergeDimensions = (next: NonNullable<ProcessingPulseState['data']>) => {
    const nextDims = next.dimensions ?? [];
    const cachedDims = cached?.data?.dimensions ?? [];
    if (next.dimension_throughput_included && nextDims.length > 0) {
      return {
        dimensions: nextDims,
        dimension_throughput_included: true as boolean | undefined,
      };
    }
    if (cachedDims.length > 0) {
      return {
        dimensions: cachedDims,
        dimension_throughput_included: true as boolean | undefined,
      };
    }
    return {
      dimensions: nextDims,
      dimension_throughput_included: next.dimension_throughput_included,
    };
  };

  // Warming stub must not wipe a good prior pulse while background rebuild finishes.
  if (fast.data.warming === true && cached?.data && !cached.data.warming) {
    return { pulse: cached, pendingStale: false };
  }

  if (fast.data.pending_metrics_included) {
    const phases = sortPhasesByPending(
      filterMonitorPhases(fast.data.phase_dashboard ?? fast.data.phases ?? [])
    );
    const dims = mergeDimensions(fast.data);
    return {
      pulse: {
        ...fast,
        data: {
          ...fast.data,
          phase_dashboard: phases,
          phases,
          ...dims,
        },
      },
      pendingStale: false,
    };
  }
  if (!cached?.data?.pending_metrics_included) {
    return { pulse: fast, pendingStale: true };
  }

  const cachedPhases = cached.data.phase_dashboard ?? cached.data.phases ?? [];
  const cachedByPhase = new Map(
    cachedPhases
      .filter(p => typeof p.phase_name === 'string' && p.phase_name.length > 0)
      .map(p => [p.phase_name as string, p])
  );
  if (cachedByPhase.size === 0) {
    return { pulse: fast, pendingStale: true };
  }

  const asOf =
    cached.data.pending_metrics_as_of_utc ?? cached.data.generated_at_utc;
  let pendingStale = false;
  if (asOf) {
    const age = Date.now() - new Date(asOf).getTime();
    if (!Number.isFinite(age) || age > PENDING_METRICS_MAX_AGE_MS) {
      pendingStale = true;
    }
  } else {
    pendingStale = true;
  }

  const fastPhases = fast.data.phase_dashboard ?? fast.data.phases ?? [];
  for (const p of fastPhases) {
    const name = p.phase_name;
    if (!name) continue;
    const c = cachedByPhase.get(name);
    if (!c) continue;
    if ((p.runs_1h ?? 0) > (c.runs_1h ?? 0)) {
      pendingStale = true;
      break;
    }
  }

  if (pendingStale) {
    return { pulse: fast, pendingStale: true };
  }

  const mergedPhases = sortPhasesByPending(
    filterMonitorPhases(
      fastPhases.map(p => {
        const name = p.phase_name;
        if (!name) return p;
        const c = cachedByPhase.get(name);
        if (!c) return p;
        return {
          ...p,
          pending_records: c.queue_depth ?? c.pending_records,
          queue_depth: c.queue_depth ?? c.pending_records,
          scheduling_backlog: c.scheduling_backlog,
          pending_first_pass: c.first_pass_depth ?? c.pending_first_pass,
          first_pass_depth: c.first_pass_depth ?? c.pending_first_pass,
          pending_retry: c.retry_depth ?? c.pending_retry,
          retry_depth: c.retry_depth ?? c.pending_retry,
          intake_first_pass: c.intake_first_pass,
          work_queue_metric_kind: c.work_queue_metric_kind,
          rows_per_run: c.rows_per_run ?? c.estimated_batch_per_run,
          measured_rows_per_run_24h: c.measured_rows_per_run_24h,
          configured_rows_per_run: c.configured_rows_per_run,
          rows_per_run_source: c.rows_per_run_source ?? c.estimated_batch_per_run_source,
          rows_per_run_sample_count: c.rows_per_run_sample_count,
          estimated_batch_per_run: c.rows_per_run ?? c.estimated_batch_per_run,
          estimated_batch_per_run_source:
            c.rows_per_run_source ?? c.estimated_batch_per_run_source,
          batches_to_drain: c.estimated_phase_runs ?? c.batches_to_drain,
          estimated_phase_runs: c.estimated_phase_runs ?? c.batches_to_drain,
        };
      })
    )
  );

  const dims = mergeDimensions(fast.data);
  return {
    pulse: {
      ...fast,
      data: {
        ...fast.data,
        phase_dashboard: mergedPhases,
        phases: mergedPhases,
        pending_metrics_included: true,
        pending_metrics_as_of_utc:
          cached.data.pending_metrics_as_of_utc ?? cached.data.generated_at_utc,
        operator_metrics: cached.data.operator_metrics ?? fast.data.operator_metrics,
        queue_audit: cached.data.queue_audit ?? fast.data.queue_audit,
        ...dims,
      },
    },
    pendingStale: false,
  };
}

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
    degraded?: boolean;
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
  const [processingPulse, setProcessingPulse] =
    useState<ProcessingPulseState | null>(null);
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
  const { ctxStatus: ccStatus, orchStatus: orchCollection } = useShellStatus();
  /** From GET /api/system_monitoring/automation/status — confirms FIFO vs legacy LIFO batch ordering. */
  const [pipelineArticleSelection, setPipelineArticleSelection] = useState<{
    mode?: string;
    label?: string;
    sql_created_at?: string;
    order_env?: string;
  } | null>(null);
  const [poposPhaseWorker, setPoposPhaseWorker] = useState<{
    alive?: boolean;
    age_sec?: number | null;
    workers?: number;
    cycle?: { last_run_at?: string | null; detail?: Record<string, unknown> } | null;
    cycles?: Array<{ phase_name?: string; last_run_at?: string | null; detail?: Record<string, unknown> }>;
    phases?: Array<{ phase_name?: string; last_run_at?: string | null; last_success?: boolean }>;
  } | null>(null);
  const [remoteOwnedPhases, setRemoteOwnedPhases] = useState<string[]>([]);


  /** Fast path: health + activity only — must not wait on pipeline/pulse (120s-class calls). */
  const refreshOverview = useCallback(async () => {
    const ov = await apiService.getMonitoringOverview();
    setOverview(ov ?? null);
    return ov;
  }, []);

  const [pendingMetricsLoading, setPendingMetricsLoading] = useState(false);

  /** Snapshot-backed pending counts (fast); use includePendingMetrics for live SQL refresh. */
  const fetchPendingMetrics = useCallback(async (live = false) => {
    setPendingMetricsLoading(true);
    try {
      const pulse = await apiService.getProcessingProgress(
        live
          ? { includePendingMetrics: true }
          : { useBacklogSnapshot: true }
      );
      if (pulse?.success && pulse.data) {
        setProcessingPulse(prev => {
          const fastPhases =
            prev?.data?.phase_dashboard ?? prev?.data?.phases ?? [];
          const fullPhases = pulse.data?.phase_dashboard ?? pulse.data?.phases ?? [];
          // Reject empty/warming snapshot that would wipe a good prior phase table.
          if (
            (pulse.data.warming === true || fullPhases.length === 0) &&
            (prev?.data?.phase_dashboard?.length || prev?.data?.phases?.length)
          ) {
            return prev;
          }
          if (fastPhases.length === 0 || fullPhases.length === 0) {
            const phases = sortPhasesByPending(
              filterMonitorPhases(fullPhases.length ? fullPhases : fastPhases)
            );
            return {
              ...pulse,
              data: {
                ...pulse.data,
                phase_dashboard: phases,
                phases,
                pending_metrics_as_of_utc:
                  pulse.data.pending_metrics_as_of_utc ?? pulse.data.generated_at_utc,
              },
            };
          }
          type PhaseRow = NonNullable<
            ProcessingPulseState['data']
          >['phase_dashboard'][number];
          const fullByPhase = new Map<string, PhaseRow>(
            fullPhases
              .filter((p): p is PhaseRow => Boolean(p.phase_name))
              .map(p => [p.phase_name as string, p])
          );
          const mergedPhases = sortPhasesByPending(
            filterMonitorPhases(
              fastPhases.map(p => {
                const name = p.phase_name;
                if (!name) return p;
                const row = fullByPhase.get(name);
                if (!row) return p;
                return {
                  ...p,
                  pending_records: row.queue_depth ?? row.pending_records,
                  queue_depth: row.queue_depth ?? row.pending_records,
                  scheduling_backlog: row.scheduling_backlog,
                  pending_first_pass: row.first_pass_depth ?? row.pending_first_pass,
                  first_pass_depth: row.first_pass_depth ?? row.pending_first_pass,
                  pending_retry: row.retry_depth ?? row.pending_retry,
                  retry_depth: row.retry_depth ?? row.pending_retry,
                  intake_first_pass: row.intake_first_pass,
                  work_queue_metric_kind: row.work_queue_metric_kind,
                  rows_per_run: row.rows_per_run ?? row.estimated_batch_per_run,
                  measured_rows_per_run_24h: row.measured_rows_per_run_24h,
                  configured_rows_per_run: row.configured_rows_per_run,
                  rows_per_run_source:
                    row.rows_per_run_source ?? row.estimated_batch_per_run_source,
                  rows_per_run_sample_count: row.rows_per_run_sample_count,
                  estimated_batch_per_run: row.rows_per_run ?? row.estimated_batch_per_run,
                  estimated_batch_per_run_source:
                    row.rows_per_run_source ?? row.estimated_batch_per_run_source,
                  batches_to_drain: row.estimated_phase_runs ?? row.batches_to_drain,
                  estimated_phase_runs: row.estimated_phase_runs ?? row.batches_to_drain,
                };
              })
            )
          );
          return {
            ...pulse,
            data: {
              ...pulse.data,
              phase_dashboard: mergedPhases,
              phases: mergedPhases,
              pending_metrics_included: true,
              pending_metrics_as_of_utc:
                pulse.data.pending_metrics_as_of_utc ?? pulse.data.generated_at_utc,
            },
          };
        });
      }
    } catch {
      /* getProcessingProgress returns { success: false } on failure */
    } finally {
      setPendingMetricsLoading(false);
    }
  }, []);

  /** Heavy panels: pipeline, pulse, GPU, automation — orchestrator/CC from ShellStatusContext. */
  const refreshHeavyPanels = useCallback(async () => {
    // Pipeline/automation first — single-worker API can queue behind a cold processing_progress build.
    const pipelineResult = await Promise.allSettled([
      apiService.getPipelineStatus(),
      apiService.getAutomationStatus().catch(() => null),
    ]);
    const pulseGpuResults = await Promise.allSettled([
      apiService.getProcessingProgress({ useBacklogSnapshot: true }),
      apiService.getGpuMetricHistory(72),
    ]);
    const results = [...pipelineResult, ...pulseGpuResults];
    const settledErr = (r: PromiseSettledResult<unknown>, label: string) =>
      r.status === 'rejected'
        ? { success: false as const, error: `${label}: ${(r.reason as Error)?.message ?? 'failed'}` }
        : null;
    const pipe =
      results[0].status === 'fulfilled' ? results[0].value : settledErr(results[0], 'pipeline_status');
    const autoEnvelope = results[1].status === 'fulfilled' ? results[1].value : null;
    const pulse =
      results[2].status === 'fulfilled' ? results[2].value : settledErr(results[2], 'processing_progress');
    const gpuH = results[3].status === 'fulfilled' ? results[3].value : null;
    setPipeline(pipe ?? null);
    if (pulse && typeof pulse === 'object' && 'success' in pulse) {
      setProcessingPulse(prev => {
        const { pulse: merged, pendingStale } = mergeProcessingPulseWithCachedPending(
          pulse as ProcessingPulseState,
          prev
        );
        if (pendingStale) {
          // Snapshot refresh only — live backlog_metrics SQL (includePendingMetrics)
          // takes 30–70s and saturates the UI DB pool, blocking the rest of the site.
          queueMicrotask(() => {
            void fetchPendingMetrics(false);
          });
        }
        return merged;
      });
    } else {
      setProcessingPulse(pulse ?? null);
    }
    setGpuMetricHistory(gpuH ?? null);
    const autoData = (
      autoEnvelope as {
        data?: {
          pipeline_article_selection?: {
            mode?: string;
            label?: string;
            sql_created_at?: string;
            order_env?: string;
          };
          popos_phase_worker?: {
            alive?: boolean;
            age_sec?: number | null;
            cycle?: { last_run_at?: string | null; detail?: Record<string, unknown> } | null;
            phases?: Array<{
              phase_name?: string;
              last_run_at?: string | null;
              last_success?: boolean;
            }>;
          };
          remote_owned_phases?: string[];
        };
      } | null
    )?.data;
    setPipelineArticleSelection(autoData?.pipeline_article_selection ?? null);
    setPoposPhaseWorker(autoData?.popos_phase_worker ?? null);
    setRemoteOwnedPhases(
      Array.isArray(autoData?.remote_owned_phases) ? autoData.remote_owned_phases : []
    );
  }, [fetchPendingMetrics]);

  /** Full monitor refresh after manual phase trigger (overview + heavy + pending metrics). */
  const refreshMonitor = useCallback(async () => {
    await refreshOverview();
    void refreshHeavyPanels();
    void fetchPendingMetrics();
  }, [refreshOverview, refreshHeavyPanels, fetchPendingMetrics]);

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
    let pollTick = 0;

    void (async () => {
      setInitialLoad(true);
      setError(null);
      try {
        // Unblock health/activity UI as soon as overview returns (do not wait on 120s pipeline/pulse).
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

      /** Wait for each tick to finish before scheduling the next (no overlapping bundles). */
      const schedulePoll = () => {
        pollTimeoutId = setTimeout(() => {
          void (async () => {
            if (cancelled) return;
            try {
              await refreshOverview();
              void refreshHeavyPanels();
              pollTick += 1;
              // Refresh queue depths ~every 30s (backlog SQL is heavy for every 15s poll).
              if (pollTick % 2 === 0) void fetchPendingMetrics();
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
      'entity_profile_sync',
      'claim_extraction',
      'claims_to_facts',
      'event_tracking',
      'topic_clustering',
      'entity_profile_build',
      'unified_intake_extraction',
    ],
    []
  );

  const runPhaseOptions = useMemo(() => {
    const rows = filterMonitorPhases(
      processingPulse?.data?.phase_dashboard ??
        processingPulse?.data?.phases ??
        []
    );
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
    !initialLoad &&
    overview != null &&
    overview.success === false &&
    overview.degraded !== true;
  const overviewDegraded =
    !initialLoad && overview != null && overview.degraded === true;

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
      {overviewDegraded && !overviewLoadFailed && (overview?.error as string) && (
        <Alert severity='warning' sx={{ mb: 2 }}>
          Monitoring overview loaded with reduced detail (API was slow under load).{' '}
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
      {(remoteOwnedPhases.length > 0 || poposPhaseWorker) && (
        <Alert
          severity={poposPhaseWorker?.alive ? 'success' : 'warning'}
          sx={{ mb: 2, py: 0.5 }}
        >
          {poposPhaseWorker?.alive ? (
            <>
              PopOS phase worker
              {typeof poposPhaseWorker.workers === 'number' && poposPhaseWorker.workers > 0
                ? `s (${poposPhaseWorker.workers} processes)`
                : ''}{' '}
              heartbeat OK
              {poposPhaseWorker.age_sec != null
                ? ` (${Math.round(poposPhaseWorker.age_sec)}s ago)`
                : ''}
              {remoteOwnedPhases.length > 0
                ? ` — remote-owned: ${remoteOwnedPhases.join(', ')}`
                : ''}
              . Widow AutomationManager does not drain those phases locally.
            </>
          ) : (
            <>
              PopOS phase worker heartbeat missing or stale
              {remoteOwnedPhases.length > 0
                ? ` (Widow still owns schedule disable for: ${remoteOwnedPhases.join(', ')})`
                : ''}
              . Check <code>news-intelligence-popos-worker</code> on PopOS — Monitor
              Widow workers alone will look idle for remote phases.
            </>
          )}
        </Alert>
      )}
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
              No background tasks running right now on Widow or PopOS. Remote-owned
              drains appear here while PopOS workers report{' '}
              <code>status=running</code> heartbeats.
            </Typography>
          ) : (
            <List dense disablePadding>
              {currentActivities.map((a, i) => {
                const runEst = activityRunEstimateSecondary(a);
                const host =
                  a.execution_host === 'popos'
                    ? 'PopOS'
                    : a.execution_host === 'widow'
                      ? 'Widow'
                      : null;
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
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 0.5,
                              flexShrink: 0,
                            }}
                          >
                            {host ? (
                              <Chip
                                size='small'
                                variant='outlined'
                                color={host === 'PopOS' ? 'secondary' : 'default'}
                                label={host}
                                sx={{
                                  height: 22,
                                  '& .MuiChip-label': {
                                    px: 0.75,
                                    py: 0,
                                    fontSize: '0.7rem',
                                  },
                                }}
                              />
                            ) : null}
                            <Chip
                              size='small'
                              variant='outlined'
                              label={`×${
                                typeof a.running_instances === 'number'
                                  ? a.running_instances
                                  : 1
                              }`}
                              sx={{
                                height: 22,
                                '& .MuiChip-label': {
                                  px: 0.75,
                                  py: 0,
                                  fontSize: '0.7rem',
                                },
                              }}
                            />
                          </Box>
                        </Box>
                      }
                      secondary={
                        <span>
                          {a.started_at ? timeAgo(a.started_at as string) : '—'}
                          {typeof a.worker_id === 'string' && a.worker_id
                            ? ` · worker ${a.worker_id}`
                            : null}
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
        scheduler task).         <strong>Pass %</strong> ={' '}
        <code style={{ fontSize: '0.85em' }}>100 × successes ÷ completions</code> in the window (run
        success rate — not the same as pipeline &quot;first pass&quot; queue columns); SQL
        treats non-TRUE <code style={{ fontSize: '0.85em' }}>success</code> (FALSE or NULL) as not passed —
        a sample proportion, not a confidence interval. Chip arrows compare the last hour to a baseline
        rate (see tooltips; heuristic only). Dimension chips are SQL throughputs, not mutually exclusive
        pipeline stages.
      </Typography>
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {processingPulse?.success && processingPulse.data ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {processingPulse.data.warming === true && (
                <Alert severity='info' sx={{ py: 0.5 }}>
                  Processing pulse snapshot is building — phase table fills on the next refresh (~15s).
                </Alert>
              )}
              {processingPulse.data.pending_metrics_included === false && (
                <Alert severity='info' sx={{ py: 0.5 }}>
                  {pendingMetricsLoading ? (
                    <>
                      Loading <strong>unprocessed row</strong> counts from backlog_metrics…
                    </>
                  ) : (
                    <>
                      Per-phase <strong>unprocessed rows</strong> are not loaded yet (fast path
                      refresh). Throughput chips and run counts still reflect the last 7 days. Queue
                      depths refresh automatically every ~30s or after phase runs.
                    </>
                  )}
                </Alert>
              )}
              {processingPulse.data.dimension_throughput_included === false &&
                (processingPulse.data.dimensions ?? []).length === 0 &&
                processingPulse.data.warming !== true && (
                <Alert severity='info' sx={{ py: 0.5 }}>
                  Dimension throughput chips are still loading (cached with the pulse snapshot).
                  Phase queue and run history are current.
                </Alert>
              )}
              {processingPulse.data.pending_metrics_included === true &&
                processingPulse.data.pending_metrics_as_of_utc && (
                  <Typography variant='caption' color='text.secondary'>
                    Queue depths as of{' '}
                    {shortLocalDateTime(processingPulse.data.pending_metrics_as_of_utc)} — first-pass /
                    retry / intake columns refresh with the ~15m snapshot index
                    {processingPulse.data.intake_window_hours != null
                      ? ` (intake window ${processingPulse.data.intake_window_hours}h)`
                      : ''}
                    ; throughput and run counts update every 15s
                  </Typography>
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
                    const inv =
                      d.id === 'contexts_claimed' &&
                      d.backlog_breakdown?.total_no_claims != null &&
                      (d.backlog_breakdown.total_no_claims ?? 0) >
                        (d.backlog ?? 0)
                        ? ` · ${formatPulseCount(d.backlog_breakdown.total_no_claims)} terminal (no claims, already processed)`
                        : '';
                    const bl =
                      d.backlog != null
                        ? `queue ${formatPulseCount(d.backlog)}${inv} · `
                        : '';
                    const titleExtra =
                      d.id === 'contexts_claimed' && d.backlog_note
                        ? `\n\n${d.backlog_note}`
                        : '';
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
                        title={`${t.title}\n${d.label}\n${bl}1h ${d.last_1h ?? '—'} · 24h ${d.last_24h ?? '—'} · 7d ${d.last_7d ?? '—'}${titleExtra}`}
                      />
                    );
                  })}
                </Stack>
              </Box>
              <Divider />
              <Box>
                {(() => {
                  const om = processingPulse.data.operator_metrics ?? {};
                  const reviewPending = Number(om.storyline_review_queue_pending ?? 0);
                  const byDomain = (om.storyline_review_queue_pending_by_domain ??
                    {}) as Record<string, number>;
                  const domainBits = Object.entries(byDomain)
                    .filter(([, n]) => Number(n) > 0)
                    .sort((a, b) => Number(b[1]) - Number(a[1]))
                    .map(([d, n]) => `${d} ${formatPulseCount(n)}`)
                    .join(' · ');
                  return (
                    <Chip
                      size='small'
                      color={reviewPending > 0 ? 'warning' : 'default'}
                      variant='outlined'
                      sx={{ mb: 1 }}
                      label={`Storyline review queue · ${formatPulseCount(reviewPending)} pending`}
                      title={
                        domainBits
                          ? `Pending article suggestions awaiting approve/reject\n${domainBits}`
                          : 'Pending article suggestions awaiting approve/reject (storyline_review_agent)'
                      }
                    />
                  );
                })()}
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.75 }}>
                  Automation phases — each Total queue is an independent per-phase depth (articles,
                  contexts, or profiles). Do not sum across rows; correlated pipeline stages overlap.
                  First-time work, retries, fresh intake; modeled rows per run and estimated runs to
                  clear; then pass/fail when the phase completes. Rotating pools (e.g. storyline
                  automation) are omitted from this table.
                </Typography>
                <Table size='small' sx={{ '& td': { py: 0.5 } }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>Phase</TableCell>
                      <TableCell
                        align='right'
                        title='queue_depth: actionable work remaining (same eligibility SQL automation uses). scheduling_backlog is excess beyond one batch tick.'
                      >
                        queue_depth
                      </TableCell>
                      <TableCell
                        align='right'
                        title='Never successfully cleared — grows with intake, shrinks as automation catches up'
                      >
                        First pass
                      </TableCell>
                      <TableCell
                        align='right'
                        title='Attempted but needs another pass (failed / legacy false-clear)'
                      >
                        Retry
                      </TableCell>
                      <TableCell
                        align='right'
                        title='First-pass items created within the intake window (default 72h)'
                      >
                        New intake
                      </TableCell>
                      <TableCell
                        align='right'
                        title={
                          processingPulse.data.reporting_definitions?.rows_per_run ??
                          'Rows per phase run: measured 24h average when batch history exists, else configured batch size'
                        }
                      >
                        Rows/run
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
                      <TableCell
                        align='right'
                        title='Run success rate: scheduler completions marked success=TRUE (not pipeline first-pass queue)'
                      >
                        Run success % 24h
                      </TableCell>
                      <TableCell
                        align='right'
                        title='Run success rate over 7 days (scheduler completions, not pipeline pass markers)'
                      >
                        Run success % 7d
                      </TableCell>
                      <TableCell align='right'>Avg s</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sortPhasesByPending(
                      filterMonitorPhases(
                        processingPulse.data.phase_dashboard ??
                          processingPulse.data.phases ??
                          []
                      )
                    )
                      .slice(0, 40)
                      .map(p => (
                        <TableRow
                          key={p.phase_name}
                          sx={
                            p.queue_stale
                              ? { '& td': { bgcolor: 'action.hover' } }
                              : undefined
                          }
                        >
                          <TableCell>
                            {formatMonitorPhaseLabel(p.phase_name ?? '')}
                            {p.scheduling_status === 'suppressed' && (
                              <Typography
                                component='span'
                                variant='caption'
                                color='text.secondary'
                                sx={{ display: 'block' }}
                              >
                                suppressed (intake mode)
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell align='right'>
                            {formatPulseCount(phaseQueueDepth(p))}
                            {(p.scheduling_backlog ?? 0) > 0 &&
                              (p.scheduling_backlog ?? 0) !== phaseQueueDepth(p) && (
                                <Typography
                                  component='span'
                                  variant='caption'
                                  color='text.secondary'
                                  sx={{ display: 'block' }}
                                >
                                  sched {formatPulseCount(p.scheduling_backlog)}
                                </Typography>
                              )}
                          </TableCell>
                          <TableCell align='right'>
                            {phaseFirstPassDepth(p) > 0 ? (
                              <Typography
                                component='span'
                                variant='body2'
                                color={
                                  (p.intake_first_pass ?? 0) > 0 ? 'info.main' : 'text.primary'
                                }
                              >
                                {formatPulseCount(phaseFirstPassDepth(p))}
                              </Typography>
                            ) : (
                              formatPulseCount(0)
                            )}
                          </TableCell>
                          <TableCell align='right'>
                            {(p.pending_retry ?? 0) > 0 ? (
                              <Typography component='span' variant='body2' color='warning.main'>
                                {formatPulseCount(p.pending_retry ?? 0)}
                              </Typography>
                            ) : (
                              formatPulseCount(0)
                            )}
                          </TableCell>
                          <TableCell align='right'>
                            {(p.intake_first_pass ?? 0) > 0 ? (
                              <Typography component='span' variant='body2' color='info.main'>
                                {formatPulseCount(p.intake_first_pass ?? 0)}
                              </Typography>
                            ) : (
                              formatPulseCount(0)
                            )}
                          </TableCell>
                          <TableCell align='right'>
                            {(() => {
                              const cell = formatRowsPerRunCell(p);
                              if (cell.subtitle) {
                                return (
                                  <Box sx={{ lineHeight: 1.2 }}>
                                    <Typography
                                      component='span'
                                      variant='body2'
                                      color={cell.muted ? 'text.secondary' : 'text.primary'}
                                    >
                                      {cell.main}
                                    </Typography>
                                    <Typography
                                      component='div'
                                      variant='caption'
                                      color='text.secondary'
                                    >
                                      {cell.subtitle}
                                    </Typography>
                                  </Box>
                                );
                              }
                              return cell.main;
                            })()}
                          </TableCell>
                          <TableCell align='right'>
                            {(() => {
                              const runsToClear =
                                p.estimated_phase_runs ?? p.batches_to_drain;
                              if (runsToClear == null) return '—';
                              if ((runsToClear ?? 0) > 1) {
                                return (
                                  <Typography
                                    component='span'
                                    variant='body2'
                                    color='warning.main'
                                  >
                                    {formatPulseCount(runsToClear)}
                                  </Typography>
                                );
                              }
                              return formatPulseCount(runsToClear);
                            })()}
                          </TableCell>
                          <TableCell align='right'>{p.runs_1h ?? 0}</TableCell>
                          <TableCell
                            align='right'
                            title={
                              p.queue_stale
                                ? 'Backlog exists but no meaningful completions in the last 24h'
                                : undefined
                            }
                          >
                            {(p.runs_24h ?? 0) === 0 && p.queue_stale ? (
                              <Typography component='span' variant='body2' color='warning.main'>
                                {p.runs_24h ?? 0}
                              </Typography>
                            ) : (
                              p.runs_24h ?? 0
                            )}
                          </TableCell>
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
                            {(p.run_success_rate_24h ?? p.pass_rate_24h) != null
                              ? `${p.run_success_rate_24h ?? p.pass_rate_24h}%`
                              : '—'}
                          </TableCell>
                          <TableCell align='right'>
                            {(p.run_success_rate_7d ?? p.pass_rate_7d) != null
                              ? `${p.run_success_rate_7d ?? p.pass_rate_7d}%`
                              : '—'}
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
                {filterMonitorPhases(
                  processingPulse.data.phase_dashboard ?? processingPulse.data.phases ?? []
                ).length > 40 && (
                  <Typography variant='caption' color='text.secondary' sx={{ mt: 0.5, display: 'block' }}>
                    Showing 40 rows sorted by first-pass queue, then total pending.
                  </Typography>
                )}
              </Box>
              {processingPulse.data.queue_audit?.phases &&
                Object.keys(processingPulse.data.queue_audit.phases).length > 0 && (
                  <>
                    <Divider />
                    <Box>
                      <Typography
                        variant='caption'
                        color='text.secondary'
                        sx={{ display: 'block', mb: 0.75 }}
                      >
                        Queue audit — independent SQL cross-checks for queue_depth (not duplicate
                        totals). Mismatch means investigate backlog_metrics vs inventory definitions.
                      </Typography>
                      <Table size='small' sx={{ '& td': { py: 0.5 } }}>
                        <TableHead>
                          <TableRow>
                            <TableCell>Phase</TableCell>
                            <TableCell align='right'>queue_depth</TableCell>
                            <TableCell align='right'>Actionable</TableCell>
                            <TableCell align='right'>Spine queue</TableCell>
                            <TableCell align='right'>Inventory</TableCell>
                            <TableCell align='center'>SQL match</TableCell>
                            <TableCell>Cross-check</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {Object.entries(processingPulse.data.queue_audit.phases).map(
                            ([key, row]) => {
                              const depth = row.queue_depth ?? row.monitor_pending ?? 0;
                              const actionable = row.actionable_unified_intake;
                              const spine = row.spine_queue_depth;
                              const inventory =
                                row.inventory_missing_pass ?? row.total_missing_unified_pass;
                              const sqlMatch =
                                row.matches_actionable_sql ?? row.matches_automation_sql;
                              return (
                              <TableRow key={key}>
                                <TableCell>{QUEUE_AUDIT_PHASE_LABELS[key] ?? key}</TableCell>
                                <TableCell align='right'>
                                  {formatPulseCount(depth)}
                                </TableCell>
                                <TableCell align='right'>
                                  {actionable != null ? formatPulseCount(actionable) : '—'}
                                </TableCell>
                                <TableCell align='right'>
                                  {spine != null && spine > 0 ? formatPulseCount(spine) : '—'}
                                </TableCell>
                                <TableCell align='right'>
                                  {inventory != null ? formatPulseCount(inventory) : '—'}
                                </TableCell>
                                <TableCell align='center'>
                                  {row.error ? (
                                    '—'
                                  ) : sqlMatch ? (
                                    <Typography component='span' color='success.main'>
                                      yes
                                    </Typography>
                                  ) : (
                                    <Typography component='span' color='warning.main'>
                                      no
                                    </Typography>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <Typography variant='body2' title={row.note}>
                                    {formatQueueAuditCheck(row)}
                                  </Typography>
                                </TableCell>
                              </TableRow>
                            );
                            }
                          )}
                        </TableBody>
                      </Table>
                    </Box>
                  </>
                )}
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
                        {formatMonitorPhaseLabel(name)}
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
