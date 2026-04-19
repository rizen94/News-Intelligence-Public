/**
 * Domain briefing — Report API (5W1H + key_actors), optional feed + on-demand digest.
 * v9: four editorial lenses (Domain pulse, Collisions, Power ledger, Quiet-but-watch).
 * See docs/EDITORIAL_DISPLAY_STRATEGY.md.
 */
import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardActionArea,
  CardContent,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Collapse,
  Paper,
  Divider,
  Skeleton,
} from '@mui/material';
import Refresh from '@mui/icons-material/Refresh';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import OpenInNew from '@mui/icons-material/OpenInNew';
import AutoAwesome from '@mui/icons-material/AutoAwesome';
import SearchIcon from '@mui/icons-material/Search';
import apiService from '../../services/apiService';
import {
  contextCentricApi,
  type PatternDiscovery,
} from '../../services/api/contextCentric';
import { useDomain } from '../../contexts/DomainContext';
import EntityCard from '../../components/EntityCard/EntityCard';
import { sanitizeLeadText } from '../../utils/sanitizeDisplayText';
import type {
  ReportPayload,
  EditorialDocument,
  ReportStoryline,
} from '../../types';

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

function getTimeOfDayLabel(slot: ReportPayload['time_of_day']): string {
  switch (slot) {
    case 'morning':
      return 'While you were sleeping · Day ahead';
    case 'midday':
      return 'Midday update · Quick scan';
    case 'evening':
      return 'This evening · What it means';
    case 'weekend':
      return 'Week in review · Deeper reads';
    default:
      return 'Your briefing';
  }
}

function is5W1H(ed: EditorialDocument | null | undefined): boolean {
  return Boolean(
    ed &&
      (ed.who != null || ed.what != null || ed.when != null || ed.where != null)
  );
}

interface LeadCardProps {
  item: ReportStoryline;
  domain: string;
  isLead: boolean;
  onNavigate: (id: number) => void;
}

