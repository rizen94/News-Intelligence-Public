/**
 * Today's Report — Editorial view using docs/EDITORIAL_DISPLAY_STRATEGY.md as single source of truth.
 * Hierarchy: dominant lead → 2 secondary → digest. Time-based layout (morning/midday/evening/weekend).
 * Trust signals: freshness, source count, optional "Why this is the lead". Progressive disclosure: glance → scan → read → dive.
 */
import {
  Box,
  Typography,
  Card,
  CardActionArea,
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
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../../services/apiService';
import { contextCentricApi, type TrackedEvent } from '../../services/api/contextCentric';
import { useDomain } from '../../contexts/DomainContext';

interface ArticleItem {
  id?: number;
  title?: string;
  source?: string;
  source_domain?: string;
  published_date?: string;
  published_at?: string;
  category?: string;
}

interface StorylineItem {
  id?: number;
  title?: string;
  description?: string;
  article_count?: number;
  status?: string;
  updated_at?: string;
}

type PhaseLabel = 'Breaking' | 'Developing' | 'Analysis';

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

function getTimeOfDay(): 'morning' | 'midday' | 'evening' | 'weekend' {
  const d = new Date();
  const h = d.getHours();
  const day = d.getDay();
  if (day === 0 || day === 6) return 'weekend';
  if (h >= 5 && h < 11) return 'morning';
  if (h >= 11 && h < 17) return 'midday';
  return 'evening';
}

function getTimeOfDayLabel(): string {
  const slot = getTimeOfDay();
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
      return 'Today\'s report';
  }
}

