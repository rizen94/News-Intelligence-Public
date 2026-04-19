/**
 * Intelligence Dashboard — threads strip + What's New + Active Investigations.
 * Collection/pipeline counts live on Monitor (ops / finance-adjacent).
 * Product notes: docs/archive/planning_incubator/WEB_PRODUCT_DISPLAY_PLAN.md
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
  Skeleton,
  Divider,
} from '@mui/material';
import {
  contextCentricApi,
  type Context,
  type TrackedEvent,
} from '../../services/api/contextCentric';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import ThreadCard from '../../components/Thread/ThreadCard';

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
  const [contextsLoading, setContextsLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setContextsLoading(true);
      setEventsLoading(true);

      const ctxRes = contextCentricApi.getContexts({ domain_key: domain, limit: 10, brief: true }).catch(() => ({ items: [] as Context[] }));
      const evRes = contextCentricApi.getTrackedEvents({ domain_key: domain, limit: 8 }).catch(() => ({ items: [] as TrackedEvent[] }));
      const [ctxData, evData] = await Promise.all([ctxRes, evRes]);
      if (cancelled) return;
      const rawCtx = ctxData?.items ?? [];
      const rawEv = evData?.items ?? [];
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

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 600 }}>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
            Threads
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Latest contexts and tracked events (same thread model as Briefing and
            Investigate).
          </Typography>
          <Grid container spacing={2}>
            {contextsLoading
              ? [1, 2, 3].map(i => (
                  <Grid item xs={12} md={4} key={`sk-c-${i}`}>
                    <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 1 }} />
                  </Grid>
                ))
              : contexts.slice(0, 3).map(c => {
                  const snippet = c.content ? cleanSnippet(c.content, 100) : null;
                  const ago = c.created_at ? timeAgo(new Date(c.created_at)) : null;
                  return (
                    <Grid item xs={12} md={4} key={c.id}>
                      <ThreadCard
                        kind="context"
                        title={c.title || '(No title)'}
                        subtitle={ago ? `Added ${ago}` : undefined}
                        why={snippet ?? undefined}
                        href={`/${domain}/discover/contexts/${c.id}?from=dashboard`}
                        ctaLabel="Open context"
                      />
                    </Grid>
                  );
                })}
            {!contextsLoading &&
              !eventsLoading &&
              contexts.length === 0 &&
              events.length === 0 && (
                <Grid item xs={12}>
                  <Typography variant="body2" color="text.secondary">
                    No threads yet — open Briefing or add tracked events under
                    Investigate.
                  </Typography>
                </Grid>
              )}
            {eventsLoading
              ? [1, 2].map(i => (
                  <Grid item xs={12} md={4} key={`sk-e-${i}`}>
                    <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 1 }} />
                  </Grid>
                ))
              : events.slice(0, 3).map(e => (
                  <Grid item xs={12} md={4} key={e.id}>
                    <ThreadCard
                      kind="event"
                      title={e.event_name || `Event #${e.id}`}
                      subtitle={
                        e.start_date
                          ? `Since ${new Date(e.start_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
                          : e.event_type ?? undefined
                      }
                      why={e.geographic_scope ?? undefined}
                      href={`/${domain}/investigate/events/${e.id}?from=dashboard`}
                      chip={e.event_type ?? undefined}
                      ctaLabel="Open event"
                    />
                  </Grid>
                ))}
          </Grid>
        </Grid>
        {/* What's New */}
        <Grid item xs={12} md={6}>
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

        {/* Active Investigations */}
        <Grid item xs={12} md={6}>
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
      </Grid>
    </Box>
  );
}
