/**
 * Tracked event detail — chronicles, linked contexts, and investigation report (dossier).
 * Phase 1: Edit event (v6 quality-first).
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, CardHeader, CardContent, Typography, Button, Box, Skeleton,
  Chip, Divider, List, ListItemButton, ListItemText, Alert,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, FormControlLabel, Checkbox,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import Article from '@mui/icons-material/Article';
import Refresh from '@mui/icons-material/Refresh';
import Edit from '@mui/icons-material/Edit';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { contextCentricApi, type TrackedEvent } from '@/services/api/contextCentric';

const DOMAIN_KEYS = ['politics', 'finance', 'science-tech'];
const EVENT_TYPES = ['election', 'legislation', 'investigation', 'policy', 'economic', 'diplomatic', 'conflict', 'disaster', 'market_event'];

interface Chronicle {
  id: number;
  update_date?: string | null;
  developments?: { context_id?: number; type?: string }[] | null;
  analysis?: { summary?: string; context_count?: number } | null;
  predictions?: unknown[] | null;
  momentum_score?: number | null;
  created_at?: string | null;
}

type EventWithChronicles = TrackedEvent & { chronicles?: Chronicle[] };

export default function EventDetailPage() {
  const { domain, id } = useParams<{ domain: string; id: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<EventWithChronicles | null>(null);
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<{
    report_md: string;
    generated_at: string | null;
    context_count: number;
  } | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<{
    event_type: string;
    event_name: string;
    start_date: string;
    end_date: string;
    geographic_scope: string;
    domain_keys: string[];
  }>({ event_type: '', event_name: '', start_date: '', end_date: '', geographic_scope: '', domain_keys: [] });
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [chronicleRefreshing, setChronicleRefreshing] = useState(false);

  const numId = id ? parseInt(id, 10) : NaN;

  const loadEvent = useCallback(() => {
    if (!id || Number.isNaN(numId)) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setReportError(null);
    contextCentricApi.getTrackedEvent(numId)
      .then((e) => setEvent(e as EventWithChronicles))
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          setEvent(null);
          return;
        }
        setEvent(null);
        setReportError((err as Error)?.message ?? 'Failed to load event');
      })
      .finally(() => setLoading(false));
  }, [id, numId]);

  const loadReport = useCallback(() => {
    if (Number.isNaN(numId)) return;
    contextCentricApi.getTrackedEventReport(numId).then((r) => {
      if (r) setReport({ report_md: r.report_md, generated_at: r.generated_at, context_count: r.context_count });
      else setReport(null);
    }).catch(() => setReport(null));
  }, [numId]);

  useEffect(() => {
    loadEvent();
  }, [loadEvent]);

  useEffect(() => {
    if (!Number.isNaN(numId)) loadReport();
  }, [numId, loadReport]);

  const handleEditOpen = useCallback(() => {
    if (!event) return;
    setEditForm({
      event_type: event.event_type ?? 'election',
      event_name: event.event_name ?? '',
      start_date: event.start_date ? event.start_date.slice(0, 10) : '',
      end_date: event.end_date ? event.end_date.slice(0, 10) : '',
      geographic_scope: event.geographic_scope ?? '',
      domain_keys: Array.isArray(event.domain_keys) ? [...event.domain_keys] : [],
    });
    setEditError(null);
    setEditOpen(true);
  }, [event]);

  const handleEditSubmit = useCallback(async () => {
    if (!event || !editForm.event_name.trim()) return;
    setEditSubmitting(true);
    setEditError(null);
    try {
      await contextCentricApi.updateTrackedEvent(event.id, {
        event_type: editForm.event_type,
        event_name: editForm.event_name.trim(),
        start_date: editForm.start_date || null,
        end_date: editForm.end_date || null,
        geographic_scope: editForm.geographic_scope.trim() || null,
        domain_keys: editForm.domain_keys,
      });
      setEditOpen(false);
      loadEvent();
    } catch (e: unknown) {
      setEditError((e as Error)?.message ?? 'Failed to update event');
    } finally {
      setEditSubmitting(false);
    }
  }, [event, editForm, loadEvent]);

  const handleGenerateReport = useCallback(() => {
    if (Number.isNaN(numId)) return;
    setReportLoading(true);
    setReportError(null);
    contextCentricApi.generateTrackedEventReport(numId)
      .then((r) => {
        if (r.success && r.report_md) {
          setReport({
            report_md: r.report_md,
            generated_at: r.generated_at ?? null,
            context_count: r.context_count ?? 0,
          });
        } else {
          setReportError(r.error ?? 'Generation failed');
        }
      })
      .catch((e: unknown) => {
        const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          ?? (e as Error)?.message
          ?? 'Failed to generate report';
        setReportError(msg);
      })
      .finally(() => setReportLoading(false));
  }, [numId]);

  if (!domain) return null;

  const formatDate = (d: string | null | undefined) =>
    d ? new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : null;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate`)}>
          Back to Investigate
        </Button>
        {event && (
          <>
            <Button
              variant="outlined"
              size="small"
              startIcon={<Refresh />}
              onClick={async () => {
                if (Number.isNaN(numId)) return;
                setChronicleRefreshing(true);
                try {
                  await contextCentricApi.triggerEventChronicleUpdate(numId);
                  loadEvent();
                } finally {
                  setChronicleRefreshing(false);
                }
              }}
              disabled={chronicleRefreshing}
            >
              {chronicleRefreshing ? 'Refreshing…' : 'Refresh chronicles'}
            </Button>
            <Button variant="outlined" size="small" startIcon={<Edit />} onClick={handleEditOpen}>
              Edit event
            </Button>
          </>
        )}
      </Box>

      <Dialog open={editOpen} onClose={() => !editSubmitting && setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit tracked event</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Event name"
              value={editForm.event_name}
              onChange={(e) => setEditForm((f) => ({ ...f, event_name: e.target.value }))}
              required
              fullWidth
              size="small"
            />
            <TextField
              select
              SelectProps={{ native: true }}
              label="Event type"
              value={editForm.event_type}
              onChange={(e) => setEditForm((f) => ({ ...f, event_type: e.target.value }))}
              fullWidth
              size="small"
            >
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </TextField>
            <TextField label="Start date" type="date" value={editForm.start_date} onChange={(e) => setEditForm((f) => ({ ...f, start_date: e.target.value }))} InputLabelProps={{ shrink: true }} fullWidth size="small" />
            <TextField label="End date" type="date" value={editForm.end_date} onChange={(e) => setEditForm((f) => ({ ...f, end_date: e.target.value }))} InputLabelProps={{ shrink: true }} fullWidth size="small" />
            <TextField label="Geographic scope" value={editForm.geographic_scope} onChange={(e) => setEditForm((f) => ({ ...f, geographic_scope: e.target.value }))} fullWidth size="small" placeholder="e.g. US, EU" />
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>Domains</Typography>
              {DOMAIN_KEYS.map((d) => (
                <FormControlLabel
                  key={d}
                  control={
                    <Checkbox
                      checked={editForm.domain_keys.includes(d)}
                      onChange={(_, checked) =>
                        setEditForm((f) => ({
                          ...f,
                          domain_keys: checked ? [...f.domain_keys, d] : f.domain_keys.filter((k) => k !== d),
                        }))
                      }
                    />
                  }
                  label={d}
                />
              ))}
            </Box>
            {editError && <Typography color="error" variant="body2">{editError}</Typography>}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)} disabled={editSubmitting}>Cancel</Button>
          <Button variant="contained" onClick={handleEditSubmit} disabled={editSubmitting}>
            {editSubmitting ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {loading ? (
        <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 1 }} />
      ) : !event ? (
        <Typography color="text.secondary">Event not found.</Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Card variant="outlined">
            <CardHeader
              title={event.event_name || `Event #${event.id}`}
              subheader={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                  <Chip label={event.event_type} size="small" color="primary" variant="outlined" />
                  {event.geographic_scope && <Chip label={event.geographic_scope} size="small" variant="outlined" />}
                </Box>
              }
            />
            <CardContent>
              <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Started: {formatDate(event.start_date) ?? '—'}
                </Typography>
                {event.end_date && (
                  <Typography variant="body2" color="text.secondary">
                    Ended: {formatDate(event.end_date)}
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>

          {event.chronicles && event.chronicles.length > 0 && (
            <Card variant="outlined">
              <CardHeader title="Chronicles" titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }} />
              <Divider />
              {event.chronicles.map((chr, idx) => {
                const analysis = chr.analysis as { summary?: string; context_count?: number } | null;
                const devs = (chr.developments ?? []) as { context_id?: number; type?: string }[];
                return (
                  <React.Fragment key={chr.id}>
                    {idx > 0 && <Divider />}
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="subtitle2">
                          {formatDate(chr.update_date) ?? 'Update'}
                        </Typography>
                        {chr.momentum_score != null && (
                          <Chip
                            label={`Momentum: ${(chr.momentum_score * 100).toFixed(0)}%`}
                            size="small"
                            color={chr.momentum_score >= 0.7 ? 'error' : chr.momentum_score >= 0.4 ? 'warning' : 'default'}
                            variant="outlined"
                          />
                        )}
                      </Box>

                      {analysis?.summary && (
                        <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1, mb: 1.5 }}>
                          <Typography variant="body2" sx={{ lineHeight: 1.6 }}>{analysis.summary}</Typography>
                        </Box>
                      )}

                      {devs.length > 0 && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                            Related contexts ({devs.length})
                          </Typography>
                          <List dense disablePadding>
                            {devs.map((d) => (
                              d.context_id != null && (
                                <ListItemButton
                                  key={d.context_id}
                                  onClick={() => navigate(`/${domain}/discover/contexts/${d.context_id}`)}
                                  sx={{ py: 0.5 }}
                                >
                                  <ListItemText
                                    primary={`Context #${d.context_id}`}
                                    primaryTypographyProps={{ variant: 'body2' }}
                                  />
                                </ListItemButton>
                              )
                            ))}
                          </List>
                        </Box>
                      )}
                    </CardContent>
                  </React.Fragment>
                );
              })}
            </Card>
          )}

          <Card variant="outlined">
            <CardHeader
              title="Investigation report"
              subheader={
                report
                  ? `Generated ${report.generated_at ? new Date(report.generated_at).toLocaleString() : ''} from ${report.context_count} contexts`
                  : 'Journalism-style dossier from chronicles and contexts'
              }
              action={
                <Button
                  size="small"
                  startIcon={report ? <Refresh /> : <Article />}
                  onClick={handleGenerateReport}
                  disabled={reportLoading}
                >
                  {report ? 'Regenerate' : 'Generate report'}
                </Button>
              }
            />
            <Divider />
            <CardContent>
              {reportError && (
                <Alert severity="error" onClose={() => setReportError(null)} sx={{ mb: 2 }}>
                  {reportError}
                </Alert>
              )}
              {reportLoading && <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 1 }} />}
              {!reportLoading && report && (
                <Box sx={{ '& .markdown-body': { '& h2': { mt: 2, mb: 1 }, '& ul': { pl: 2 }, '& p': { mb: 1 } } }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.report_md}</ReactMarkdown>
                </Box>
              )}
              {!reportLoading && !report && !reportError && (
                <Typography color="text.secondary">
                  Generate a dossier that summarises this investigation with an executive summary, timeline, key
                  entities, sources, and what we know vs what&apos;s uncertain. Regenerate after new contexts are
                  added to refresh the report.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
}