function formatDate(dateString?: string): string {
  if (!dateString) return '';
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

function phaseFromItem(status?: string, updated?: string): PhaseLabel {
  if (status?.toLowerCase().includes('break')) return 'Breaking';
  if (updated) {
    const mins = Math.floor((Date.now() - new Date(updated).getTime()) / 60000);
    if (mins < 120) return 'Developing';
  }
  return 'Analysis';
}

export default function ReportPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();

  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [storylines, setStorylines] = useState<StorylineItem[]>([]);
  const [events, setEvents] = useState<TrackedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [whyLeadExpanded, setWhyLeadExpanded] = useState(false);

  useEffect(() => {
    load();
  }, [domain]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [articlesRes, storylinesRes, eventsRes] = await Promise.all([
        apiService.getArticles({ limit: 12 }).catch(() => ({ data: { articles: [] } })),
        apiService.getStorylines().catch(() => ({ data: { storylines: [] } })),
        contextCentricApi.getTrackedEvents({ domain_key: domain, limit: 8 }).catch(() => ({ items: [] as TrackedEvent[] })),
      ]);
      const rawArticles = (articlesRes as { data?: { articles?: ArticleItem[] } })?.data?.articles ?? (articlesRes as { articles?: ArticleItem[] })?.articles ?? [];
      const rawStorylines = (storylinesRes as { data?: { storylines?: StorylineItem[] } })?.data?.storylines ?? (storylinesRes as { storylines?: StorylineItem[] })?.storylines ?? [];
      setArticles(Array.isArray(rawArticles) ? rawArticles : []);
      setStorylines(Array.isArray(rawStorylines) ? rawStorylines : []);
      setEvents(eventsRes?.items ?? []);
    } catch {
      setError('Failed to load report data');
    } finally {
      setLoading(false);
    }
  };

  // Lead: prefer first event (investigation/tracking), then first storyline, then first article
  const leadEvent = events[0];
  const leadStoryline = storylines[0];
  const leadArticle = articles[0];
  const leadPhase: PhaseLabel = leadEvent
    ? phaseFromItem(leadEvent.status, leadEvent.updated_at ?? leadEvent.created_at)
    : leadStoryline
      ? phaseFromItem(leadStoryline.status, leadStoryline.updated_at)
      : leadArticle?.published_at
        ? (Date.now() - new Date(leadArticle.published_at).getTime() < 2 * 60 * 60 * 1000 ? 'Breaking' : 'Developing')
        : 'Analysis';

  const secondaryEvents = events.slice(1, 2);
  const secondaryStorylines = storylines.slice(leadEvent ? 0 : 1, leadEvent ? 1 : 3);
  const secondaryArticles = articles.slice(leadEvent || leadStoryline ? 0 : 1, 3);
  const digestStorylines = storylines.slice(leadEvent ? 0 : 3, 6);
  const digestArticles = articles.slice(3, 10);
  const digestEvents = events.slice(2, 6);
  const e0 = secondaryEvents[0];

  const leadTitle =
    leadEvent?.event_name ?? leadStoryline?.title ?? leadArticle?.title ?? 'No lead';
  const leadSupport =
    leadStoryline?.description?.slice(0, 200) ?? (leadArticle ? `${leadArticle.source ?? ''} · ${formatDate(leadArticle.published_at ?? leadArticle.published_date)}` : leadEvent ? 'Tracked event' : '');
  const leadUpdated =
    leadEvent?.updated_at ?? leadEvent?.created_at ?? leadStoryline?.updated_at ?? leadArticle?.published_at ?? leadArticle?.published_date;
  const leadSourceCount =
    leadStoryline?.article_count ?? (leadEvent ? 1 : 0) ?? (leadArticle ? 1 : 0);

  const isBreaking = leadPhase === 'Breaking';

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Today&apos;s Report
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {getTimeOfDayLabel()}
          </Typography>
        </Box>
        <Button variant="outlined" size="small" startIcon={<Refresh />} onClick={load} disabled={loading}>
          Refresh
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Dominant lead — massive weight, visual grammar by phase */}
          {(leadEvent || leadStoryline || leadArticle) && (
            <Paper
              elevation={0}
              sx={{
                borderLeft: '4px solid',
                borderColor: isBreaking ? 'error.main' : 'primary.main',
                p: 2.5,
                bgcolor: isBreaking ? 'error.50' : 'grey.50',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                <Chip
                  label={leadPhase}
                  size="small"
                  color={isBreaking ? 'error' : 'default'}
                  variant={isBreaking ? 'filled' : 'outlined'}
                />
                {leadUpdated && (
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                    {timeAgo(new Date(leadUpdated))}
                  </Typography>
                )}
                {leadSourceCount > 0 && (
                  <Typography variant="caption" color="text.secondary">
                    · {leadSourceCount} source{leadSourceCount !== 1 ? 's' : ''}
                  </Typography>
                )}
              </Box>
              <CardActionArea
                onClick={() => {
                  if (leadEvent?.id) navigate(`/${domain}/investigate/events/${leadEvent.id}`);
                  else if (leadStoryline?.id) navigate(`/${domain}/storylines/${leadStoryline.id}`);
                }}
                sx={{ alignItems: 'flex-start', py: 0.5 }}
              >
                <Typography variant="h4" component="h2" sx={{ fontWeight: 700, lineHeight: 1.25, mb: 1 }}>
                  {leadTitle}
                </Typography>
                {leadSupport && (
                  <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
                    {typeof leadSupport === 'string' ? leadSupport.slice(0, 220) : ''}
                    {(typeof leadSupport === 'string' && leadSupport.length > 220) ? '…' : ''}
                  </Typography>
                )}
                <Typography variant="caption" color="primary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {leadEvent ? 'View event' : 'Read storyline'} <OpenInNew fontSize="small" />
                </Typography>
              </CardActionArea>
              {/* Trust: optional "Why this is the lead" */}
              <Box sx={{ mt: 2 }}>
                <ListItemButton
                  dense
                  onClick={() => setWhyLeadExpanded(!whyLeadExpanded)}
                  sx={{ px: 0 }}
                >
                  <InfoOutlined fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText primary="Why this is the lead" secondary="Methodology" />
                  {whyLeadExpanded ? <ExpandLess /> : <ExpandMore />}
                </ListItemButton>
                <Collapse in={whyLeadExpanded}>
                  <Typography variant="body2" color="text.secondary" sx={{ pl: 4, pr: 2, pb: 1 }}>
                    Lead is chosen by recency and phase: we prefer tracked events, then active storylines, then latest articles. Breaking items get top placement; freshness and source count are shown for transparency.
                  </Typography>
                </Collapse>
              </Box>
            </Paper>
          )}

          {/* Secondary leads — exactly 2, medium weight */}
          <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 600 }}>
            Also leading
          </Typography>
          <Grid container spacing={2}>
            {(secondaryStorylines[0] || secondaryArticles[0] || secondaryEvents[0]) && (
              <Grid item xs={12} md={6}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardActionArea
                    onClick={() => {
                      const e = secondaryEvents[0];
                      const s = secondaryStorylines[0];
                      if (e?.id) navigate(`/${domain}/investigate/events/${e.id}`);
                      else if (s?.id) navigate(`/${domain}/storylines/${s.id}`);
                    }}
                    sx={{ p: 2, display: 'block', textAlign: 'left' }}
                  >
                    <Chip
                      label={e0 ? phaseFromItem(undefined, e0.updated_at ?? e0.created_at) : phaseFromItem(secondaryStorylines[0]?.status, secondaryStorylines[0]?.updated_at)}
                      size="small"
                      sx={{ mb: 1 }}
                    />
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {e0?.event_name ?? secondaryStorylines[0]?.title ?? secondaryArticles[0]?.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {secondaryStorylines[0]?.description?.slice(0, 80) ?? secondaryArticles[0]?.source ?? (e0 ? 'Tracked event' : '')}
                      {(secondaryStorylines[0]?.article_count ?? 0) > 0 && ` · ${secondaryStorylines[0]?.article_count} articles`}
                    </Typography>
                  </CardActionArea>
                </Card>
              </Grid>
            )}
            {(secondaryStorylines[1] || secondaryArticles[1]) && (
              <Grid item xs={12} md={6}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardActionArea
                    onClick={() => {
                      const s = secondaryStorylines[1];
                      if (s?.id) navigate(`/${domain}/storylines/${s.id}`);
                    }}
                    sx={{ p: 2, display: 'block', textAlign: 'left' }}
                  >
                    <Chip
                      label={phaseFromItem(secondaryStorylines[1]?.status, secondaryStorylines[1]?.updated_at)}
                      size="small"
                      sx={{ mb: 1 }}
                    />
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {secondaryStorylines[1]?.title ?? secondaryArticles[1]?.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {secondaryStorylines[1]?.description?.slice(0, 80) ?? secondaryArticles[1]?.source ?? ''}
                      {(secondaryStorylines[1]?.article_count ?? 0) > 0 && ` · ${secondaryStorylines[1]?.article_count} articles`}
                    </Typography>
                  </CardActionArea>
                </Card>
              </Grid>
            )}
          </Grid>

          {/* Digest — supporting stories, lightweight scannable */}
          <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 600 }}>
            Digest
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Top stories
                </Typography>
                <List dense disablePadding>
                  {digestArticles.slice(0, 4).map((a, i) => (
                    <ListItemButton
                      key={a.id ?? i}
                      dense
                      onClick={() => a.id && navigate(`/${domain}/storylines`)}
                    >
                      <ListItemText
                        primary={a.title?.slice(0, 60)}
                        secondary={a.source ? `${a.source} · ${timeAgo(new Date(a.published_at ?? a.published_date ?? 0))}` : undefined}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Active storylines
                </Typography>
                <List dense disablePadding>
                  {digestStorylines.slice(0, 4).map((s, i) => (
                    <ListItemButton
                      key={s.id ?? i}
                      dense
                      onClick={() => s.id && navigate(`/${domain}/storylines/${s.id}`)}
                    >
                      <ListItemText
                        primary={s.title?.slice(0, 60)}
                        secondary={s.article_count ? `${s.article_count} articles` : undefined}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Tracked events
                </Typography>
                <List dense disablePadding>
                  {digestEvents.slice(0, 4).map((e) => (
                    <ListItemButton
                      key={e.id}
                      dense
                      onClick={() => navigate(`/${domain}/investigate/events/${e.id}`)}
                    >
                      <ListItemText
                        primary={(e.event_name ?? 'Event').slice(0, 60)}
                        secondary={e.updated_at ? timeAgo(new Date(e.updated_at)) : undefined}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </Paper>
            </Grid>
          </Grid>

          <Divider sx={{ my: 1 }} />

          {/* Dive */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <Button size="small" variant="outlined" onClick={() => navigate(`/${domain}/storylines`)}>
              All storylines
            </Button>
            <Button size="small" variant="outlined" onClick={() => navigate(`/${domain}/investigate`)}>
              Investigate
            </Button>
            <Button size="small" variant="outlined" onClick={() => navigate(`/${domain}/briefings`)}>
              Briefings
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}
