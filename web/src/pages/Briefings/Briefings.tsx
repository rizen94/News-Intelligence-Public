import { Schedule, Article, Timeline as TimelineIcon, Refresh, AutoAwesome } from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  Divider,
  Paper,
  Tab,
  Tabs,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import apiService from '../../services/apiService';

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

interface Article {
  id?: number;
  title?: string;
  source?: string;
  source_domain?: string;
  published_date?: string;
  published_at?: string;
  category?: string;
}

interface Storyline {
  id?: number;
  title?: string;
  description?: string;
  article_count?: number;
  status?: string;
}

interface TodaysBriefing {
  date: string;
  topStories: Article[];
  storylines: Storyline[];
  summary: string;
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

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => (
  <div
    role='tabpanel'
    hidden={value !== index}
    id={`briefings-tabpanel-${index}`}
    aria-labelledby={`briefings-tab-${index}`}
    {...other}
  >
    {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
  </div>
);

const formatDate = (dateString?: string): string => {
  if (!dateString) return 'No date';
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return 'Invalid date';
  }
};

const Briefings: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  const [todaysBriefing, setTodaysBriefing] = useState<TodaysBriefing | null>(null);
  const [todaysLoading, setTodaysLoading] = useState(true);
  const [todaysError, setTodaysError] = useState<string | null>(null);

