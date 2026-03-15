/**
 * Monitor — System health, connection status, live activity, and pipeline visibility.
 * Shows API/DB/webserver status, current & recent activity, collection/quality,
 * pipeline status, phase timeline (last run / next due), decision log, and optional phase trigger.
 */
import React, { useEffect, useState, useCallback } from 'react';
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
  InputLabel,
  Select,
  MenuItem,
  Button,
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
import { contextCentricApi } from '@/services/api/contextCentric';

const POLL_INTERVAL_MS = 4500;

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

function formatDueIn(lastRunIso: string | null, intervalSeconds: number): string {
  if (!intervalSeconds || intervalSeconds <= 0) return '—';
  if (!lastRunIso) return 'due now';
  const last = new Date(lastRunIso).getTime();
  const next = last + intervalSeconds * 1000;
  const now = Date.now();
  if (next <= now) return 'due now';
  const sec = Math.floor((next - now) / 1000);
  if (sec < 60) return `in ${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `in ${min}m`;
  return `in ${Math.floor(min / 60)}h`;
}

type PhaseRow = { name: string; last_run: string | null; interval_seconds?: number; enabled?: boolean; phase?: number; phase_group_label?: string; parallel_group?: string };
type DecisionEntry = { decision?: string; outcome?: string; factors?: Record<string, unknown>; timestamp?: string };

export default function MonitorPage() {
  const [overview, setOverview] = useState<{
    success?: boolean;
    connections?: Record<string, unknown>;
    activities?: { current?: Array<Record<string, unknown>>; recent?: Array<Record<string, unknown>> };
    error?: string;
  } | null>(null);
  const [orchDashboard, setOrchDashboard] = useState<{
    status?: Record<string, unknown>;
    decision_log?: { entries?: DecisionEntry[] };
  } | null>(null);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [pipeline, setPipeline] = useState<{ success?: boolean; data?: Record<string, unknown> } | null>(null);
  const [automation, setAutomation] = useState<{ success?: boolean; data?: { phases?: PhaseRow[]; queue_size?: number; is_running?: boolean; active_workers?: number } } | null>(null);
  const [sourcesCollected, setSourcesCollected] = useState<{
    success?: boolean;
    data?: {
      window_minutes?: number;
      rss_feeds?: Array<{ feed_name: string; feed_url: string; domain: string; last_fetched_at: string }>;
      orchestrator_sources?: Array<{ source_id: string; last_collected_at: string }>;
      pipeline_stages?: Array<{ stage: string; last_run_at: string }>;
      summary?: string[];
    };
  } | null>(null);
  const [runSummary, setRunSummary] = useState<{
    success?: boolean;
    data?: {
      window_hours?: number;
      phases_run_recently?: Array<{ name: string; last_run: string | null; interval_seconds?: number }>;
      phases_not_run_recently?: Array<{ name: string; last_run: string | null; interval_seconds?: number }>;
      pipeline_checkpoints_recent?: Array<{ stage: string; status: string; timestamp: string }>;
      recent_activity?: Array<{ timestamp?: string; component?: string; event_type?: string; status?: string; message?: string }>;
    };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggerPhaseName, setTriggerPhaseName] = useState<string>('');
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{ success: boolean; message: string; warning?: string } | null>(null);

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
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        await loadOverview();
        if (cancelled) return;
        const [o, q, pipe, auto, sources, summary] = await Promise.all([
          apiService.getOrchestratorDashboard?.({ decision_log_limit: 25 }).then((d: unknown) => d as { status?: Record<string, unknown>; decision_log?: { entries?: DecisionEntry[] } }).catch(() => null),
          contextCentricApi.getQuality().catch(() => null),
          apiService.getPipelineStatus?.().then((r: unknown) => r as { success?: boolean; data?: Record<string, unknown> }).catch(() => null),
          apiService.getAutomationStatus?.().then((r: unknown) => r as { success?: boolean; data?: { phases?: PhaseRow[] } }).catch(() => null),
          apiService.getSourcesCollected?.(30).then((r: unknown) => r as typeof sourcesCollected).catch(() => null),
          apiService.getProcessRunSummary?.(24, 60).then((r: unknown) => r as typeof runSummary).catch(() => null),
        ]);
        if (cancelled) return;
        setOrchDashboard(o ?? null);
        setQuality(q ?? null);
        setPipeline(pipe ?? null);
        setAutomation(auto ?? null);
        setSourcesCollected(sources ?? null);
        setRunSummary(summary ?? null);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const t = setInterval(() => {
      loadOverview();
      apiService.getAutomationStatus?.().then((r: unknown) => setAutomation(r as typeof automation)).catch(() => {});
      apiService.getPipelineStatus?.().then((r: unknown) => setPipeline(r as typeof pipeline)).catch(() => {});
      apiService.getOrchestratorDashboard?.({ decision_log_limit: 25 }).then((d: unknown) => setOrchDashboard(d as typeof orchDashboard)).catch(() => {});
      apiService.getSourcesCollected?.(30).then((r: unknown) => setSourcesCollected(r as typeof sourcesCollected)).catch(() => {});
      apiService.getProcessRunSummary?.(24, 60).then((r: unknown) => setRunSummary(r as typeof runSummary)).catch(() => {});
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [loadOverview]);

  const handleTriggerPhase = async () => {
    if (!triggerPhaseName || !apiService.triggerPhase) return;
    setTriggering(true);
    setTriggerResult(null);
    try {
      const result = await apiService.triggerPhase(triggerPhaseName) as { success?: boolean; message?: string; error?: string; warning?: string };
      if (result?.success !== false) {
        setTriggerResult({
          success: true,
          message: (result?.message as string) || `Phase "${triggerPhaseName}" requested.`,
          warning: result?.warning as string | undefined,
        });
        setTriggerPhaseName('');
        loadOverview();
        // Refresh again so Current activity shows "Requested — queued" then "Running..." when the worker starts
        setTimeout(loadOverview, 2500);
        setTimeout(loadOverview, 6000);
      } else {
        setTriggerResult({ success: false, message: (result?.error as string) || 'Request failed.' });
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
  const webserver = connections?.webserver as Record<string, unknown> | undefined;
  const wsStatus = webserver?.status as string | undefined;
  const currentActivities = (overview?.activities as { current?: Array<Record<string, unknown>> })?.current ?? [];
  const recentActivities = (overview?.activities as { recent?: Array<Record<string, unknown>> })?.recent ?? [];

  const lastTimes = (orchStatus?.last_collection_times as Record<string, string> | undefined) ?? {};
  const byDomain = quality?.by_domain as Record<string, { context_coverage_pct?: number; entity_coverage_pct?: number }> | undefined;
  const decisionLog = orchDashboard?.decision_log as { entries?: DecisionEntry[] } | undefined;
  const decisionEntries = decisionLog?.entries ?? [];
  const pipelineData = pipeline?.data ?? {};
  const pipelineStatus = pipelineData?.pipeline_status as string | undefined;
  const phases: PhaseRow[] = automation?.data?.phases ?? [];
  const queueSize = automation?.data?.queue_size as number | undefined;
  const automationRunning = automation?.data?.is_running as boolean | undefined;

  const statusChip = (status: string | undefined, label: string) => {
    const ok = status === 'ok' || status === 'healthy' || status === 'HEALTHY';
    return (
      <Chip
        size="small"
        icon={ok ? <CheckCircleOutlineIcon /> : <ErrorOutlineIcon />}
        label={label}
        color={ok ? 'success' : 'error'}
        variant="outlined"
        sx={{ mr: 1 }}
      />
    );
  };

  const pipelineStatusColor = pipelineStatus === 'running' ? 'info' : pipelineStatus === 'error' ? 'error' : pipelineStatus === 'healthy' ? 'success' : 'default';

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

      {/* Connection status */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        System health & connection status
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Card variant="outlined" sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <ApiIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {loading && !overview ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(apiStatus ?? (overview?.success ? 'ok' : undefined), 'API')
              )}
            </Box>
            <Typography variant="caption" color="text.secondary">Backend API</Typography>
          </CardContent>
        </Card>
        <Card variant="outlined" sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <StorageIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {loading && !overview ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(dbStatus, 'Database')
              )}
            </Box>
            <Typography variant="caption" color="text.secondary">PostgreSQL</Typography>
          </CardContent>
        </Card>
        <Card variant="outlined" sx={{ minWidth: 160 }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <PublicIcon sx={{ mr: 1, color: 'text.secondary' }} />
              {loading && !overview ? (
                <Skeleton width={80} height={24} />
              ) : (
                statusChip(wsStatus, 'Web server')
              )}
            </Box>
            <Typography variant="caption" color="text.secondary">Frontend / proxy</Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Current activities */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Current activity
      </Typography>
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {loading && currentActivities.length === 0 ? (
            <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 1 }} />
          ) : currentActivities.length === 0 ? (
            <Typography color="text.secondary" variant="body2">
              No background tasks running right now. The system will show items like &quot;Running RSS collection&quot; or &quot;Processing storyline X&quot; when work is in progress.
            </Typography>
          ) : (
            <List dense disablePadding>
              {currentActivities.map((a, i) => (
                <ListItem key={(a.id as string) || i} disablePadding sx={{ py: 0.5 }}>
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    <RefreshIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={(a.message as string) || 'Working…'}
                    secondary={a.started_at ? timeAgo(a.started_at as string) : null}
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
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Recent activity
          </Typography>
          <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent sx={{ py: 1.5 }}>
              <List dense disablePadding>
                {recentActivities.slice(0, 10).map((a, i) => (
                  <ListItem key={(a.id as string) || i} disablePadding sx={{ py: 0.5 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {(a.success as boolean) !== false ? (
                        <CheckCircleOutlineIcon sx={{ color: 'success.main', fontSize: 20 }} />
                      ) : (
                        <ErrorOutlineIcon sx={{ color: 'error.main', fontSize: 20 }} />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={(a.message as string) || '—'}
                      secondary={a.completed_at ? timeAgo(a.completed_at as string) : null}
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
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Sources collected (last 30 min)
      </Typography>
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {sourcesCollected?.data && (sourcesCollected.data.rss_feeds?.length ?? 0) + (sourcesCollected.data.orchestrator_sources?.length ?? 0) + (sourcesCollected.data.pipeline_stages?.length ?? 0) > 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {sourcesCollected.data.rss_feeds && sourcesCollected.data.rss_feeds.length > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    RSS feeds
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                    {sourcesCollected.data.rss_feeds.slice(0, 12).map((f, i) => (
                      <Box key={i} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <Chip
                          size="small"
                          variant="outlined"
                          label={f.feed_name.length > 28 ? `${f.feed_name.slice(0, 26)}…` : f.feed_name}
                          title={f.feed_name}
                          sx={{ maxWidth: 200 }}
                        />
                        <Typography component="span" variant="caption" color="text.secondary">
                          {f.last_fetched_at ? timeAgo(f.last_fetched_at) : '—'}
                        </Typography>
                      </Box>
                    ))}
                    {sourcesCollected.data.rss_feeds.length > 12 && (
                      <Chip size="small" variant="outlined" label={`+${sourcesCollected.data.rss_feeds.length - 12} more`} />
                    )}
                  </Box>
                </Box>
              )}
              {sourcesCollected.data.orchestrator_sources && sourcesCollected.data.orchestrator_sources.length > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Other sources
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                    {sourcesCollected.data.orchestrator_sources.map((s, i) => (
                      <Box key={i} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <Chip size="small" color="primary" variant="outlined" label={s.source_id} />
                        <Typography component="span" variant="caption" color="text.secondary">
                          {s.last_collected_at ? timeAgo(s.last_collected_at) : '—'}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              )}
              {sourcesCollected.data.pipeline_stages && sourcesCollected.data.pipeline_stages.length > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Pipeline stages
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                    {sourcesCollected.data.pipeline_stages.map((s, i) => (
                      <Box key={i} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <Chip size="small" variant="outlined" label={s.stage.replace(/_/g, ' ')} />
                        <Typography component="span" variant="caption" color="text.secondary">
                          {s.last_run_at ? timeAgo(s.last_run_at) : '—'}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              )}
            </Box>
          ) : (
            <Typography color="text.secondary" variant="body2">
              No sources in the last {sourcesCollected?.data?.window_minutes ?? 30} minutes.
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Process run summary: what has run vs not triggered recently */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Process run summary (last 24h)
      </Typography>
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {runSummary?.data ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
                <Typography variant="body2">
                  <strong>Phases run:</strong> {runSummary.data.phases_run_recently?.length ?? 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  <strong>Not run / never:</strong> {runSummary.data.phases_not_run_recently?.length ?? 0}
                </Typography>
                {runSummary.data.pipeline_checkpoints_recent?.length != null && runSummary.data.pipeline_checkpoints_recent.length > 0 && (
                  <Typography variant="body2" color="text.secondary">
                    <strong>Pipeline checkpoints:</strong> {runSummary.data.pipeline_checkpoints_recent.length}
                  </Typography>
                )}
              </Box>
              {runSummary.data.phases_not_run_recently && runSummary.data.phases_not_run_recently.length > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Phases not run in last 24h (or never)
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {runSummary.data.phases_not_run_recently.slice(0, 20).map((p, i) => (
                      <Chip
                        key={i}
                        size="small"
                        variant="outlined"
                        label={p.name}
                        title={p.last_run ? `Last run: ${p.last_run}` : 'Never run'}
                      />
                    ))}
                    {runSummary.data.phases_not_run_recently.length > 20 && (
                      <Chip size="small" variant="outlined" label={`+${runSummary.data.phases_not_run_recently.length - 20} more`} />
                    )}
                  </Box>
                </Box>
              )}
              {runSummary.data.recent_activity && runSummary.data.recent_activity.length > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Recent activity (from logs)
                  </Typography>
                  <List dense disablePadding sx={{ maxHeight: 180, overflow: 'auto' }}>
                    {runSummary.data.recent_activity.slice(-12).reverse().map((a, i) => (
                      <ListItem key={i} disablePadding sx={{ py: 0.25 }}>
                        <ListItemText
                          primary={a.message || `${a.component || ''} ${a.event_type || ''} ${a.status || ''}`.trim() || '—'}
                          secondary={a.timestamp ? timeAgo(a.timestamp) : null}
                          primaryTypographyProps={{ variant: 'caption' }}
                          secondaryTypographyProps={{ variant: 'caption' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
            </Box>
          ) : (
            <Typography color="text.secondary" variant="body2">
              Run summary not available. Check automation is running and logs exist.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Divider sx={{ my: 2 }} />

      {/* Pipeline status */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Pipeline & automation
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader title="Pipeline status" subheader="Traces and processing" avatar={<ScheduleIcon />} />
          <CardContent>
            {loading && !pipeline?.data ? (
              <Skeleton variant="rectangular" height={80} />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip size="small" color={pipelineStatusColor} label={pipelineStatus ?? '—'} />
                  {typeof pipelineData?.success_rate === 'number' && (
                    <Typography variant="body2" color="text.secondary">Success rate: {pipelineData.success_rate}%</Typography>
                  )}
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Articles processed: {pipelineData?.articles_processed ?? '—'} · Analyzed: {pipelineData?.articles_analyzed ?? '—'} · Recent (1h): {pipelineData?.recent_articles ?? '—'}
                </Typography>
                {pipelineData?.active_traces != null && Number(pipelineData.active_traces) > 0 && (
                  <Typography variant="caption" color="info.main">Active traces: {pipelineData.active_traces}</Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
        <Card sx={{ minWidth: 260 }}>
          <CardHeader title="Automation manager" subheader="Queue and workers" />
          <CardContent>
            {loading && automation?.data === undefined ? (
              <Skeleton variant="rectangular" height={60} />
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip size="small" color={automationRunning ? 'success' : 'default'} label={automationRunning ? 'Running' : 'Stopped'} />
                  <Typography variant="body2">Queue: {queueSize ?? 0}</Typography>
                  {automation?.data?.active_workers != null && (
                    <Typography variant="caption" color="text.secondary">Workers: {automation.data.active_workers}</Typography>
                  )}
                </Box>
              </Box>
            )}
          </CardContent>
        </Card>
      </Box>

      {/* Phase timeline — grouped by related processes, sequential order */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Phase timeline (grouped by stage, last run / next due)
      </Typography>
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5, overflowX: 'auto' }}>
          {loading && phases.length === 0 ? (
            <Skeleton variant="rectangular" height={120} />
          ) : phases.length === 0 ? (
            <Typography color="text.secondary" variant="body2">No phase data. Automation may not be running.</Typography>
          ) : (() => {
            const enabled = phases.filter(p => p.enabled !== false);
            const byGroup = enabled.reduce<{ label: string; phaseNum: number; rows: PhaseRow[] }[]>((acc, p) => {
              const label = p.phase_group_label ?? `Phase ${p.phase ?? 0}`;
              const phaseNum = p.phase ?? 0;
              const existing = acc.find(g => g.label === label);
              if (existing) {
                existing.rows.push(p);
                existing.phaseNum = Math.min(existing.phaseNum, phaseNum);
              } else {
                acc.push({ label, phaseNum, rows: [p] });
              }
              return acc;
            }, []);
            byGroup.sort((a, b) => a.phaseNum - b.phaseNum);
            return (
              <Box>
                {byGroup.map(({ label, rows }) => (
                  <Box key={label} sx={{ mb: 2 }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', display: 'block', mb: 0.5 }}>
                      {label}
                    </Typography>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ width: '40%' }}>Task</TableCell>
                          <TableCell>Last run</TableCell>
                          <TableCell>Interval</TableCell>
                          <TableCell>Next due</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {rows.map((p) => (
                          <TableRow key={p.name}>
                            <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                              {p.name}
                              {p.parallel_group && (
                                <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                                  (parallel)
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell>{p.last_run ? timeAgo(p.last_run) : 'never'}</TableCell>
                            <TableCell>{p.interval_seconds != null ? `${Math.round(p.interval_seconds / 60)}m` : '—'}</TableCell>
                            <TableCell>{formatDueIn(p.last_run, p.interval_seconds ?? 0)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Box>
                ))}
              </Box>
            );
          })()}
        </CardContent>
      </Card>

      {/* Decision log */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Coordinator decision log
      </Typography>
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent sx={{ py: 1.5 }}>
          {loading && decisionEntries.length === 0 ? (
            <Skeleton variant="rectangular" height={80} />
          ) : decisionEntries.length === 0 ? (
            <Typography color="text.secondary" variant="body2">No decisions yet. The coordinator logs collect_rss, process_phase, idle, etc.</Typography>
          ) : (
            <List dense disablePadding>
              {decisionEntries.slice(0, 20).map((e, i) => (
                <ListItem key={i} disablePadding sx={{ py: 0.3 }}>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography component="span" variant="body2" sx={{ fontFamily: 'monospace' }}>{e.decision ?? '—'}</Typography>
                        <Chip size="small" variant="outlined" label={e.outcome ?? '—'} />
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
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Run phase now
          </Typography>
          <Card variant="outlined">
            <CardContent sx={{ py: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                <FormControl size="small" sx={{ minWidth: 220 }}>
                  <InputLabel>Phase</InputLabel>
                  <Select
                    value={triggerPhaseName}
                    label="Phase"
                    onChange={(e) => setTriggerPhaseName(e.target.value)}
                  >
                    <MenuItem value="">Select…</MenuItem>
                    {(phases.length > 0 ? phases.map((p) => p.name) : ['rss_processing', 'article_processing', 'digest_generation', 'context_sync', 'entity_extraction', 'event_tracking', 'topic_clustering']).map((name) => (
                      <MenuItem key={name} value={name}>{name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  size="small"
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleTriggerPhase}
                  disabled={!triggerPhaseName || triggering}
                >
                  {triggering ? 'Requesting…' : 'Run now'}
                </Button>
              </Box>
              {triggerResult && (
                <Box sx={{ mt: 1.5 }}>
                  <Alert severity={triggerResult.success ? 'success' : 'error'} onClose={() => setTriggerResult(null)}>
                    {triggerResult.message}
                  </Alert>
                  {triggerResult.success && triggerResult.warning && (
                    <Alert severity="warning" sx={{ mt: 1 }} onClose={() => setTriggerResult(null)}>
                      {triggerResult.warning}
                    </Alert>
                  )}
                </Box>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                Enqueues the phase; it will appear under Current activity when it runs. Running phases out of order may process incomplete data (e.g. run rss_processing before event_tracking).
              </Typography>
            </CardContent>
          </Card>
        </Box>
      )}

      <Divider sx={{ my: 2 }} />

      {/* Collection status & quality */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Collection & quality
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
        <Card sx={{ minWidth: 280 }}>
          <CardHeader title="Collection status" subheader="Orchestrator last run" />
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
