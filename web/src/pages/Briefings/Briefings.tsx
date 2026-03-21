/**
 * Briefings — Editorial display: Glance → Scan → Read → Dive.
 * See docs/EDITORIAL_DISPLAY_STRATEGY.md.
 */
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActionArea,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Alert,
  List,
  ListItemButton,
  ListItemText,
  ListItemSecondaryAction,
  Collapse,
  Paper,
  Tab,
  Tabs,
} from '@mui/material';
import Refresh from '@mui/icons-material/Refresh';
import AutoAwesome from '@mui/icons-material/AutoAwesome';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import OpenInNew from '@mui/icons-material/OpenInNew';
import ThumbDownOffAlt from '@mui/icons-material/ThumbDownOffAlt';
import { IconButton } from '@mui/material';
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../../services/apiService';
import {
  contextCentricApi,
  type TrackedEvent,
} from '../../services/api/contextCentric';
import { useDomain } from '../../contexts/DomainContext';
import EntityCard from '../../components/EntityCard/EntityCard';

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

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
  editorial_document?: { lede?: string; [key: string]: unknown } | null;
  top_entities?: Array<{
    name: string;
    type: string;
    description_short?: string;
  }>;
}

interface GeneratedBriefing {
  id: number;
  title: string;
  content: string;
  generated_at: string;
  status: string;
  article_count: number;
  word_count: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div
    role='tabpanel'
    hidden={value !== index}
    id={`briefings-tabpanel-${index}`}
    aria-labelledby={`briefings-tab-${index}`}
  >
    {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
  </div>
);

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

function timeOfDayLine(): string {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return 'This morning';
  if (h >= 12 && h < 17) return 'Midday update';
  if (h >= 17 && h < 22) return 'This evening';
  return 'While you were sleeping';
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

function phaseChip(
  status?: string,
  updated?: string
): 'Breaking' | 'Developing' | 'Analysis' {
  if (status?.toLowerCase().includes('break')) return 'Breaking';
  if (updated) {
    const mins = Math.floor((Date.now() - new Date(updated).getTime()) / 60000);
    if (mins < 120) return 'Developing';
  }
  return 'Analysis';
}

export default function Briefings() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(0);

  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [storylines, setStorylines] = useState<StorylineItem[]>([]);
  const [events, setEvents] = useState<TrackedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [generating, setGenerating] = useState(false);
  const [generatedBriefing, setGeneratedBriefing] =
    useState<GeneratedBriefing | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [synthesisExpanded, setSynthesisExpanded] = useState(true);

  useEffect(() => {
    load();
  }, [domain]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [feedRes, eventsRes] = await Promise.all([
        apiService
          .getBriefingFeed(domain, 10, 6)
          .catch(() => ({ success: false })),
        contextCentricApi
          .getTrackedEvents({ domain_key: domain, limit: 5 })
          .catch(() => ({ items: [] as TrackedEvent[] })),
      ]);
      if (feedRes?.success && feedRes?.data?.articles != null) {
        const rawArticles = feedRes.data.articles ?? [];
        const rawStorylines = feedRes.data.storylines ?? [];
        setArticles(Array.isArray(rawArticles) ? rawArticles.slice(0, 8) : []);
        setStorylines(
          Array.isArray(rawStorylines) ? rawStorylines.slice(0, 6) : []
        );
      } else {
        const [articlesRes, storylinesRes] = await Promise.all([
          apiService
            .getArticles({ limit: 10 })
            .catch(() => ({ data: { articles: [] } })),
          apiService
            .getStorylines()
            .catch(() => ({ data: { storylines: [] } })),
        ]);
        const rawArticles =
          (articlesRes as { data?: { articles?: ArticleItem[] } })?.data
            ?.articles ??
          (articlesRes as { articles?: ArticleItem[] })?.articles ??
          [];
        // getStorylines returns { data: StorylineListItem[], pagination, domain } (data is the array)
        const rawStorylines = Array.isArray(
          (storylinesRes as { data?: unknown })?.data
        )
          ? (storylinesRes as { data: StorylineItem[] }).data
          : (storylinesRes as { data?: { storylines?: StorylineItem[] } })?.data
              ?.storylines ??
            (storylinesRes as { storylines?: StorylineItem[] })?.storylines ??
            [];
        setArticles(Array.isArray(rawArticles) ? rawArticles.slice(0, 8) : []);
        setStorylines(
          Array.isArray(rawStorylines) ? rawStorylines.slice(0, 6) : []
        );
      }
      setEvents(eventsRes?.items ?? []);
    } catch (e) {
      setError('Failed to load briefing data');
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (
    itemType: 'article' | 'storyline' | 'briefing',
    itemId: number | undefined,
    opts: { not_interested?: boolean; rating?: number }
  ) => {
    const res = await apiService.submitContentFeedback(
      { item_type: itemType, item_id: itemId, ...opts },
      domain
    );
    if (res?.success && opts.not_interested) {
      load();
    }
  };

  const handleGenerateBriefing = async () => {
    setGenerating(true);
    setGenerateError(null);
    try {
      const response = await apiService.generateDailyBriefing(
        undefined,
        domain
      );
      if (
        response?.success !== false &&
        (response?.content || response?.data?.content)
      ) {
        setGeneratedBriefing({
          id: Date.now(),
          title: `Daily Briefing — ${new Date().toLocaleDateString()}`,
          content: response.data?.content ?? response.content ?? '',
          generated_at: new Date().toISOString(),
          status: 'generated',
          article_count:
            response.data?.article_count ?? response.article_count ?? 0,
          word_count: (response.data?.content ?? response.content ?? '').length,
        });
        setSynthesisExpanded(true);
      } else {
        setGenerateError(response?.error ?? 'Failed to generate briefing');
      }
    } catch (e: unknown) {
      setGenerateError((e as Error)?.message ?? 'Failed to generate briefing');
    } finally {
      setGenerating(false);
    }
  };

  // Lead: prefer first storyline as dominant, else first article
  const leadStoryline = storylines[0];
  const leadArticle = articles[0];
  const secondaryStorylines = storylines.slice(1, 3);
  const secondaryArticles = articles.slice(1, 3);
  const digestArticles = articles.slice(3, 8);
  const digestStorylines = storylines.slice(3, 6);

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
            Briefings
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            {timeOfDayLine()} · Scan first, then read
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

      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
      >
        <Tab label="Today's Briefing" id='briefings-tab-0' />
        <Tab label='Generate briefing' id='briefings-tab-1' />
      </Tabs>

      <TabPanel value={activeTab} index={0}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity='error'>{error}</Alert>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Glance: dominant lead */}
            {(leadStoryline || leadArticle) && (
              <Paper
                elevation={0}
                sx={{
                  borderLeft: '4px solid',
                  borderColor: 'primary.main',
                  p: 2.5,
                  bgcolor: 'grey.50',
                }}
              >
                <Typography
                  variant='overline'
                  color='text.secondary'
                  sx={{ fontWeight: 600 }}
                >
                  Lead
                </Typography>
                <CardActionArea
                  onClick={() => {
                    if (leadStoryline?.id)
                      navigate(`/${domain}/storylines/${leadStoryline.id}`);
                  }}
                  sx={{ alignItems: 'flex-start', py: 1 }}
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
                      label={phaseChip(
                        leadStoryline?.status,
                        leadStoryline?.updated_at
                      )}
                      size='small'
                      color={
                        phaseChip(
                          leadStoryline?.status,
                          leadStoryline?.updated_at
                        ) === 'Breaking'
                          ? 'error'
                          : 'default'
                      }
                      variant='outlined'
                    />
                    {leadStoryline?.updated_at && (
                      <Typography variant='caption' color='text.secondary'>
                        {timeAgo(new Date(leadStoryline.updated_at))}
                      </Typography>
                    )}
                  </Box>
                  <Typography
                    variant='h4'
                    component='h2'
                    sx={{ fontWeight: 700, lineHeight: 1.25, mb: 1 }}
                  >
                    {(leadStoryline?.editorial_document?.lede ??
                      leadStoryline?.title) ||
                      leadArticle?.title ||
                      'No lead'}
                  </Typography>
                  {(leadStoryline?.description ||
                    leadStoryline?.editorial_document?.lede ||
                    leadArticle?.source) && (
                    <Typography variant='body1' color='text.secondary'>
                      {leadStoryline?.editorial_document?.lede
                        ? leadStoryline.editorial_document.lede.slice(0, 160) +
                          (leadStoryline.editorial_document.lede.length > 160
                            ? '…'
                            : '')
                        : leadStoryline?.description?.slice(0, 160) ||
                          `${leadArticle?.source ?? ''} · ${
                            formatDate(
                              leadArticle?.published_at ??
                                leadArticle?.published_date
                            ) || ''
                          }`}
                      {(leadStoryline?.description?.length ??
                        leadStoryline?.editorial_document?.lede?.length ??
                        0) > 160
                        ? '…'
                        : ''}
                    </Typography>
                  )}
                  {leadStoryline?.top_entities &&
                    leadStoryline.top_entities.length > 0 && (
                      <Box
                        sx={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 0.75,
                          mt: 1,
                        }}
                      >
                        {leadStoryline.top_entities.slice(0, 4).map((e, i) => (
                          <EntityCard
                            key={i}
                            entity={{
                              canonical_entity_id: i,
                              name: e.name,
                              type: e.type,
                              description: e.description_short ?? null,
                            }}
                            mode='compact'
                            domain={domain}
                          />
                        ))}
                      </Box>
                    )}
                  {leadStoryline?.id && (
                    <Typography
                      variant='caption'
                      color='primary'
                      sx={{
                        mt: 1,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                      }}
                    >
                      Read storyline <OpenInNew fontSize='small' />
                    </Typography>
                  )}
                </CardActionArea>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    mt: 1,
                    flexWrap: 'wrap',
                  }}
                >
                  <Typography variant='caption' color='text.secondary'>
                    Feedback:
                  </Typography>
                  <IconButton
                    size='small'
                    title='Not interested'
                    onClick={() =>
                      handleFeedback(
                        leadStoryline ? 'storyline' : 'article',
                        (leadStoryline?.id ?? leadArticle?.id) as number,
                        { not_interested: true }
                      )
                    }
                  >
                    <ThumbDownOffAlt fontSize='small' />
                  </IconButton>
                  <Typography variant='caption' color='text.secondary'>
                    Useful?
                  </Typography>
                  {[1, 2, 3, 4, 5].map(n => (
                    <Button
                      key={n}
                      size='small'
                      variant='outlined'
                      sx={{ minWidth: 28 }}
                      onClick={() =>
                        handleFeedback(
                          leadStoryline ? 'storyline' : 'article',
                          (leadStoryline?.id ?? leadArticle?.id) as number,
                          { rating: n }
                        )
                      }
                    >
                      {n}
                    </Button>
                  ))}
                </Box>
              </Paper>
            )}

            {/* Scan: secondary leads (2 cards) */}
            <Grid container spacing={2}>
              {(secondaryStorylines[0] || secondaryArticles[0]) && (
                <Grid item xs={12} md={6}>
                  <Card variant='outlined' sx={{ height: '100%' }}>
                    <CardActionArea
                      onClick={() => {
                        const s = secondaryStorylines[0];
                        if (s?.id) navigate(`/${domain}/storylines/${s.id}`);
                      }}
                      sx={{ p: 2, display: 'block', textAlign: 'left' }}
                    >
                      <Chip
                        label={phaseChip(
                          secondaryStorylines[0]?.status,
                          secondaryStorylines[0]?.updated_at
                        )}
                        size='small'
                        sx={{ mb: 1 }}
                      />
                      <Typography variant='h6' sx={{ fontWeight: 600 }}>
                        {(secondaryStorylines[0]?.editorial_document?.lede ??
                          secondaryStorylines[0]?.title) ||
                          secondaryArticles[0]?.title}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        {secondaryStorylines[0]?.description?.slice(0, 100) ||
                          secondaryArticles[0]?.source ||
                          ''}{' '}
                        · {secondaryStorylines[0]?.article_count ?? 0} articles
                      </Typography>
                      {secondaryStorylines[0]?.top_entities &&
                        secondaryStorylines[0].top_entities.length > 0 && (
                          <Box
                            sx={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              gap: 0.5,
                              mt: 0.5,
                            }}
                          >
                            {secondaryStorylines[0].top_entities
                              .slice(0, 2)
                              .map((e, i) => (
                                <EntityCard
                                  key={i}
                                  entity={{
                                    canonical_entity_id: i,
                                    name: e.name,
                                    type: e.type,
                                    description: e.description_short ?? null,
                                  }}
                                  mode='compact'
                                  domain={domain}
                                />
                              ))}
                          </Box>
                        )}
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          mt: 1,
                        }}
                      >
                        <IconButton
                          size='small'
                          title='Not interested'
                          onClick={e => {
                            e.stopPropagation();
                            handleFeedback(
                              secondaryStorylines[0] ? 'storyline' : 'article',
                              (secondaryStorylines[0]?.id ??
                                secondaryArticles[0]?.id) as number,
                              { not_interested: true }
                            );
                          }}
                        >
                          <ThumbDownOffAlt fontSize='small' />
                        </IconButton>
                        {[1, 2, 3, 4, 5].map(n => (
                          <Button
                            key={n}
                            size='small'
                            sx={{ minWidth: 24, p: 0.25 }}
                            onClick={e => {
                              e.stopPropagation();
                              handleFeedback(
                                secondaryStorylines[0]
                                  ? 'storyline'
                                  : 'article',
                                (secondaryStorylines[0]?.id ??
                                  secondaryArticles[0]?.id) as number,
                                { rating: n }
                              );
                            }}
                          >
                            {n}
                          </Button>
                        ))}
                      </Box>
                    </CardActionArea>
                  </Card>
                </Grid>
              )}
              {(secondaryStorylines[1] || secondaryArticles[1]) && (
                <Grid item xs={12} md={6}>
                  <Card variant='outlined' sx={{ height: '100%' }}>
                    <CardActionArea
                      onClick={() => {
                        const s = secondaryStorylines[1];
                        if (s?.id) navigate(`/${domain}/storylines/${s.id}`);
                      }}
                      sx={{ p: 2, display: 'block', textAlign: 'left' }}
                    >
                      <Chip
                        label={phaseChip(
                          secondaryStorylines[1]?.status,
                          secondaryStorylines[1]?.updated_at
                        )}
                        size='small'
                        sx={{ mb: 1 }}
                      />
                      <Typography variant='h6' sx={{ fontWeight: 600 }}>
                        {(secondaryStorylines[1]?.editorial_document?.lede ??
                          secondaryStorylines[1]?.title) ||
                          secondaryArticles[1]?.title}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        {secondaryStorylines[1]?.description?.slice(0, 100) ||
                          secondaryArticles[1]?.source ||
                          ''}{' '}
                        · {secondaryStorylines[1]?.article_count ?? 0} articles
                      </Typography>
                      {secondaryStorylines[1]?.top_entities &&
                        secondaryStorylines[1].top_entities.length > 0 && (
                          <Box
                            sx={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              gap: 0.5,
                              mt: 0.5,
                            }}
                          >
                            {secondaryStorylines[1].top_entities
                              .slice(0, 2)
                              .map((e, i) => (
                                <EntityCard
                                  key={i}
                                  entity={{
                                    canonical_entity_id: i,
                                    name: e.name,
                                    type: e.type,
                                    description: e.description_short ?? null,
                                  }}
                                  mode='compact'
                                  domain={domain}
                                />
                              ))}
                          </Box>
                        )}
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          mt: 1,
                        }}
                      >
                        <IconButton
                          size='small'
                          title='Not interested'
                          onClick={e => {
                            e.stopPropagation();
                            handleFeedback(
                              secondaryStorylines[1] ? 'storyline' : 'article',
                              (secondaryStorylines[1]?.id ??
                                secondaryArticles[1]?.id) as number,
                              { not_interested: true }
                            );
                          }}
                        >
                          <ThumbDownOffAlt fontSize='small' />
                        </IconButton>
                        {[1, 2, 3, 4, 5].map(n => (
                          <Button
                            key={n}
                            size='small'
                            sx={{ minWidth: 24, p: 0.25 }}
                            onClick={e => {
                              e.stopPropagation();
                              handleFeedback(
                                secondaryStorylines[1]
                                  ? 'storyline'
                                  : 'article',
                                (secondaryStorylines[1]?.id ??
                                  secondaryArticles[1]?.id) as number,
                                { rating: n }
                              );
                            }}
                          >
                            {n}
                          </Button>
                        ))}
                      </Box>
                    </CardActionArea>
                  </Card>
                </Grid>
              )}
            </Grid>

            {/* Digest: supporting stories + storylines + events */}
            <Grid container spacing={3}>
              <Grid item xs={12} md={4}>
                <Typography
                  variant='subtitle2'
                  color='text.secondary'
                  sx={{ mb: 1, fontWeight: 600 }}
                >
                  Top stories
                </Typography>
                <List dense disablePadding>
                  {digestArticles.map((a, i) => (
                    <ListItemButton key={a.id ?? i} dense>
                      <ListItemText
                        primary={a.title || 'Untitled'}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondary={a.source_domain || a.source}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          size='small'
                          title='Not interested'
                          onClick={e => {
                            e.stopPropagation();
                            handleFeedback('article', a.id as number, {
                              not_interested: true,
                            });
                          }}
                        >
                          <ThumbDownOffAlt fontSize='small' />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItemButton>
                  ))}
                  {digestArticles.length === 0 && (
                    <Typography variant='body2' color='text.secondary'>
                      No more stories
                    </Typography>
                  )}
                </List>
              </Grid>
              <Grid item xs={12} md={4}>
                <Typography
                  variant='subtitle2'
                  color='text.secondary'
                  sx={{ mb: 1, fontWeight: 600 }}
                >
                  Active storylines
                </Typography>
                <List dense disablePadding>
                  {digestStorylines.map((s, i) => (
                    <ListItemButton
                      key={s.id ?? i}
                      dense
                      onClick={() =>
                        s.id && navigate(`/${domain}/storylines/${s.id}`)
                      }
                    >
                      <ListItemText
                        primary={
                          (s.editorial_document?.lede ?? s.title) || 'Untitled'
                        }
                        secondary={[
                          `${s.article_count ?? 0} articles`,
                          s.top_entities?.length
                            ? `Key: ${s.top_entities
                                .slice(0, 3)
                                .map(e => e.name)
                                .join(', ')}`
                            : null,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          size='small'
                          title='Not interested'
                          onClick={e => {
                            e.stopPropagation();
                            handleFeedback('storyline', s.id as number, {
                              not_interested: true,
                            });
                          }}
                        >
                          <ThumbDownOffAlt fontSize='small' />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItemButton>
                  ))}
                  {digestStorylines.length === 0 && (
                    <Typography variant='body2' color='text.secondary'>
                      No more storylines
                    </Typography>
                  )}
                </List>
              </Grid>
              <Grid item xs={12} md={4}>
                <Typography
                  variant='subtitle2'
                  color='text.secondary'
                  sx={{ mb: 1, fontWeight: 600 }}
                >
                  Tracked events
                </Typography>
                <List dense disablePadding>
                  {events.slice(0, 5).map(e => (
                    <ListItemButton
                      key={e.id}
                      dense
                      onClick={() =>
                        navigate(`/${domain}/investigate/events/${e.id}`)
                      }
                    >
                      <ListItemText
                        primary={e.event_name || `Event #${e.id}`}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondary={e.event_type}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                    </ListItemButton>
                  ))}
                  {events.length === 0 && (
                    <Typography variant='body2' color='text.secondary'>
                      No tracked events
                    </Typography>
                  )}
                </List>
              </Grid>
            </Grid>

            {/* Read: full synthesis (progressive disclosure) */}
            <Card variant='outlined'>
              <CardContent>
                <Button
                  fullWidth
                  onClick={() => setSynthesisExpanded(!synthesisExpanded)}
                  endIcon={synthesisExpanded ? <ExpandLess /> : <ExpandMore />}
                  sx={{
                    justifyContent: 'space-between',
                    textTransform: 'none',
                  }}
                >
                  <Typography variant='subtitle1' fontWeight={600}>
                    Full briefing synthesis
                  </Typography>
                </Button>
                <Collapse in={synthesisExpanded}>
                  {!generatedBriefing ? (
                    <Box sx={{ pt: 2 }}>
                      <Typography
                        variant='body2'
                        color='text.secondary'
                        sx={{ mb: 2 }}
                      >
                        Generate an AI summary of today’s developments.
                      </Typography>
                      <Button
                        variant='contained'
                        startIcon={
                          generating ? (
                            <CircularProgress size={20} color='inherit' />
                          ) : (
                            <AutoAwesome />
                          )
                        }
                        onClick={handleGenerateBriefing}
                        disabled={generating}
                      >
                        {generating ? 'Generating…' : 'Generate briefing'}
                      </Button>
                    </Box>
                  ) : (
                    <Box sx={{ pt: 2 }}>
                      <Box
                        sx={{
                          display: 'flex',
                          gap: 1,
                          mb: 2,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Chip
                          label={generatedBriefing.status}
                          size='small'
                          color='success'
                        />
                        <Chip
                          label={`${generatedBriefing.article_count} articles`}
                          size='small'
                          variant='outlined'
                        />
                        <Typography variant='caption' color='text.secondary'>
                          {formatDate(generatedBriefing.generated_at)}
                        </Typography>
                      </Box>
                      <Typography
                        component='div'
                        sx={{ whiteSpace: 'pre-wrap' }}
                        variant='body1'
                      >
                        {generatedBriefing.content}
                      </Typography>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          mt: 2,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Button
                          size='small'
                          startIcon={<AutoAwesome />}
                          onClick={handleGenerateBriefing}
                          disabled={generating}
                        >
                          Regenerate
                        </Button>
                        <Typography variant='body2' color='text.secondary'>
                          How useful was this briefing?
                        </Typography>
                        {[1, 2, 3, 4, 5].map(n => (
                          <Button
                            key={n}
                            size='small'
                            variant='outlined'
                            sx={{ minWidth: 28 }}
                            onClick={() =>
                              handleFeedback('briefing', undefined, {
                                rating: n,
                              })
                            }
                          >
                            {n}
                          </Button>
                        ))}
                      </Box>
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

            {/* Dive: quick links */}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant='outlined'
                size='small'
                onClick={() => navigate(`/${domain}/storylines`)}
              >
                All storylines
              </Button>
              <Button
                variant='outlined'
                size='small'
                onClick={() => navigate(`/${domain}/investigate`)}
              >
                Investigate
              </Button>
            </Box>
          </Box>
        )}
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Card>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Generate daily briefing
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              AI-powered summary of today’s top news and developments for this
              domain.
            </Typography>
            <Button
              variant='contained'
              startIcon={
                generating ? (
                  <CircularProgress size={20} color='inherit' />
                ) : (
                  <AutoAwesome />
                )
              }
              onClick={handleGenerateBriefing}
              disabled={generating}
            >
              {generating ? 'Generating…' : 'Generate briefing'}
            </Button>
            {generateError && (
              <Alert
                severity='error'
                sx={{ mt: 2 }}
                onClose={() => setGenerateError(null)}
              >
                {generateError}
              </Alert>
            )}
            {generatedBriefing && (
              <Paper variant='outlined' sx={{ mt: 3, p: 2 }}>
                <Typography variant='subtitle1' fontWeight={600} gutterBottom>
                  {generatedBriefing.title}
                </Typography>
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ display: 'block', mb: 1 }}
                >
                  {formatDate(generatedBriefing.generated_at)} ·{' '}
                  {generatedBriefing.article_count} articles
                </Typography>
                <Typography
                  component='div'
                  sx={{ whiteSpace: 'pre-wrap' }}
                  variant='body1'
                >
                  {generatedBriefing.content}
                </Typography>
              </Paper>
            )}
          </CardContent>
        </Card>
      </TabPanel>
    </Box>
  );
}