function LeadStorylineCard({
  item,
  domain,
  isLead,
  onNavigate,
}: LeadCardProps) {
  const [whyHowOpen, setWhyHowOpen] = useState(false);
  const ed = item.editorial_document;
  const has5W1H = is5W1H(ed ?? undefined);

  const cleanedLede = sanitizeLeadText((ed?.lede ?? '').trim());
  const lede = cleanedLede || item.title;
  const support =
    !has5W1H && item.title ? (item.title !== lede ? item.title : '') : '';

  return (
    <Paper
      elevation={0}
      sx={{
        borderLeft: '4px solid',
        borderColor: item.phase === 'Breaking' ? 'error.main' : 'primary.main',
        p: 2.5,
        bgcolor: item.phase === 'Breaking' ? 'error.50' : 'grey.50',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
          mb: 1,
        }}
      >
        <Chip
          label={item.phase}
          size='small'
          color={item.phase === 'Breaking' ? 'error' : 'default'}
          variant={item.phase === 'Breaking' ? 'filled' : 'outlined'}
        />
        <Typography variant='caption' color='text.secondary'>
          {timeAgo(new Date(item.updated_at))}
        </Typography>
        {item.source_count > 0 && (
          <Typography variant='caption' color='text.secondary'>
            · {item.source_count} source{item.source_count !== 1 ? 's' : ''}
          </Typography>
        )}
      </Box>
      <CardActionArea
        onClick={() => onNavigate(item.id)}
        sx={{ alignItems: 'flex-start', py: 0.5 }}
      >
        <Typography
          variant={isLead ? 'h4' : 'h6'}
          component='h2'
          sx={{ fontWeight: 700, lineHeight: 1.25, mb: 1 }}
        >
          {lede}
        </Typography>
        {support && (
          <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
            {support.slice(0, 220)}
            {support.length > 220 ? '…' : ''}
          </Typography>
        )}
        {has5W1H && ed && (
          <Box sx={{ mt: 1.5, textAlign: 'left' }}>
            {ed.who && ed.who.length > 0 && (
              <Box sx={{ mb: 1 }}>
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}
                >
                  Who
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                  {item.key_actors
                    ?.slice(0, isLead ? 10 : 2)
                    .map((actor, i) => (
                      <EntityCard
                        key={actor.canonical_entity_id ?? i}
                        entity={{
                          canonical_entity_id: actor.canonical_entity_id,
                          name: actor.name,
                          type: actor.type,
                          description: actor.description,
                          profile_id: actor.profile_id ?? null,
                          has_dossier: false,
                          role_in_story: actor.role_in_story,
                        }}
                        mode='compact'
                        domain={domain}
                      />
                    ))}
                </Box>
              </Box>
            )}
            {ed.what && ed.what.length > 0 && (
              <Box sx={{ mb: 1, pl: 2 }} component='ul'>
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}
                >
                  What
                </Typography>
                {ed.what.slice(0, 4).map((w, i) => (
                  <Typography
                    key={i}
                    variant='body2'
                    component='li'
                    sx={{ mb: 0.25 }}
                  >
                    {w}
                  </Typography>
                ))}
              </Box>
            )}
            {ed.when && ed.when.length > 0 && (
              <Box sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ fontWeight: 600, width: '100%' }}
                >
                  When
                </Typography>
                {ed.when.slice(0, 5).map((t, i) => (
                  <Chip key={i} size='small' label={t} variant='outlined' />
                ))}
              </Box>
            )}
            {ed.where && ed.where.length > 0 && (
              <Box sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ fontWeight: 600, width: '100%' }}
                >
                  Where
                </Typography>
                {ed.where.slice(0, 4).map((w, i) => (
                  <Chip key={i} size='small' label={w} variant='outlined' />
                ))}
              </Box>
            )}
            {(ed.why || ed.how) && (
              <Box sx={{ mt: 1 }}>
                <ListItemButton
                  dense
                  onClick={() => setWhyHowOpen(!whyHowOpen)}
                  sx={{ px: 0 }}
                >
                  <ListItemText primary='Why / How' secondary='Analysis' />
                  {whyHowOpen ? <ExpandLess /> : <ExpandMore />}
                </ListItemButton>
                <Collapse in={whyHowOpen}>
                  <Typography
                    variant='body2'
                    color='text.secondary'
                    sx={{ pl: 0, pr: 2, pb: 1 }}
                  >
                    {[ed.why, ed.how].filter(Boolean).join(' ')}
                  </Typography>
                </Collapse>
              </Box>
            )}
            {ed.outlook && (
              <Paper
                variant='outlined'
                sx={{ p: 1, mt: 1, bgcolor: 'action.hover' }}
              >
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ fontWeight: 600 }}
                >
                  What to watch
                </Typography>
                <Typography variant='body2'>{ed.outlook}</Typography>
              </Paper>
            )}
          </Box>
        )}
        <Typography
          variant='caption'
          color='primary'
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1 }}
        >
          Read storyline <OpenInNew fontSize='small' />
        </Typography>
      </CardActionArea>
    </Paper>
  );
}

interface FeedArticle {
  id?: number;
  title?: string;
  source?: string;
}
interface FeedStoryline {
  id?: number;
  title?: string;
}
interface GeneratedDigest {
  content: string;
  generated_at: string;
  article_count: number;
}

function patternDiscoverySummary(p: PatternDiscovery): string {
  const t = p.pattern_type?.replace(/_/g, ' ') ?? 'Pattern';
  if (p.data != null && typeof p.data === 'object') {
    const d = p.data as Record<string, unknown>;
    const bit = Object.keys(d)
      .slice(0, 2)
      .map(k => `${k}: ${String(d[k]).slice(0, 48)}`)
      .join(' · ');
    return bit ? `${t} — ${bit}` : t;
  }
  return t;
}

function uniqueLeadActors(leads: ReportStoryline[]) {
  const map = new Map<
    number,
    NonNullable<ReportStoryline['key_actors']>[0]
  >();
  for (const s of leads) {
    for (const a of s.key_actors ?? []) {
      if (!map.has(a.canonical_entity_id)) map.set(a.canonical_entity_id, a);
    }
  }
  return [...map.values()];
}

