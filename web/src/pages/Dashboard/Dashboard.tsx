/**
 * Intelligence Dashboard — 3 columns: What's New, Active Investigations, System Intelligence.
 * Aligned with WEB_PRODUCT_DISPLAY_PLAN.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Card,
  CardHeader,
  CardContent,
  CardActionArea,
  Typography,
  List,
  ListItemButton,
  ListItemText,
  Box,
  Chip,
  Skeleton,
  Divider,
} from '@mui/material';
import { contextCentricApi, type Context, type TrackedEvent, type ContextCentricStatus } from '../../services/api/contextCentric';
import apiService from '../../services/apiService';
import { useDomainRoute } from '../../hooks/useDomainRoute';

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return (doc.body.textContent || '').trim();
}

function cleanSnippet(raw: string, maxLen: number): string {
  const text = /<[a-z][\s\S]*?>/i.test(raw) ? stripHtml(raw) : raw;
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

export default function Dashboard() {
  // URL is source of truth so What's New matches the domain in the address bar (not stale context).
  const { domain } = useDomainRoute();
  const navigate = useNavigate();
  const [contexts, setContexts] = useState<Context[]>([]);
  const [events, setEvents] = useState<TrackedEvent[]>([]);
  const [status, setStatus] = useState<ContextCentricStatus | null>(null);
  const [orchStatus, setOrchStatus] = useState<Record<string, unknown> | null>(null);
  const [contextsLoading, setContextsLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [statusOrchLoading, setStatusOrchLoading] = useState(true);

  // Load in two waves so the right column (status/orch) can show first, then contexts and events
  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setContextsLoading(true);
      setEventsLoading(true);
      setStatusOrchLoading(true);

      // Wave 1: light endpoints so "System Intelligence" appears quickly
      const stRes = contextCentricApi.getStatus(domain).catch(() => null);
      const oRes = (async () => {
        try {
          const fn = apiService.getOrchestratorDashboard;
          if (typeof fn !== 'function') return null;
          const d = await fn.call(apiService, { decision_log_limit: 1 });
          return (d as { status?: Record<string, unknown> } | null)?.status ?? null;
        } catch {
          return null;
        }
      })();
      const [statusData, orchData] = await Promise.all([stRes, oRes]);
      if (cancelled) return;
      setStatus(statusData ?? null);
      setOrchStatus(orchData ?? null);
      setStatusOrchLoading(false);

      // Wave 2: contexts (brief) and events in parallel
      const ctxRes = contextCentricApi.getContexts({ domain_key: domain, limit: 10, brief: true }).catch(() => ({ items: [] as Context[] }));
      const evRes = contextCentricApi.getTrackedEvents({ domain_key: domain, limit: 8 }).catch(() => ({ items: [] as TrackedEvent[] }));
      const [ctxData, evData] = await Promise.all([ctxRes, evRes]);
      if (cancelled) return;
      const rawCtx = ctxData?.items ?? [];
      const rawEv = evData?.items ?? [];
      // Safety net if API omits domain_key filter or returns mixed rows
      setContexts(rawCtx.filter((c) => !c.domain_key || c.domain_key === domain));
      setEvents(
        rawEv.filter(
          (e) => !e.domain_keys?.length || e.domain_keys.includes(domain),
        ),
      );
      setContextsLoading(false);
      setEventsLoading(false);
    };

    load();
    return () => { cancelled = true; };
  }, [domain]);

  const lastTimes = (orchStatus?.last_collection_times as Record<string, string> | undefined) ?? {};

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 600 }}>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        {/* Left: What's New */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardHeader title="What's New" subheader="Latest contexts" />
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
              {contextsLoading ? (
                <Box sx={{ p: 2 }}><Skeleton variant="rectangular" height={200} /></Box>
              ) : contexts.length === 0 ? (
                <Box sx={{ p: 2 }}><Typography color="text.secondary">No contexts yet.</Typography></Box>
              ) : (
                contexts.slice(0, 8).map((c, i) => {
                  const snippet = c.content ? cleanSnippet(c.content, 120) : null;
                  const ago = c.created_at ? timeAgo(new Date(c.created_at)) : null;
                  return (
                    <React.Fragment key={c.id}>
                      <CardActionArea onClick={() => navigate(`/${domain}/discover/contexts/${c.id}`)} sx={{ px: 2, py: 1.5 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          {c.title || '(No title)'}
                        </Typography>
                        {snippet && (
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.3, lineHeight: 1.4, fontSize: '0.82rem' }}>
                            {snippet}
                          </Typography>
                        )}
                        {ago && (
                          <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: 'block' }}>{ago}</Typography>
                        )}
                      </CardActionArea>
                      {i < contexts.length - 1 && <Divider />}
                    </React.Fragment>
                  );
                })
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Middle: Active Investigations */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardHeader title="Active Investigations" subheader="Tracked events" />
            <CardContent>
              {eventsLoading ? (
                <Skeleton variant="rectangular" height={200} />
              ) : events.length === 0 ? (
                <Typography color="text.secondary">No tracked events.</Typography>
              ) : (
                <List dense>
                  {events.slice(0, 8).map((e) => (
                    <ListItemButton
                      key={e.id}
                      onClick={() => navigate(`/${domain}/investigate/events/${e.id}`)}
                    >
                      <ListItemText
                        primary={e.event_name || `Event #${e.id}`}
                        secondary={e.event_type ?? undefined}
                        primaryTypographyProps={{ noWrap: true }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              )}
              <Box sx={{ mt: 2 }}>
                <Typography
                  component="button"
                  variant="body2"
                  color="primary"
                  sx={{ cursor: 'pointer', border: 'none', background: 'none' }}
                  onClick={() => navigate(`/${domain}/investigate`)}
                >
                  View all →
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Right: System Intelligence */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardHeader title="System Intelligence" subheader="Collection & pipeline" />
            <CardContent>
              {statusOrchLoading ? (
                <Skeleton variant="rectangular" height={120} />
              ) : (
                <>
                  {status && (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                      <Chip size="small" label={`Contexts: ${status.contexts}`} />
                      <Chip size="small" label={`Entity Profiles: ${status.entity_profiles}`} />
                      <Chip size="small" label={`Events: ${status.extracted_events ?? status.tracked_events}`} />
                    </Box>
                  )}
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Collection
                  </Typography>
                  {Object.entries(lastTimes).length === 0 ? (
                    <Typography variant="caption" color="text.secondary">No collection times yet.</Typography>
                  ) : (
                    <List dense disablePadding>
                      {Object.entries(lastTimes).map(([source, time]) => (
                        <ListItemText
                          key={source}
                          primary={source}
                          secondary={time ? new Date(time).toLocaleString() : '—'}
                          primaryTypographyProps={{ variant: 'body2' }}
                          secondaryTypographyProps={{ variant: 'caption' }}
                        />
                      ))}
                    </List>
                  )}
                  <Box sx={{ mt: 2 }}>
                    <Typography
                      component="button"
                      variant="body2"
                      color="primary"
                      sx={{ cursor: 'pointer', border: 'none', background: 'none' }}
                      onClick={() => navigate(`/${domain}/monitor`)}
                    >
                      Monitor →
                    </Typography>
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
