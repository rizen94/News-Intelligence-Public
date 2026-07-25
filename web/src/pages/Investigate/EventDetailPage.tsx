/**
 * Tracked event detail — chronicles, linked contexts, and investigation report (dossier).
 * Phase 1: Edit event (v6 quality-first).
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Button,
  Box,
  Skeleton,
  Chip,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import Article from '@mui/icons-material/Article';
import ReasoningPanel from '@/components/ReasoningPanel';
import Refresh from '@mui/icons-material/Refresh';
import Edit from '@mui/icons-material/Edit';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  contextCentricApi,
  type TrackedEvent,
  type EventArticleMembership,
  type TrackedEventFacet,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

const EVENT_TYPES = [
  'election',
  'legislation',
  'investigation',
  'policy',
  'economic',
  'diplomatic',
  'conflict',
  'disaster',
  'market_event',
];

interface Development {
  context_id?: number;
  storyline_id?: number;
  type?: string;
  title?: string;
  domain_key?: string;
}

interface Chronicle {
  id: number;
  update_date?: string | null;
  developments?: Development[] | null;
  analysis?: { summary?: string; context_count?: number } | null;
  predictions?: unknown[] | null;
  momentum_score?: number | null;
  created_at?: string | null;
}

const CHRONICLE_STOPWORDS = new Set([
  'about',
  'after',
  'against',
  'amid',
  'among',
  'around',
  'before',
  'between',
  'during',
  'from',
  'into',
  'large',
  'latest',
  'major',
  'model',
  'models',
  'news',
  'other',
  'over',
  'research',
  'says',
  'than',
  'that',
  'their',
  'there',
  'these',
  'this',
  'through',
  'under',
  'update',
  'updates',
  'with',
  'world',
  'would',
]);

function significantEventTokens(eventName: string): string[] {
  const raw = (eventName || '').split(/\W+/).filter(Boolean);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const w of raw) {
    const low = w.toLowerCase();
    if (low.length < 4 || CHRONICLE_STOPWORDS.has(low) || seen.has(low)) continue;
    seen.add(low);
    out.push(low);
    if (out.length >= 6) break;
  }
  return out;
}

function significantEventPhrases(eventName: string): string[] {
  const raw = (eventName || '').split(/\W+/).filter(w => w.length >= 4);
  const phrases: string[] = [];
  const seen = new Set<string>();
  for (let i = 0; i < raw.length - 1; i++) {
    const a = raw[i].toLowerCase();
    const b = raw[i + 1].toLowerCase();
    if (CHRONICLE_STOPWORDS.has(a) && CHRONICLE_STOPWORDS.has(b)) continue;
    const phrase = `${raw[i]} ${raw[i + 1]}`.toLowerCase();
    if (seen.has(phrase)) continue;
    seen.add(phrase);
    phrases.push(phrase);
    if (phrases.length >= 4) break;
  }
  return phrases;
}

/** Title-first relevance for Related contexts (mirrors API filter). */
function developmentTitleMatchesEvent(
  eventName: string,
  title?: string | null
): boolean {
  const titleL = (title || '').toLowerCase().trim();
  if (!titleL) return false;
  const phrases = significantEventPhrases(eventName);
  if (phrases.some(p => titleL.includes(p))) return true;
  const tokenHit = (token: string) =>
    new RegExp(`(?<![\\w-])${token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\w-])`).test(
      titleL
    );
  const tokens = significantEventTokens(eventName);
  if (!tokens.length) {
    const frag = (eventName || '').trim().toLowerCase().slice(0, 40);
    return Boolean(frag) && titleL.includes(frag);
  }
  const hits = tokens.filter(t => tokenHit(t)).length;
  const need = tokens.length >= 2 ? 2 : 1;
  if (hits >= need) return true;
  return tokens.some(t => t.length >= 8 && tokenHit(t));
}