export default function ReportPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [payload, setPayload] = useState<ReportPayload | null>(null);
  const [reportLoading, setReportLoading] = useState(true);
  const [reportError, setReportError] = useState<string | null>(null);
  const [feedArticles, setFeedArticles] = useState<FeedArticle[]>([]);
  const [feedStorylines, setFeedStorylines] = useState<FeedStoryline[]>([]);
  const [feedLoading, setFeedLoading] = useState(true);
  const [patterns, setPatterns] = useState<PatternDiscovery[]>([]);
  const [patternsLoading, setPatternsLoading] = useState(true);
  const [patternsError, setPatternsError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generatedDigest, setGeneratedDigest] = useState<GeneratedDigest | null>(
    null
  );
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [digestExpanded, setDigestExpanded] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setReportLoading(true);
    setReportError(null);
    setFeedLoading(true);
    setPatternsLoading(true);
    setPatternsError(null);
    setPayload(null);

    (async () => {
      const res = await apiService.getReport(domain);
      if (cancelled) return;
      if (res.success && res.data) {
        setPayload(res.data);
        setReportError(null);
      } else {
        setReportError(res.message ?? 'Failed to load report');
        setPayload(null);
      }
      setReportLoading(false);
    })();

    (async () => {
      const feedRes = await apiService
        .getBriefingFeed(domain, 6, 4)
        .catch(() => null);
      if (cancelled) return;
      const fd = feedRes as {
        success?: boolean;
        data?: { articles?: FeedArticle[]; storylines?: FeedStoryline[] };
      } | null;
      if (fd?.success && fd.data) {
        setFeedArticles(Array.isArray(fd.data.articles) ? fd.data.articles : []);
        setFeedStorylines(
          Array.isArray(fd.data.storylines) ? fd.data.storylines : []
        );
      } else {
        setFeedArticles([]);
        setFeedStorylines([]);
      }
      setFeedLoading(false);
    })();

    (async () => {
      try {
        const data = await contextCentricApi.getPatternDiscoveries({
          domain_key: domain,
          limit: 8,
        });
        if (cancelled) return;
        setPatterns(data?.items ?? []);
        setPatternsError(null);
      } catch {
        if (cancelled) return;
        setPatterns([]);
        setPatternsError('Could not load pattern discoveries.');
      } finally {
        if (!cancelled) setPatternsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [domain]);

  const load = async () => {
    setReportLoading(true);
    setReportError(null);
    setFeedLoading(true);
    setPatternsLoading(true);
    setPatternsError(null);

    const res = await apiService.getReport(domain);
    if (res.success && res.data) {
      setPayload(res.data);
      setReportError(null);
    } else {
      setReportError(res.message ?? 'Failed to load report');
      setPayload(null);
    }
    setReportLoading(false);

    const feedRes = await apiService.getBriefingFeed(domain, 6, 4).catch(() => null);
    const fd = feedRes as {
      success?: boolean;
      data?: { articles?: FeedArticle[]; storylines?: FeedStoryline[] };
    } | null;
    if (fd?.success && fd.data) {
      setFeedArticles(Array.isArray(fd.data.articles) ? fd.data.articles : []);
      setFeedStorylines(
        Array.isArray(fd.data.storylines) ? fd.data.storylines : []
      );
    } else {
      setFeedArticles([]);
      setFeedStorylines([]);
    }
    setFeedLoading(false);

    try {
      const data = await contextCentricApi.getPatternDiscoveries({
        domain_key: domain,
        limit: 8,
      });
      setPatterns(data?.items ?? []);
      setPatternsError(null);
    } catch {
      setPatterns([]);
      setPatternsError('Could not load pattern discoveries.');
    } finally {
      setPatternsLoading(false);
    }
  };

  const quietPicks = useMemo(() => {
    if (!payload?.lead_storylines?.length) return [];
    return [...payload.lead_storylines]
      .sort(
        (a, b) =>
          new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime()
      )
      .slice(0, 3);
  }, [payload]);

  const powerActors = useMemo(
    () => (payload ? uniqueLeadActors(payload.lead_storylines) : []),
    [payload]
  );

  const handleGenerateDigest = async () => {
    setGenerating(true);
    setGenerateError(null);
    try {
      const response = await apiService.generateDailyBriefing(undefined, domain);
      const content =
        response?.data?.content ?? (response as { content?: string })?.content;
      if (response?.success !== false && content) {
        setGeneratedDigest({
          content: String(content),
          generated_at: new Date().toISOString(),
          article_count:
            response?.data?.article_count ??
            (response as { article_count?: number })?.article_count ??
            0,
        });
      } else {
        setGenerateError(
          (response as { error?: string })?.error ??
            (response as { message?: string })?.message ??
            'Failed to generate digest'
        );
      }
    } catch (e: unknown) {
      setGenerateError((e as Error)?.message ?? 'Failed to generate digest');
    } finally {
      setGenerating(false);
    }
  };

  const timeOfDay = payload?.time_of_day ?? 'morning';

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 2,
          mb: 2,
        }}
      >
        <Box>
          <Typography variant='h4' sx={{ fontWeight: 700 }}>
            Briefing
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            {getTimeOfDayLabel(timeOfDay)}
          </Typography>
        </Box>
        <Button
          variant='outlined'
          size='small'
          startIcon={<Refresh />}
          onClick={load}
          disabled={reportLoading}
        >
          Refresh
        </Button>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* —— Domain pulse —— */}
        <Box>
          <Typography
            variant='overline'
            color='primary.main'
            sx={{ fontWeight: 700, letterSpacing: 0.08 }}
          >
            Domain pulse
          </Typography>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
            What moved: lead storylines, investigations, events, and coverage. Deep
            links open the storyline or event with{' '}
            <Typography component='span' variant='body2' sx={{ fontStyle: 'italic' }}>
              ?from=daily
            </Typography>{' '}
            for context.
          </Typography>
          {reportLoading && !payload ? (
            <Skeleton variant='rounded' height={220} sx={{ mb: 2 }} />
          ) : reportError && !payload ? (
            <Alert severity='error'>{reportError}</Alert>
          ) : payload ? (
            <>
              {payload.lead_storylines.length > 0 ? (
                <LeadStorylineCard
                  item={payload.lead_storylines[0]}
                  domain={payload.domain}
                  isLead
                  onNavigate={id =>
                    navigate(`/${payload.domain}/storylines/${id}?from=daily`)
                  }
                />
              ) : (
                <Paper variant='outlined' sx={{ p: 3, textAlign: 'center' }}>
                  <Typography color='text.secondary'>
                    No lead storylines for this domain yet.
                  </Typography>
                </Paper>
              )}

              {payload.lead_storylines.length > 1 && (
                <>
                  <Typography
                    variant='overline'
                    color='text.secondary'
                    sx={{ fontWeight: 600, mt: 2, display: 'block' }}
                  >
                    Also leading
                  </Typography>
                  <Grid container spacing={2}>
                    {payload.lead_storylines.slice(1, 3).map(item => (
                      <Grid item xs={12} md={6} key={item.id}>
                        <LeadStorylineCard
                          item={item}
                          domain={payload.domain}
                          isLead={false}
                          onNavigate={id =>
                            navigate(
                              `/${payload.domain}/storylines/${id}?from=daily`
                            )
                          }
                        />
                      </Grid>
                    ))}
                  </Grid>
                </>
              )}

              <Typography
                variant='overline'
                color='text.secondary'
                sx={{ fontWeight: 600, mt: 2, display: 'block' }}
              >
                Digest
              </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Paper variant='outlined' sx={{ p: 2 }}>
                <Typography
                  variant='subtitle2'
                  color='text.secondary'
                  gutterBottom
                >
                  Investigations
                </Typography>
                <List dense disablePadding>
                  {(payload.investigations ?? []).slice(0, 5).map(inv => (
                    <ListItemButton
                      key={inv.id}
                      dense
                      onClick={() =>
                        navigate(
                          `/${payload.domain}/investigate/events/${inv.id}?from=daily`
                        )
                      }
                    >
                      <ListItemText
                        primary={inv.name?.slice(0, 50) || `#${inv.id}`}
                        secondary={sanitizeLeadText(inv.briefing ?? '').slice(
                          0,
                          60
                        )}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItemButton>
                  ))}
                  {(!payload.investigations ||
                    payload.investigations.length === 0) && (
                    <ListItemText
                      primary='None'
                      primaryTypographyProps={{
                        variant: 'body2',
                        color: 'text.secondary',
                      }}
                    />
                  )}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper variant='outlined' sx={{ p: 2 }}>
                <Typography
                  variant='subtitle2'
                  color='text.secondary'
                  gutterBottom
                >
                  Recent events
                </Typography>
                <List dense disablePadding>
                  {(payload.recent_events ?? []).slice(0, 5).map(ev => (
                    <ListItemButton
                      key={ev.id}
                      dense
                      onClick={() =>
                        navigate(
                          `/${payload.domain}/investigate/events/${ev.id}?from=daily`
                        )
                      }
                    >
                      <ListItemText
                        primary={ev.title?.slice(0, 50) || `#${ev.id}`}
                        secondary={
                          ev.date ? timeAgo(new Date(ev.date)) : ev.type
                        }
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItemButton>
                  ))}
                  {(!payload.recent_events ||
                    payload.recent_events.length === 0) && (
                    <ListItemText
                      primary='None'
                      primaryTypographyProps={{
                        variant: 'body2',
                        color: 'text.secondary',
                      }}
                    />
                  )}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper variant='outlined' sx={{ p: 2 }}>
                <Typography
                  variant='subtitle2'
                  color='text.secondary'
                  gutterBottom
                >
                  Daily brief
                </Typography>
                {payload.daily_brief ? (
                  <Typography variant='body2' sx={{ whiteSpace: 'pre-wrap' }}>
                    {payload.daily_brief.slice(0, 400)}
                    {payload.daily_brief.length > 400 ? '…' : ''}
                  </Typography>
                ) : (
                  <Typography variant='body2' color='text.secondary'>
                    No brief generated yet.
                  </Typography>
                )}
              </Paper>
            </Grid>
          </Grid>

          {(payload.related_cross_domain?.events?.length ?? 0) > 0 ||
          (payload.related_cross_domain?.storylines?.length ?? 0) > 0 ? (
            <Paper variant='outlined' sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
              <Typography
                variant='overline'
                color='text.secondary'
                sx={{ fontWeight: 600, display: 'block', mb: 1 }}
              >
                Also relevant (other domains)
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Typography variant='caption' color='text.secondary'>
                    Linked events
                  </Typography>
                  <List dense disablePadding>
                    {(payload.related_cross_domain?.events ?? [])
                      .slice(0, 6)
                      .map(ev => (
                        <ListItemButton
                          key={ev.id}
                          dense
                          onClick={() =>
                            navigate(
                              `/${ev.suggested_domain ?? domain}/investigate/events/${ev.id}?from=daily`
                            )
                          }
                        >
                          <ListItemText
                            primary={ev.title?.slice(0, 56) || `#${ev.id}`}
                            secondary={`${ev.origin_domain} · ${ev.link_reason}`}
                            primaryTypographyProps={{ variant: 'body2' }}
                          />
                        </ListItemButton>
                      ))}
                    {(!payload.related_cross_domain?.events ||
                      payload.related_cross_domain.events.length === 0) && (
                      <ListItemText
                        primary='None'
                        primaryTypographyProps={{
                          variant: 'body2',
                          color: 'text.secondary',
                        }}
                      />
                    )}
                  </List>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant='caption' color='text.secondary'>
                    Storylines (shared entities)
                  </Typography>
                  <List dense disablePadding>
                    {(payload.related_cross_domain?.storylines ?? [])
                      .slice(0, 6)
                      .map(s => (
                        <ListItemButton
                          key={`${s.origin_domain}-${s.id}`}
                          dense
                          onClick={() =>
                            navigate(
                              `/${s.origin_domain}/storylines/${s.id}?from=daily`
                            )
                          }
                        >
                          <ListItemText
                            primary={s.title?.slice(0, 56) || `#${s.id}`}
                            secondary={s.origin_domain}
                            primaryTypographyProps={{ variant: 'body2' }}
                          />
                        </ListItemButton>
                      ))}
                    {(!payload.related_cross_domain?.storylines ||
                      payload.related_cross_domain.storylines.length === 0) && (
                      <ListItemText
                        primary='None'
                        primaryTypographyProps={{
                          variant: 'body2',
                          color: 'text.secondary',
                        }}
                      />
                    )}
                  </List>
                </Grid>
              </Grid>
            </Paper>
          ) : null}

              {feedLoading ? (
                <Skeleton variant='rounded' height={120} sx={{ mb: 1 }} />
              ) : (feedArticles.length > 0 || feedStorylines.length > 0) ? (
                <Paper variant='outlined' sx={{ p: 2, bgcolor: 'grey.50' }}>
                  <Typography
                    variant='overline'
                    color='text.secondary'
                    sx={{ fontWeight: 600, display: 'block', mb: 1 }}
                  >
                    More coverage
                  </Typography>
                  <Typography
                    variant='body2'
                    color='text.secondary'
                    sx={{ mb: 1.5 }}
                  >
                    From your briefing feed (re-ranked; demotes low-signal
                    topics).
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Typography variant='caption' color='text.secondary'>
                        Articles
                      </Typography>
                      <List dense disablePadding>
                        {feedArticles.slice(0, 5).map(a => (
                          <ListItemButton
                            key={a.id ?? a.title}
                            dense
                            onClick={() =>
                              a.id != null &&
                              navigate(`/${domain}/articles/${a.id}?from=daily`)
                            }
                          >
                            <ListItemText
                              primary={(a.title || '').slice(0, 72)}
                              primaryTypographyProps={{ variant: 'body2' }}
                            />
                          </ListItemButton>
                        ))}
                      </List>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Typography variant='caption' color='text.secondary'>
                        Storylines
                      </Typography>
                      <List dense disablePadding>
                        {feedStorylines.slice(0, 4).map(s => (
                          <ListItemButton
                            key={s.id ?? s.title}
                            dense
                            onClick={() =>
                              s.id != null &&
                              navigate(
                                `/${domain}/storylines/${s.id}?from=daily`
                              )
                            }
                          >
                            <ListItemText
                              primary={(s.title || '').slice(0, 72)}
                              primaryTypographyProps={{ variant: 'body2' }}
                            />
                          </ListItemButton>
                        ))}
                      </List>
                    </Grid>
                  </Grid>
                </Paper>
              ) : null}
            </>
          ) : null}
        </Box>

        {/* Collisions — patterns & co-occurrence (summary + Search) */}
        <Box>
          <Typography
            variant='overline'
            color='primary.main'
            sx={{ fontWeight: 700, letterSpacing: 0.08 }}
          >
            Collisions
          </Typography>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 1.5 }}>
            Emerging pattern discoveries for this domain. Open Search for full
            claim / entity / pattern exploration.
          </Typography>
          {patternsLoading ? (
            <Skeleton variant='rounded' height={100} />
          ) : patternsError ? (
            <Alert severity='warning'>{patternsError}</Alert>
          ) : patterns.length === 0 ? (
            <Typography variant='body2' color='text.secondary'>
              No pattern discoveries in window — try Search for full exploration.
            </Typography>
          ) : (
            <Paper variant='outlined' sx={{ p: 2, bgcolor: 'grey.50' }}>
              <List dense disablePadding>
                {patterns.slice(0, 5).map(p => (
                  <ListItem key={p.id} disablePadding sx={{ py: 0.5 }}>
                    <ListItemText
                      primary={patternDiscoverySummary(p)}
                      primaryTypographyProps={{ variant: 'body2' }}
                    />
                  </ListItem>
                ))}
              </List>
              <Button
                size='small'
                variant='outlined'
                startIcon={<SearchIcon />}
                sx={{ mt: 1 }}
                onClick={() =>
                  navigate(`/${domain}/investigate/search?from=daily`)
                }
              >
                Open in Search
              </Button>
            </Paper>
          )}
        </Box>

        {/* Power ledger — entities / dossiers */}
        <Box>
          <Typography
            variant='overline'
            color='primary.main'
            sx={{ fontWeight: 700, letterSpacing: 0.08 }}
          >
            Power ledger
          </Typography>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 1.5 }}>
            Key actors from lead storylines — open dossiers when linked.
          </Typography>
          {!payload ? (
            reportLoading ? (
              <Skeleton variant='rounded' height={80} />
            ) : (
              <Typography variant='body2' color='text.secondary'>
                Load briefing to see entities.
              </Typography>
            )
          ) : powerActors.length === 0 ? (
            <Typography variant='body2' color='text.secondary'>
              No key actors in lead cards yet.
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {powerActors.slice(0, 12).map((actor, i) => (
                <EntityCard
                  key={`${actor.canonical_entity_id}-${i}`}
                  entity={{
                    canonical_entity_id: actor.canonical_entity_id,
                    name: actor.name,
                    type: actor.type,
                    description: actor.description,
                    profile_id: actor.profile_id ?? null,
                    has_dossier: false,
                    role_in_story: actor.role_in_story,
                  }}
                  mode='compact'
                  domain={payload.domain}
                />
              ))}
            </Box>
          )}
          <Button
            size='small'
            sx={{ mt: 1 }}
            onClick={() =>
              navigate(`/${domain}/investigate/entities?from=daily`)
            }
          >
            All entities
          </Button>
        </Box>

        {/* Quiet-but-watch */}
        <Box>
          <Typography
            variant='overline'
            color='primary.main'
            sx={{ fontWeight: 700, letterSpacing: 0.08 }}
          >
            Quiet-but-watch
          </Typography>
          <Alert severity='info' sx={{ mb: 2 }}>
            Threads that move slowly can still matter. Storyline{' '}
            <code>updated_at</code> may reflect automation, not a new article —
            use Storylines sort &quot;Latest article&quot; and Watchlist alerts
            for resurfacing. Backend flags for material change may arrive in a
            later release.
          </Alert>
          {payload && quietPicks.length > 0 && (
            <Paper variant='outlined' sx={{ p: 2, mb: 2 }}>
              <Typography
                variant='subtitle2'
                color='text.secondary'
                gutterBottom
              >
                Slower-moving leads (by last update in this briefing)
              </Typography>
              <List dense disablePadding>
                {quietPicks.map(s => (
                  <ListItemButton
                    key={s.id}
                    dense
                    onClick={() =>
                      navigate(
                        `/${payload.domain}/storylines/${s.id}?from=daily`
                      )
                    }
                  >
                    <ListItemText
                      primary={s.title?.slice(0, 72) || `#${s.id}`}
                      secondary={`Updated ${timeAgo(new Date(s.updated_at))}`}
                      primaryTypographyProps={{ variant: 'body2' }}
                    />
                  </ListItemButton>
                ))}
              </List>
            </Paper>
          )}
          <Button
            variant='outlined'
            size='small'
            onClick={() =>
              navigate(`/${domain}/watchlist?from=daily`)
            }
          >
            Watchlist &amp; alerts
          </Button>
        </Box>

          <Card variant='outlined'>
            <CardContent>
              <Button
                fullWidth
                onClick={() => setDigestExpanded(!digestExpanded)}
                endIcon={digestExpanded ? <ExpandLess /> : <ExpandMore />}
                sx={{ justifyContent: 'space-between', textTransform: 'none' }}
              >
                <Typography variant='subtitle1' fontWeight={600}>
                  Extended digest (AI)
                </Typography>
              </Button>
              <Collapse in={digestExpanded}>
                <Typography variant='body2' color='text.secondary' sx={{ mt: 1, mb: 2 }}>
                  On-demand summary from recent domain activity (separate from the
                  lead cards above). Useful for a narrative scan.
                </Typography>
                {!generatedDigest ? (
                  <Button
                    variant='contained'
                    startIcon={
                      generating ? (
                        <CircularProgress size={20} color='inherit' />
                      ) : (
                        <AutoAwesome />
                      )
                    }
                    onClick={handleGenerateDigest}
                    disabled={generating}
                  >
                    {generating ? 'Generating…' : 'Generate extended digest'}
                  </Button>
                ) : (
                  <Box>
                    <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
                      {new Date(generatedDigest.generated_at).toLocaleString()} ·{' '}
                      {generatedDigest.article_count} articles (window)
                    </Typography>
                    <Typography
                      component='div'
                      sx={{ whiteSpace: 'pre-wrap' }}
                      variant='body2'
                    >
                      {sanitizeLeadText(generatedDigest.content) || generatedDigest.content}
                    </Typography>
                    <Button
                      size='small'
                      sx={{ mt: 1 }}
                      startIcon={<AutoAwesome />}
                      onClick={handleGenerateDigest}
                      disabled={generating}
                    >
                      Regenerate
                    </Button>
                  </Box>
                )}
                {generateError && (
                  <Alert
                    severity='error'
                    sx={{ mt: 2 }}
                    onClose={() => setGenerateError(null)}
                  >
                    {generateError}
                  </Alert>
                )}
              </Collapse>
            </CardContent>
          </Card>

          <Divider sx={{ my: 1 }} />
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <Button
              size='small'
              variant='outlined'
              onClick={() => navigate(`/${domain}/storylines`)}
            >
              All storylines
            </Button>
            <Button
              size='small'
              variant='outlined'
              onClick={() => navigate(`/${domain}/investigate`)}
            >
              Investigate
            </Button>
          </Box>
      </Box>
    </Box>
  );
}