  const [generating, setGenerating] = useState(false);
  const [generatedBriefing, setGeneratedBriefing] = useState<GeneratedBriefing | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    loadTodaysBriefing();
  }, []);

  const loadTodaysBriefing = async () => {
    try {
      setTodaysLoading(true);
      setTodaysError(null);

      const [articlesResponse, storylinesResponse] = await Promise.all([
        apiService.getArticles({ limit: 10 }),
        apiService.getStorylines(),
      ]);

      const articles = articlesResponse.data?.articles?.slice(0, 5) || [];
      const storylines = storylinesResponse.data?.storylines?.slice(0, 3) || [];

      setTodaysBriefing({
        date: new Date().toLocaleDateString(),
        topStories: articles,
        storylines,
        summary: `Today's briefing covers ${articlesResponse.data?.articles?.length || 0} articles across ${storylinesResponse.data?.storylines?.length || 0} active storylines.`,
      });
    } catch (err: any) {
      setTodaysError('Failed to load today\'s briefing');
      console.error('Error loading briefing:', err);
    } finally {
      setTodaysLoading(false);
    }
  };

  const handleGenerateBriefing = async () => {
    try {
      setGenerating(true);
      setGenerateError(null);

      const response = await apiService.generateDailyBriefing();

      if (response.success !== false) {
        setGeneratedBriefing({
          id: Date.now(),
          title: `Daily Briefing - ${new Date().toLocaleDateString()}`,
          content: response.data?.content || response.content || 'Briefing generated successfully.',
          generated_at: new Date().toISOString(),
          status: 'generated',
          article_count: response.data?.article_count || response.article_count || 0,
          word_count: response.data?.content?.length || response.content?.length || 0,
        });
      } else {
        setGenerateError(response.error || 'Failed to generate briefing');
      }
    } catch (err: any) {
      setGenerateError('Failed to generate briefing: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleRefresh = () => {
    if (activeTab === 0) {
      loadTodaysBriefing();
    } else {
      setGeneratedBriefing(null);
      setGenerateError(null);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant='h4' gutterBottom>
            Briefings
          </Typography>
          <Typography variant='subtitle1' color='text.secondary'>
            Daily intelligence briefings and generation
          </Typography>
        </Box>
        <Button variant='outlined' startIcon={<Refresh />} onClick={handleRefresh}>
          Refresh
        </Button>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(_e, newValue) => setActiveTab(newValue)}>
          <Tab label="Today's Briefing" />
          <Tab label='Generate Briefing' />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        {todaysLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : todaysError ? (
          <Alert severity='error' sx={{ mb: 2 }}>{todaysError}</Alert>
        ) : (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                    <Schedule color='primary' />
                    <Typography variant='h5'>
                      {todaysBriefing?.date} - News Intelligence Briefing
                    </Typography>
                  </Box>
                  <Typography variant='body1' color='text.secondary'>
                    {todaysBriefing?.summary}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Article color='primary' />
                    <Typography variant='h6'>Top Stories</Typography>
                  </Box>
                  {todaysBriefing?.topStories?.length ? (
                    <List>
                      {todaysBriefing.topStories.map((article, index) => (
                        <React.Fragment key={article.id || index}>
                          <ListItem>
                            <ListItemText
                              primary={article.title || 'Untitled Article'}
                              secondary={
                                <Box>
                                  <Typography variant='body2' color='text.secondary'>
                                    {article.source || article.source_domain || 'Unknown Source'} &bull;{' '}
                                    {formatDate(article.published_date || article.published_at)}
                                  </Typography>
                                  {article.category && (
                                    <Chip label={article.category} size='small' sx={{ mt: 0.5 }} />
                                  )}
                                </Box>
                              }
                            />
                          </ListItem>
                          {index < todaysBriefing.topStories.length - 1 && <Divider />}
                        </React.Fragment>
                      ))}
                    </List>
                  ) : (
                    <Typography variant='body2' color='text.secondary'>
                      No stories available
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <TimelineIcon color='primary' />
                    <Typography variant='h6'>Active Storylines</Typography>
                  </Box>
                  {todaysBriefing?.storylines?.length ? (
                    <List>
                      {todaysBriefing.storylines.map((storyline, index) => (
                        <React.Fragment key={storyline.id || index}>
                          <ListItem>
                            <ListItemText
                              primary={storyline.title || 'Untitled Storyline'}
                              secondary={
                                <Box>
                                  <Typography variant='body2' color='text.secondary'>
                                    {storyline.article_count || 0} articles &bull;{' '}
                                    {storyline.status || 'Unknown status'}
                                  </Typography>
                                  {storyline.description && (
                                    <Typography variant='body2' sx={{ mt: 0.5 }}>
                                      {storyline.description.length > 100
                                        ? `${storyline.description.substring(0, 100)}...`
                                        : storyline.description}
                                    </Typography>
                                  )}
                                </Box>
                              }
                            />
                          </ListItem>
                          {index < todaysBriefing.storylines.length - 1 && <Divider />}
                        </React.Fragment>
                      ))}
                    </List>
                  ) : (
                    <Typography variant='body2' color='text.secondary'>
                      No active storylines
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        )}
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  Generate Daily Briefing
                </Typography>
                <Typography variant='body2' color='text.secondary' sx={{ mb: 3 }}>
                  Generate an AI-powered briefing summarizing today&apos;s top news and developments.
                </Typography>
                <Button
                  variant='contained'
                  startIcon={generating ? <CircularProgress size={20} color='inherit' /> : <AutoAwesome />}
                  onClick={handleGenerateBriefing}
                  disabled={generating}
                  fullWidth
                  size='large'
                >
                  {generating ? 'Generating...' : 'Generate Briefing'}
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            {generateError && (
              <Alert severity='error' sx={{ mb: 2 }}>{generateError}</Alert>
            )}
            {generatedBriefing && (
              <Paper sx={{ p: 3 }}>
                <Typography variant='h6' gutterBottom>
                  {generatedBriefing.title}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip label={generatedBriefing.status} color='success' size='small' />
                  <Chip label={`${generatedBriefing.article_count} articles`} size='small' variant='outlined' />
                  <Chip label={`${generatedBriefing.word_count} chars`} size='small' variant='outlined' />
                </Box>
                <Divider sx={{ mb: 2 }} />
                <Typography variant='body1' sx={{ whiteSpace: 'pre-wrap' }}>
                  {generatedBriefing.content}
                </Typography>
                <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mt: 2 }}>
                  Generated: {formatDate(generatedBriefing.generated_at)}
                </Typography>
              </Paper>
            )}
            {!generatedBriefing && !generateError && (
              <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
                <Typography variant='body2' color='text.secondary'>
                  Click &quot;Generate Briefing&quot; to create a new daily briefing
                </Typography>
              </Paper>
            )}
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};

export default Briefings;
