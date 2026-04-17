/**
 * Domain briefing — Report API (5W1H + key_actors), optional feed + on-demand digest.
 * See docs/EDITORIAL_DISPLAY_STRATEGY.md. Replaces separate Briefings + Today's Report pages.
 */
import React, { useState, useEffect } from 'react';
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
  ListItemButton,
  ListItemText,
  Collapse,
  Paper,
  Divider,
} from '@mui/material';
import Refresh from '@mui/icons-material/Refresh';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import OpenInNew from '@mui/icons-material/OpenInNew';
import AutoAwesome from '@mui/icons-material/AutoAwesome';
import apiService from '../../services/apiService';
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

export default function ReportPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [payload, setPayload] = useState<ReportPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedArticles, setFeedArticles] = useState<FeedArticle[]>([]);
  const [feedStorylines, setFeedStorylines] = useState<FeedStoryline[]>([]);
  const [generating, setGenerating] = useState(false);
  const [generatedDigest, setGeneratedDigest] = useState<GeneratedDigest | null>(
    null
  );
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [digestExpanded, setDigestExpanded] = useState(true);

  useEffect(() => {
    load();
  }, [domain]);

  const load = async () => {
    setLoading(true);
    setError(null);
    const [res, feedRes] = await Promise.all([
      apiService.getReport(domain),
      apiService.getBriefingFeed(domain, 6, 4).catch(() => null),
    ]);
    if (res.success && res.data) {
      setPayload(res.data);
    } else {
      setError(res.message ?? 'Failed to load report');
      setPayload(null);
    }
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
    setLoading(false);
  };

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
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity='error'>{error}</Alert>
      ) : !payload ? null : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {payload.lead_storylines.length > 0 ? (
            <LeadStorylineCard
              item={payload.lead_storylines[0]}
              domain={payload.domain}
              isLead
              onNavigate={id => navigate(`/${payload.domain}/storylines/${id}`)}
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
                sx={{ fontWeight: 600 }}
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
                        navigate(`/${payload.domain}/storylines/${id}`)
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
            sx={{ fontWeight: 600 }}
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
                          `/${payload.domain}/investigate/events/${inv.id}`
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
                          `/${payload.domain}/investigate/events/${ev.id}`
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
                              `/${ev.suggested_domain ?? domain}/investigate/events/${ev.id}`
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
                            navigate(`/${s.origin_domain}/storylines/${s.id}`)
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

          {(feedArticles.length > 0 || feedStorylines.length > 0) && (
            <Paper variant='outlined' sx={{ p: 2, bgcolor: 'grey.50' }}>
              <Typography
                variant='overline'
                color='text.secondary'
                sx={{ fontWeight: 600, display: 'block', mb: 1 }}
              >
                More coverage
              </Typography>
              <Typography variant='body2' color='text.secondary' sx={{ mb: 1.5 }}>
                From your briefing feed (re-ranked; demotes low-signal topics).
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
                          navigate(`/${domain}/articles/${a.id}`)
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
                          navigate(`/${domain}/storylines/${s.id}`)
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
          )}

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
      )}
    </Box>
  );
}