/** One chronicle card per calendar day; keep newest id. */
function dedupeChroniclesByDate(chronicles: Chronicle[]): Chronicle[] {
  const byDay = new Map<string, Chronicle>();
  for (const chr of chronicles) {
    const day = (chr.update_date || chr.created_at || '').slice(0, 10) || `id-${chr.id}`;
    const prev = byDay.get(day);
    if (!prev || chr.id > prev.id) byDay.set(day, chr);
  }
  return Array.from(byDay.values()).sort((a, b) => {
    const da = a.update_date || '';
    const db = b.update_date || '';
    if (da !== db) return db.localeCompare(da);
    return b.id - a.id;
  });
}

function filterChronicleDevelopments(
  eventName: string,
  developments: Development[] | null | undefined
): Development[] {
  const raw = developments ?? [];
  const seen = new Set<string>();
  const out: Development[] = [];
  for (const d of raw) {
    if (!developmentTitleMatchesEvent(eventName, d.title)) continue;
    const key =
      d.context_id != null
        ? `c:${d.context_id}`
        : d.storyline_id != null
          ? `s:${d.domain_key || ''}:${d.storyline_id}`
          : `t:${(d.title || '').slice(0, 80)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(d);
  }
  return out;
}

/**
 * Drop empty day shells that only repeat the same summary with no on-topic contexts.
 * Keeps every card that still has related contexts; otherwise one latest summary card.
 */
function prepareChroniclesForDisplay(
  eventName: string,
  chronicles: Chronicle[] | null | undefined
): Array<Chronicle & { developments: Development[] }> {
  const enriched = dedupeChroniclesByDate(chronicles ?? []).map(chr => ({
    ...chr,
    developments: filterChronicleDevelopments(eventName, chr.developments),
  }));
  const withDevs = enriched.filter(c => c.developments.length > 0);
  if (withDevs.length > 0) {
    return withDevs.map(c => ({
      ...c,
      momentum_score:
        c.developments.length > 0
          ? Math.min(1, c.developments.length * 0.1)
          : null,
    }));
  }
  const latest = enriched[0];
  if (!latest) return [];
  return [
    {
      ...latest,
      momentum_score: null,
      analysis: latest.analysis
        ? {
            ...latest.analysis,
            // Do not surface polluted attachment lists in the empty state.
          }
        : latest.analysis,
    },
  ];
}

type EventWithChronicles = TrackedEvent & { chronicles?: Chronicle[] };

export default function EventDetailPage() {
  const { availableDomains } = useDomain();
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
  const [reportSavedNote, setReportSavedNote] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<{
    event_type: string;
    event_name: string;
    start_date: string;
    end_date: string;
    geographic_scope: string;
    domain_keys: string[];
  }>({
    event_type: '',
    event_name: '',
    start_date: '',
    end_date: '',
    geographic_scope: '',
    domain_keys: [],
  });
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [chronicleRefreshing, setChronicleRefreshing] = useState(false);
  const [reconciliation, setReconciliation] = useState<{
    chronological_events?: Array<{
      chronological_event_id: number;
      event_title?: string | null;
      event_date?: string | null;
    }>;
    storyline_refs?: Array<{ domain: string; storyline_id: number }>;
    entity_overlap_score?: number;
    confidence?: string;
  } | null>(null);
  const [linkedEvents, setLinkedEvents] = useState<TrackedEvent[]>([]);
  const [membership, setMembership] = useState<EventArticleMembership[]>([]);
  const [facets, setFacets] = useState<TrackedEventFacet[]>([]);

  const numId = id ? parseInt(id, 10) : NaN;

  const loadEvent = useCallback(() => {
    if (!id || Number.isNaN(numId)) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setReportError(null);
    contextCentricApi
      .getTrackedEvent(numId)
      .then(e => setEvent(e as EventWithChronicles))
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response
          ?.status;
        if (status === 404) {
          setEvent(null);
          return;
        }
        setEvent(null);
        setReportError((err as Error)?.message ?? 'Failed to load event');
      })
      .finally(() => setLoading(false));
    contextCentricApi
      .getEventReconciliationForTracked(numId)
      .then(r => {
        if (r && (r as { found?: boolean }).found !== false) {
          setReconciliation(r as typeof reconciliation);
        }
      })
      .catch(() => setReconciliation(null));
  }, [id, numId]);

  const loadReport = useCallback(() => {
    if (Number.isNaN(numId)) return;
    contextCentricApi
      .getTrackedEventReport(numId)
      .then(r => {
        if (r)
          setReport({
            report_md: r.report_md,
            generated_at: r.generated_at,
            context_count: r.context_count,
          });
        else setReport(null);
      })
      .catch(() => setReport(null));
  }, [numId]);

  useEffect(() => {
    loadEvent();
  }, [loadEvent]);

  useEffect(() => {
    if (!Number.isNaN(numId)) loadReport();
  }, [numId, loadReport]);

  useEffect(() => {
    if (Number.isNaN(numId)) {
      setLinkedEvents([]);
      setMembership([]);
      setFacets([]);
      return;
    }
    contextCentricApi
      .getTrackedEventLinkedEvents(numId, 12)
      .then(r => setLinkedEvents(r.items ?? []))
      .catch(() => setLinkedEvents([]));
    contextCentricApi
      .getTrackedEventMembership(numId, 80)
      .then(r => setMembership(r.items ?? []))
      .catch(() => setMembership([]));
    contextCentricApi
      .getTrackedEventFacets(numId)
      .then(r => setFacets(r.items ?? []))
      .catch(() => setFacets([]));
  }, [numId]);

  const handleEditOpen = useCallback(() => {
    if (!event) return;
    setEditForm({
      event_type: event.event_type ?? 'election',
      event_name: event.event_name ?? '',
      start_date: event.start_date ? event.start_date.slice(0, 10) : '',
      end_date: event.end_date ? event.end_date.slice(0, 10) : '',
      geographic_scope: event.geographic_scope ?? '',
      domain_keys: Array.isArray(event.domain_keys)
        ? [...event.domain_keys]
        : [],
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
    setReportSavedNote(false);
    contextCentricApi
      .generateTrackedEventReport(numId)
      .then(r => {
        if (r.success && r.report_md) {
          setReport({
            report_md: r.report_md,
            generated_at: r.generated_at ?? null,
            context_count: r.context_count ?? 0,
          });
          setReportSavedNote(true);
        } else {
          setReportError(r.error ?? 'Generation failed');
        }
      })
      .catch((e: unknown) => {
        const msg =
          (e as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ??
          (e as Error)?.message ??
          'Failed to generate report';
        setReportError(msg);
      })
      .finally(() => setReportLoading(false));
  }, [numId]);

  if (!domain) return null;

  const formatDate = (d: string | null | undefined) => {
    if (!d) return null;
    // Date-only strings must use local calendar parts — `new Date('YYYY-MM-DD')`
    // is UTC midnight and shifts back a day in US timezones.
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d);
    const dt = m
      ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
      : new Date(d);
    if (Number.isNaN(dt.getTime())) return null;
    return dt.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate(`/${domain}/investigate`)}
        >
          Back to Investigate
        </Button>
        {event && (
          <>
            <Button
              variant='outlined'
              size='small'
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
            <Button
              variant='outlined'
              size='small'
              startIcon={<Edit />}
              onClick={handleEditOpen}
            >
              Edit event
            </Button>
          </>
        )}
      </Box>

      <Dialog
        open={editOpen}
        onClose={() => !editSubmitting && setEditOpen(false)}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>Edit tracked event</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label='Event name'
              value={editForm.event_name}
              onChange={e =>
                setEditForm(f => ({ ...f, event_name: e.target.value }))
              }
              required
              fullWidth
              size='small'
            />
            <TextField
              select
              SelectProps={{ native: true }}
              label='Event type'
              value={editForm.event_type}
              onChange={e =>
                setEditForm(f => ({ ...f, event_type: e.target.value }))
              }
              fullWidth
              size='small'
            >
              {EVENT_TYPES.map(t => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </TextField>
            <TextField
              label='Start date'
              type='date'
              value={editForm.start_date}
              onChange={e =>
                setEditForm(f => ({ ...f, start_date: e.target.value }))
              }
              InputLabelProps={{ shrink: true }}
              fullWidth
              size='small'
            />
            <TextField
              label='End date'
              type='date'
              value={editForm.end_date}
              onChange={e =>
                setEditForm(f => ({ ...f, end_date: e.target.value }))
              }
              InputLabelProps={{ shrink: true }}
              fullWidth
              size='small'
            />
            <TextField
              label='Geographic scope'
              value={editForm.geographic_scope}
              onChange={e =>
                setEditForm(f => ({ ...f, geographic_scope: e.target.value }))
              }
              fullWidth
              size='small'
              placeholder='e.g. US, EU'
            />
            <Box>
              <Typography
                variant='caption'
                color='text.secondary'
                sx={{ display: 'block', mb: 0.5 }}
              >
                Domains
              </Typography>
              {availableDomains.map(d => (
                <FormControlLabel
                  key={d.key}
                  control={
                    <Checkbox
                      checked={editForm.domain_keys.includes(d.key)}
                      onChange={(_, checked) =>
                        setEditForm(f => ({
                          ...f,
                          domain_keys: checked
                            ? [...f.domain_keys, d.key]
                            : f.domain_keys.filter(k => k !== d.key),
                        }))
                      }
                    />
                  }
                  label={`${d.name} (${d.key})`}
                />
              ))}
            </Box>
            {editError && (
              <Typography color='error' variant='body2'>
                {editError}
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)} disabled={editSubmitting}>
            Cancel
          </Button>
          <Button
            variant='contained'
            onClick={handleEditSubmit}
            disabled={editSubmitting}
          >
            {editSubmitting ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {loading ? (
        <Skeleton variant='rectangular' height={200} sx={{ borderRadius: 1 }} />
      ) : !event ? (
        <Typography color='text.secondary'>Event not found.</Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Card variant='outlined'>
            <CardHeader
              title={event.event_name || `Event #${event.id}`}
              subheader={
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flexWrap: 'wrap',
                    mt: 0.5,
                  }}
                >
                  <Chip
                    label={event.event_type}
                    size='small'
                    color='primary'
                    variant='outlined'
                  />
                  {event.arc_state && (
                    <Chip
                      label={`arc: ${event.arc_state}`}
                      size='small'
                      variant='outlined'
                    />
                  )}
                  {event.geographic_scope && (
                    <Chip
                      label={event.geographic_scope}
                      size='small'
                      variant='outlined'
                    />
                  )}
                  {(event.anchors || []).slice(0, 6).map((a, i) => (
                    <Chip
                      key={`${a.value || i}-${a.kind || 'a'}`}
                      label={`${a.kind || 'anchor'}: ${a.value || '—'}`}
                      size='small'
                      color='secondary'
                      variant='outlined'
                    />
                  ))}
                </Box>
              }
            />
            <CardContent>
              <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 1 }}>
                <Typography variant='body2' color='text.secondary'>
                  Started: {formatDate(event.start_date) ?? '—'}
                </Typography>
                {event.end_date && (
                  <Typography variant='body2' color='text.secondary'>
                    Ended: {formatDate(event.end_date)}
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>

          {(facets.length > 0 || membership.length > 0) && (
            <Card variant='outlined'>
              <CardHeader
                title='Event-core evidence'
                subheader='Typed membership + domain facet storylines (quality-type megathread)'
                titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
              />
              <CardContent sx={{ pt: 0 }}>
                {facets.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant='body2' fontWeight={600} sx={{ mb: 0.75 }}>
                      Facets ({facets.length})
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                      {facets.map(f => (
                        <Chip
                          key={`${f.domain_key}-${f.storyline_id}`}
                          label={`${f.domain_key} · ${f.facet || 'facet'} #${f.storyline_id}`}
                          size='small'
                          onClick={() =>
                            navigate(
                              `/${f.domain_key}/storylines/${f.storyline_id}`,
                            )
                          }
                        />
                      ))}
                    </Box>
                  </Box>
                )}
                {membership.length > 0 ? (
                  <>
                    <Typography variant='body2' fontWeight={600} sx={{ mb: 0.75 }}>
                      Typed members ({membership.length})
                    </Typography>
                    <List dense disablePadding>
                      {membership.slice(0, 40).map(m => (
                        <ListItemButton
                          key={`${m.domain_key}-${m.article_id}-${m.membership_type}`}
                          onClick={() =>
                            navigate(
                              `/${m.domain_key}/articles/${m.article_id}`,
                            )
                          }
                        >
                          <ListItemText
                            primary={`${m.domain_key} article #${m.article_id}`}
                            secondary={`${m.membership_type}${
                              m.anchor_ref ? ` · ${m.anchor_ref}` : ''
                            }${m.facet ? ` · ${m.facet}` : ''}`}
                          />
                        </ListItemButton>
                      ))}
                    </List>
                    {membership.length > 40 && (
                      <Typography variant='caption' color='text.secondary'>
                        Showing 40 of {membership.length}
                      </Typography>
                    )}
                  </>
                ) : (
                  <Typography variant='body2' color='text.secondary'>
                    No typed membership rows yet for this event.
                  </Typography>
                )}
              </CardContent>
            </Card>
          )}

          {reconciliation && (
            <Card variant='outlined'>
              <CardHeader
                title='Event reconciliation'
                subheader='Tracked event ↔ timeline atoms ↔ storylines'
                titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
              />
              <CardContent sx={{ pt: 0 }}>
                {(reconciliation.storyline_refs?.length ?? 0) > 0 && (
                  <Typography variant='body2' sx={{ mb: 1 }}>
                    Linked storylines:{' '}
                    {reconciliation.storyline_refs?.map(r => (
                      <Chip
                        key={`${r.domain}-${r.storyline_id}`}
                        label={`${r.domain} #${r.storyline_id}`}
                        size='small'
                        sx={{ mr: 0.5 }}
                        onClick={() =>
                          navigate(`/${r.domain}/storylines/${r.storyline_id}`)
                        }
                      />
                    ))}
                  </Typography>
                )}
                {(reconciliation.chronological_events?.length ?? 0) > 0 ? (
                  <List dense disablePadding>
                    {reconciliation.chronological_events?.map(ce => (
                      <ListItemButton key={ce.chronological_event_id} disabled>
                        <ListItemText
                          primary={ce.event_title || `Atom #${ce.chronological_event_id}`}
                          secondary={ce.event_date ?? undefined}
                        />
                      </ListItemButton>
                    ))}
                  </List>
                ) : (
                  <Typography variant='body2' color='text.secondary'>
                    No related chronological timeline atoms in reconciliation window.
                  </Typography>
                )}
                {reconciliation.confidence && (
                  <Typography variant='caption' color='text.secondary' display='block' sx={{ mt: 1 }}>
                    Confidence: {reconciliation.confidence}
                    {reconciliation.entity_overlap_score != null &&
                      ` · entity overlap ${reconciliation.entity_overlap_score}`}
                  </Typography>
                )}
              </CardContent>
            </Card>
          )}

          <Card variant='outlined'>
            <CardContent>
              <ReasoningPanel trackedEventId={Number(id)} />
            </CardContent>
          </Card>

          {linkedEvents.length > 0 && (
            <Card variant='outlined'>
              <CardHeader
                title='Linked events (cross-domain)'
                titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
              />
              <CardContent sx={{ pt: 0 }}>
                <List dense disablePadding>
                  {linkedEvents.map(le => (
                    <ListItemButton
                      key={le.id}
                      onClick={() =>
                        navigate(`/${domain}/investigate/events/${le.id}`)
                      }
                    >
                      <ListItemText
                        primary={le.event_name || `Event #${le.id}`}
                        secondary={[le.event_type, (le.domain_keys || []).join(', ')]
                          .filter(Boolean)
                          .join(' · ')}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}

          {event.chronicles && event.chronicles.length > 0 && (
            <Card variant='outlined'>
              <CardHeader
                title='Chronicles'
                titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
              />
              <Divider />
              {prepareChroniclesForDisplay(
                event.event_name || '',
                event.chronicles
              ).map((chr, idx) => {
                const analysis = chr.analysis as {
                  summary?: string;
                  context_count?: number;
                } | null;
                const devs = chr.developments;
                return (
                  <React.Fragment key={chr.id}>
                    {idx > 0 && <Divider />}
                    <CardContent>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          mb: 1,
                        }}
                      >
                        <Typography variant='subtitle2'>
                          {formatDate(chr.update_date) ?? 'Update'}
                        </Typography>
                        {chr.momentum_score != null && (
                          <Chip
                            label={`Momentum: ${(
                              chr.momentum_score * 100
                            ).toFixed(0)}%`}
                            size='small'
                            color={
                              chr.momentum_score >= 0.7
                                ? 'error'
                                : chr.momentum_score >= 0.4
                                ? 'warning'
                                : 'default'
                            }
                            variant='outlined'
                          />
                        )}
                      </Box>

                      {analysis?.summary && (
                        <Box
                          sx={{
                            p: 1.5,
                            bgcolor: 'action.hover',
                            borderRadius: 1,
                            mb: 1.5,
                          }}
                        >
                          <Typography variant='body2' sx={{ lineHeight: 1.6 }}>
                            {analysis.summary}
                          </Typography>
                        </Box>
                      )}

                      {devs.length > 0 ? (
                        <Box>
                          <Typography
                            variant='caption'
                            color='text.secondary'
                            sx={{ mb: 0.5, display: 'block' }}
                          >
                            Related contexts ({devs.length})
                          </Typography>
                          <List dense disablePadding>
                            {devs.map((d, dIdx) => {
                              const devKey =
                                d.context_id ?? d.storyline_id ?? `dev-${dIdx}`;
                              const label =
                                d.title ||
                                (d.context_id != null
                                  ? `Context #${d.context_id}`
                                  : d.storyline_id != null
                                    ? `Storyline #${d.storyline_id}`
                                    : 'Related item');
                              const devDomain = d.domain_key || domain;
                              const href =
                                d.context_id != null
                                  ? `/${devDomain}/discover/contexts/${d.context_id}`
                                  : d.storyline_id != null
                                    ? `/${devDomain}/storylines/${d.storyline_id}`
                                    : null;
                              if (!href) return null;
                              return (
                                <ListItemButton
                                  key={devKey}
                                  onClick={() => navigate(href)}
                                  sx={{ py: 0.5 }}
                                >
                                  <ListItemText
                                    primary={label}
                                    primaryTypographyProps={{
                                      variant: 'body2',
                                    }}
                                  />
                                </ListItemButton>
                              );
                            })}
                          </List>
                        </Box>
                      ) : (
                        <Typography variant='body2' color='text.secondary'>
                          No on-topic related contexts for this update.
                        </Typography>
                      )}
                    </CardContent>
                  </React.Fragment>
                );
              })}
            </Card>
          )}

          <Card variant='outlined'>
            <CardHeader
              title='Investigation report'
              subheader={
                report
                  ? `Generated ${
                      report.generated_at
                        ? new Date(report.generated_at).toLocaleString()
                        : ''
                    } from ${report.context_count} contexts`
                  : 'Journalism-style dossier from chronicles and contexts'
              }
              action={
                <Button
                  size='small'
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
                <Alert
                  severity='error'
                  onClose={() => setReportError(null)}
                  sx={{ mb: 2 }}
                >
                  {reportError}
                </Alert>
              )}
              {reportSavedNote && (
                <Alert severity='success' sx={{ mb: 2 }}>
                  Saved to reading history
                </Alert>
              )}
              {reportLoading && (
                <Skeleton
                  variant='rectangular'
                  height={120}
                  sx={{ borderRadius: 1 }}
                />
              )}
              {!reportLoading && report && (
                <Box
                  sx={{
                    '& .markdown-body': {
                      '& h2': { mt: 2, mb: 1 },
                      '& ul': { pl: 2 },
                      '& p': { mb: 1 },
                    },
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {report.report_md}
                  </ReactMarkdown>
                </Box>
              )}
              {!reportLoading && !report && !reportError && (
                <Typography color='text.secondary'>
                  Generate a dossier that summarises this investigation with an
                  executive summary, timeline, key entities, sources, and what
                  we know vs what&apos;s uncertain. Regenerate after new
                  contexts are added to refresh the report.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
}
