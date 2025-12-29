import {
  ArrowBack as ArrowBackIcon,
  Timeline as TimelineIcon,
  Article,
  Edit,
  Event as EventIcon,
  Schedule as ScheduleIcon,
  ExpandMore as ExpandMoreIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Search as SearchIcon,
  Close as CloseIcon,
  AutoAwesome as AutoAwesomeIcon,
  Settings as SettingsIcon,
  MenuBook as SynthesisIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  CircularProgress,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
  ListItemSecondaryAction,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import apiService from '../../services/apiService.ts';
import StorylineManagementDialog from '../../components/StorylineManagementDialog';
import StorylineAutomationDialog from '../../components/StorylineAutomationDialog';
import ArticleSuggestionsDialog from '../../components/ArticleSuggestionsDialog';
import { useDomainNavigation } from '../../hooks/useDomainNavigation';
import { useDomainRoute } from '../../hooks/useDomainRoute';

const StorylineDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { navigateToDomain } = useDomainNavigation();
  const { domain } = useDomainRoute();
  const [storyline, setStoryline] = useState(null);
  const [articles, setArticles] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [showTimeline, setShowTimeline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showAutomationDialog, setShowAutomationDialog] = useState(false);
  const [showSuggestionsDialog, setShowSuggestionsDialog] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  // Article management state
  const [showAddArticles, setShowAddArticles] = useState(false);
  const [availableArticles, setAvailableArticles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedArticles, setSelectedArticles] = useState([]);
  const [addArticlesLoading, setAddArticlesLoading] = useState(false);

  // Synthesis state
  const [synthesis, setSynthesis] = useState(null);
  const [synthesisLoading, setSynthesisLoading] = useState(false);
  const [showFullSynthesis, setShowFullSynthesis] = useState(false);

  useEffect(() => {
    if (id) {
      loadStoryline();
    }
  }, [id]);

  const loadStoryline = async() => {
    try {
      setLoading(true);
      setError(null);

      console.log(`Loading storyline ID ${id} from domain ${domain}`);
      const storylineResponse = await apiService.getStoryline(id, domain);
      console.log('Storyline response:', storylineResponse);

      // Check for error in response
      if (storylineResponse.error) {
        const errorMsg = storylineResponse.error;
        if (errorMsg.includes('404') || errorMsg.includes('not found')) {
          setError(`Storyline #${id} not found in ${domain} domain. It may have been deleted or moved.`);
        } else if (errorMsg.includes('500') || errorMsg.includes('Internal Server')) {
          setError('Server error loading storyline. Please try again or contact support if the issue persists.');
        } else if (errorMsg.includes('connection') || errorMsg.includes('ECONNREFUSED')) {
          setError('Cannot connect to server. Please check your connection and try again.');
        } else {
          setError(`Failed to load storyline: ${errorMsg}`);
        }
        return;
      }

      // Handle both response formats:
      // 1. Wrapped format: {success: true, data: {storyline: {...}, articles: [...]}}
      // 2. Direct format: {id, title, articles: [...]}
      let storylineData = null;
      let articlesData = [];

      if (storylineResponse.success === true || storylineResponse.success === 'True') {
        // Wrapped format
        const responseData = storylineResponse.data || {};
        storylineData = responseData.storyline || responseData;
        articlesData = responseData.articles || [];
      } else if (storylineResponse.id || storylineResponse.title) {
        // Direct format (StorylineDetailResponse)
        storylineData = storylineResponse;
        articlesData = storylineResponse.articles || [];
      } else if (storylineResponse.detail) {
        // FastAPI error format: {detail: "error message"}
        const detail = storylineResponse.detail;
        if (detail.includes('not found') || detail.includes('404')) {
          setError(`Storyline #${id} not found in ${domain} domain.`);
        } else {
          setError(`Error: ${detail}`);
        }
        return;
      } else {
        console.error('Storyline response format not recognized:', storylineResponse);
        setError('Unable to parse storyline data. Please refresh the page or contact support.');
        return;
      }

      // Validate we got storyline data
      if (!storylineData || !storylineData.id) {
        setError(`Storyline #${id} data is incomplete. Please try refreshing the page.`);
        return;
      }

      console.log('Extracted storyline data:', storylineData);
      console.log('Extracted articles data:', articlesData);
      console.log('Article count from API:', storylineData?.article_count);
      console.log('Articles array length:', articlesData?.length);

      // Ensure article_count is set correctly
      if (storylineData && !storylineData.article_count && articlesData.length > 0) {
        storylineData.article_count = articlesData.length;
        console.log('Set article_count from articles array length:', articlesData.length);
      }

      setStoryline(storylineData);
      setArticles(articlesData);
    } catch (err) {
      console.error('Error loading storyline:', err);

      // Provide specific error messages based on error type
      let errorMessage = 'Failed to load storyline';

      if (err.message) {
        if (err.message.includes('Network') || err.message.includes('fetch')) {
          errorMessage = 'Network error: Cannot connect to server. Please check your connection.';
        } else if (err.message.includes('404')) {
          errorMessage = `Storyline #${id} not found in ${domain} domain.`;
        } else if (err.message.includes('500')) {
          errorMessage = 'Server error. Please try again in a moment.';
        } else {
          errorMessage = `Error: ${err.message}`;
        }
      }

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const parseTimelineFromSummary = (summary) => {
    // Extract timeline section from summary text
    if (!summary) return [];

    const timelineSection = summary.match(/\*\*Timeline of Events\*\*([\s\S]*?)(?=\*\*|$)/i);
    if (!timelineSection) return [];

    const timelineText = timelineSection[1];
    const lines = timelineText.split('\n').filter(line => line.trim());
    const events = [];

    let currentDate = null;
    lines.forEach(line => {
      // Match date headers like "* November 2, 2025:"
      const dateMatch = line.match(/\*\s+([A-Za-z]+\s+\d+,\s+\d{4}):/);
      if (dateMatch) {
        currentDate = dateMatch[1];
      } else if (currentDate && line.trim().startsWith('+')) {
        // Match event lines like "+ Event description (time)"
        const eventMatch = line.match(/\+\s+(.+?)(?:\s+\((\d{2}:\d{2})\))?/);
        if (eventMatch) {
          events.push({
            title: eventMatch[1].trim(),
            published_at: currentDate,
            event_description: eventMatch[1].trim(),
            source_domain: 'Analysis Summary',
            event_type: 'general',
          });
        }
      }
    });

    return events;
  };

  const loadTimeline = async() => {
    try {
      setTimelineLoading(true);
      const timelineResponse = await apiService.getStorylineTimeline(id, domain);

      if (timelineResponse.success) {
        // First, try structured timeline events from database
        let events = timelineResponse.data?.timeline_events || [];

        // If no structured events, try to parse from summary
        if (events.length === 0 && storyline?.analysis_summary) {
          events = parseTimelineFromSummary(storyline.analysis_summary);
        }

        const mappedEvents = events.map(event => ({
          article_id: event.id || Math.random(), // Use random ID if parsing from summary
          title: event.title || 'Untitled Event',
          source_domain: event.source || event.source_domain || 'Unknown Source',
          published_at: event.event_date || event.published_at || event.created_at,
          event_type: event.event_type || 'general',
          event_description: event.description || event.event_description,
          confidence_score: event.confidence_score,
          summary: event.description || event.summary,
        }));
        setTimeline(mappedEvents);
      }
    } catch (err) {
      console.error('Error loading timeline:', err);
    } finally {
      setTimelineLoading(false);
    }
  };

  const loadAvailableArticles = async(searchTerm = '') => {
    try {
      setAddArticlesLoading(true);
      const response = await apiService.getAvailableArticlesForStoryline(
        id,
        100,
        searchTerm || undefined,
        domain,
      );
      if (response.success) {
        setAvailableArticles(response.data.articles || []);
      } else {
        setError('Failed to load available articles');
      }
    } catch (err) {
      console.error('Error loading available articles:', err);
      setError('Failed to load available articles');
    } finally {
      setAddArticlesLoading(false);
    }
  };

  const handleRemoveArticle = async articleId => {
    try {
      const response = await apiService.removeArticleFromStoryline(
        id,
        articleId,
        domain,
      );
      if (response.success) {
        // Reload storyline to get updated article count and list
        await loadStoryline();
        setError(null);
      } else {
        setError(response.message || 'Failed to remove article');
      }
    } catch (err) {
      console.error('Error removing article:', err);
      setError('Failed to remove article');
    }
  };

  const handleAddSelectedArticles = async() => {
    if (selectedArticles.length === 0) return;

    try {
      setAddArticlesLoading(true);
      const promises = selectedArticles.map(articleId =>
        apiService.addArticleToStoryline(id, articleId, domain),
      );

      await Promise.all(promises);

      setSelectedArticles([]);
      setShowAddArticles(false);

      // Reload storyline to get updated articles
      await loadStoryline();
    } catch (err) {
      console.error('Error adding articles:', err);
      setError('Failed to add articles');
    } finally {
      setAddArticlesLoading(false);
    }
  };

  const handleAnalyzeStoryline = async() => {
    try {
      setAnalyzing(true);
      setError(null);
      const response = await apiService.analyzeStoryline(id, domain);
      if (response.success) {
        // Show success message
        setError(null);
        alert(
          'Storyline analysis started! This may take a few minutes. The summary will appear when complete.',
        );

        // Poll for updated analysis summary (check every 5 seconds for up to 2 minutes)
        let attempts = 0;
        const maxAttempts = 24; // 2 minutes max
        const pollInterval = setInterval(async() => {
          attempts++;
          try {
            const response = await apiService.getStoryline(id, domain);
            if (
              response.success &&
              response.data?.storyline?.analysis_summary
            ) {
              clearInterval(pollInterval);
              await loadStoryline(); // Reload to show the new summary
              // Also reload timeline if it's visible or will be shown
              if (showTimeline || timeline.length === 0) {
                await loadTimeline();
              }
              alert('Analysis complete! Summary and timeline are now available.');
            } else if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              alert(
                'Analysis is taking longer than expected. Please refresh the page later to see the summary.',
              );
            }
          } catch (err) {
            console.error('Error polling for analysis:', err);
            if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
            }
          }
        }, 5000);
      } else {
        setError(response.message || 'Failed to start analysis');
      }
    } catch (err) {
      console.error('Error analyzing storyline:', err);
      setError('Failed to analyze storyline');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleStorylineUpdated = () => {
    loadStoryline();
  };

  // Check for cached synthesis on load
  useEffect(() => {
    if (id) {
      checkCachedSynthesis();
    }
  }, [id, domain]);

  const checkCachedSynthesis = async() => {
    try {
      const response = await fetch(`/api/v4/${domain}/synthesis/storyline/${id}/cached`);
      if (response.ok) {
        const data = await response.json();
        if (data.has_synthesis) {
          setSynthesis(data);
        }
      }
    } catch (err) {
      console.log('No cached synthesis available');
    }
  };

  const handleGenerateSynthesis = async(regenerate = false) => {
    try {
      setSynthesisLoading(true);
      const response = await fetch(`/api/v4/${domain}/synthesis/storyline/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          depth: 'comprehensive',
          include_terms: true,
          include_timeline: true,
          format: 'json',
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSynthesis({
          has_synthesis: true,
          content: data.summary + '\n\n' + data.sections?.map(s =>
            `## ${s.title}\n\n${s.content}`,
          ).join('\n\n'),
          markdown: data.markdown,
          word_count: data.word_count,
          quality_score: data.quality_score,
          title: data.title,
          key_terms: data.key_terms_explained,
          timeline: data.timeline,
          sources: data.source_articles,
        });
        setShowFullSynthesis(true);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to generate synthesis');
      }
    } catch (err) {
      console.error('Error generating synthesis:', err);
      setError('Failed to generate synthesis');
    } finally {
      setSynthesisLoading(false);
    }
  };

  const getStatusColor = status => {
    switch (status) {
    case 'active':
      return 'success';
    case 'developing':
      return 'warning';
    case 'concluded':
      return 'default';
    default:
      return 'default';
    }
  };

  const formatDate = dateString => {
    if (!dateString) return 'No date';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch (error) {
      return 'Invalid date';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity='error' sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!storyline) {
    return (
      <Alert severity='warning' sx={{ mb: 2 }}>
        Storyline not found
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigateToDomain('/storylines')}
        >
          Back to Storylines
        </Button>
        <Button
          startIcon={<TimelineIcon />}
          onClick={() => {
            setShowTimeline(!showTimeline);
            if (!showTimeline && timeline.length === 0) {
              loadTimeline();
            }
          }}
        >
          {showTimeline ? 'Hide Timeline' : 'View Timeline'}
        </Button>
        <Button
          startIcon={<Edit />}
          variant='outlined'
          onClick={() => setShowEditDialog(true)}
        >
          Edit Storyline
        </Button>
        <Button
          variant='outlined'
          color='secondary'
          onClick={handleAnalyzeStoryline}
          disabled={analyzing || articles.length === 0}
        >
          {analyzing ? 'Analyzing...' : 'Analyze Storyline'}
        </Button>
        <Button
          startIcon={<SettingsIcon />}
          variant='outlined'
          color='secondary'
          onClick={() => setShowAutomationDialog(true)}
        >
          Automation Settings
        </Button>
        <Button
          startIcon={<AutoAwesomeIcon />}
          variant='contained'
          color='primary'
          onClick={() => setShowSuggestionsDialog(true)}
        >
          Find Articles
        </Button>
        <Button
          startIcon={synthesisLoading ? <CircularProgress size={20} /> : <SynthesisIcon />}
          variant='contained'
          color='secondary'
          onClick={() => synthesis?.has_synthesis ? setShowFullSynthesis(true) : handleGenerateSynthesis()}
          disabled={synthesisLoading || articles.length === 0}
        >
          {synthesisLoading ? 'Generating...' : synthesis?.has_synthesis ? 'View Full Article' : 'Generate Article'}
        </Button>
        {synthesis?.has_synthesis && (
          <Tooltip title="Regenerate synthesis">
            <IconButton onClick={() => handleGenerateSynthesis(true)} disabled={synthesisLoading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        )}
      </Box>

      <Grid container spacing={3}>
        {/* Storyline Info */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  mb: 2,
                }}
              >
                <Typography variant='h4' component='h1'>
                  {storyline.title || 'Untitled Storyline'}
                </Typography>
                <Chip
                  label={storyline.status?.toUpperCase() || 'UNKNOWN'}
                  color={getStatusColor(storyline.status)}
                  variant='outlined'
                />
              </Box>

              {storyline.description && (
                <Typography
                  variant='body1'
                  color='text.secondary'
                  sx={{ mb: 2 }}
                >
                  {storyline.description}
                </Typography>
              )}

              {/* Analysis Summary Section */}
              {storyline.analysis_summary ? (
                <Box
                  sx={{
                    mb: 2,
                    p: 2,
                    bgcolor: 'background.default',
                    borderRadius: 1,
                  }}
                >
                  <Typography variant='h6' sx={{ mb: 1 }}>
                    Analysis Summary
                  </Typography>
                  <Typography variant='body1' sx={{ whiteSpace: 'pre-wrap' }}>
                    {storyline.analysis_summary}
                  </Typography>
                  {storyline.quality_score && (
                    <Box
                      sx={{
                        mt: 1,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                      }}
                    >
                      <Typography variant='caption' color='text.secondary'>
                        Quality Score:
                      </Typography>
                      <Chip
                        label={`${Math.round(storyline.quality_score * 100)}%`}
                        size='small'
                        color={
                          storyline.quality_score >= 0.8
                            ? 'success'
                            : storyline.quality_score >= 0.6
                              ? 'warning'
                              : 'default'
                        }
                      />
                    </Box>
                  )}
                </Box>
              ) : (
                <Alert severity='info' sx={{ mb: 2 }}>
                  <Typography variant='body2'>
                    No analysis summary available. Click "Analyze Storyline" to
                    generate an AI-powered summary of this storyline's articles.
                  </Typography>
                </Alert>
              )}

              <Box sx={{ display: 'flex', gap: 3 }}>
                <Typography variant='body2' color='text.secondary'>
                  <strong>Articles:</strong>{' '}
                  {storyline?.article_count ?? articles?.length ?? 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  <strong>Last Updated:</strong>{' '}
                  {formatDate(storyline.updated_at)}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  <strong>Created:</strong> {formatDate(storyline.created_at)}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Timeline Section */}
        {showTimeline && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box
                  sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}
                >
                  <TimelineIcon color='primary' />
                  <Typography variant='h6'>Timeline</Typography>
                </Box>

                {timelineLoading ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <CircularProgress />
                  </Box>
                ) : timeline.length > 0 ? (
                  <Timeline>
                    {timeline.map((event, index) => (
                      <TimelineItem key={event.article_id || index}>
                        <TimelineOppositeContent
                          sx={{ m: 'auto 0' }}
                          align='right'
                          variant='body2'
                          color='text.secondary'
                        >
                          {event.published_at
                            ? formatDate(event.published_at)
                            : 'No date'}
                        </TimelineOppositeContent>
                        <TimelineSeparator>
                          <TimelineConnector />
                          <TimelineDot color='primary'>
                            <EventIcon />
                          </TimelineDot>
                          <TimelineConnector />
                        </TimelineSeparator>
                        <TimelineContent sx={{ py: '12px', px: 2 }}>
                          <Typography variant='h6' component='span'>
                            {event.title || 'Untitled Event'}
                          </Typography>
                          <Typography variant='body2' color='text.secondary'>
                            {event.source_domain || 'Unknown Source'}
                          </Typography>
                          {event.event_type && (
                            <Chip
                              label={event.event_type}
                              size='small'
                              sx={{ mt: 1, mr: 1 }}
                            />
                          )}
                          {event.confidence_score && (
                            <Chip
                              label={`Confidence: ${(
                                event.confidence_score * 100
                              ).toFixed(0)}%`}
                              size='small'
                              variant='outlined'
                              sx={{ mt: 1 }}
                            />
                          )}
                          {event.event_description && (
                            <Typography variant='body2' sx={{ mt: 1 }}>
                              {event.event_description}
                            </Typography>
                          )}
                          {event.summary && (
                            <Typography
                              variant='body2'
                              sx={{ mt: 1, fontStyle: 'italic' }}
                            >
                              {event.summary.length > 150
                                ? `${event.summary.substring(0, 150)}...`
                                : event.summary}
                            </Typography>
                          )}
                        </TimelineContent>
                      </TimelineItem>
                    ))}
                  </Timeline>
                ) : (
                  <Typography variant='body2' color='text.secondary'>
                    No timeline events found for this storyline
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Articles in Storyline */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  mb: 2,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Article color='primary' />
                  <Typography variant='h6'>
                    Articles in this Storyline ({articles.length})
                  </Typography>
                </Box>
                <Button
                  variant='outlined'
                  startIcon={<AddIcon />}
                  onClick={() => {
                    setShowAddArticles(true);
                    loadAvailableArticles();
                  }}
                  size='small'
                >
                  Add Articles
                </Button>
              </Box>

              {articles.length > 0 ? (
                <List>
                  {articles.map((article, index) => (
                    <React.Fragment key={article.id || index}>
                      <ListItem>
                        <ListItemText
                          primary={
                            <Typography
                              variant='h6'
                              sx={{ cursor: 'pointer' }}
                              onClick={() =>
                                navigateToDomain(`/articles/${article.id}`)
                              }
                            >
                              {article.title || 'Untitled Article'}
                            </Typography>
                          }
                          secondary={
                            <Box>
                              <Typography
                                variant='body2'
                                color='text.secondary'
                              >
                                {article.source_domain || 'Unknown Source'} •{' '}
                                {formatDate(article.published_at)}
                              </Typography>
                              {article.category && (
                                <Chip
                                  label={article.category}
                                  size='small'
                                  sx={{ mt: 0.5 }}
                                />
                              )}
                              {article.summary && (
                                <Typography variant='body2' sx={{ mt: 1 }}>
                                  {article.summary.length > 200
                                    ? `${article.summary.substring(0, 200)}...`
                                    : article.summary}
                                </Typography>
                              )}
                            </Box>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Tooltip title='Remove from storyline'>
                            <IconButton
                              edge='end'
                              onClick={() => handleRemoveArticle(article.id)}
                              color='error'
                              size='small'
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < articles.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  No articles found in this storyline
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Add Articles Dialog */}
      <Dialog
        open={showAddArticles}
        onClose={() => setShowAddArticles(false)}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>
          <Box
            display='flex'
            justifyContent='space-between'
            alignItems='center'
          >
            <Typography variant='h6'>Add Articles to Storyline</Typography>
            <IconButton onClick={() => setShowAddArticles(false)} size='small'>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent>
          <TextField
            fullWidth
            placeholder='Search articles...'
            value={searchTerm}
            onChange={e => {
              const newSearch = e.target.value;
              setSearchTerm(newSearch);
              // Debounce server-side search
              clearTimeout(window.searchTimeout);
              window.searchTimeout = setTimeout(() => {
                loadAvailableArticles(newSearch);
              }, 300);
            }}
            InputProps={{
              startAdornment: (
                <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
              ),
            }}
            sx={{ mb: 2 }}
          />

          <Box sx={{ maxHeight: '400px', overflow: 'auto' }}>
            {addArticlesLoading ? (
              <Box display='flex' justifyContent='center' p={2}>
                <CircularProgress />
              </Box>
            ) : (
              <List dense>
                {availableArticles.length === 0 ? (
                  <ListItem>
                    <ListItemText primary='No articles found. Try a different search term.' />
                  </ListItem>
                ) : (
                  availableArticles.map((article, index) => (
                    <React.Fragment key={article.id}>
                      <ListItem>
                        <ListItemText
                          primary={article.title}
                          secondary={`${article.source_domain} • ${formatDate(
                            article.published_at,
                          )}`}
                        />
                        <ListItemSecondaryAction>
                          <Button
                            variant={
                              selectedArticles.includes(article.id)
                                ? 'contained'
                                : 'outlined'
                            }
                            size='small'
                            onClick={() => {
                              setSelectedArticles(prev =>
                                prev.includes(article.id)
                                  ? prev.filter(id => id !== article.id)
                                  : [...prev, article.id],
                              );
                            }}
                          >
                            {selectedArticles.includes(article.id)
                              ? 'Selected'
                              : 'Select'}
                          </Button>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < availableArticles.length - 1 ? (
                        <Divider />
                      ) : null}
                    </React.Fragment>
                  ))
                )}
              </List>
            )}
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setShowAddArticles(false)}>Cancel</Button>
          <Button
            variant='contained'
            onClick={handleAddSelectedArticles}
            disabled={addArticlesLoading || selectedArticles.length === 0}
            startIcon={<AddIcon />}
          >
            Add {selectedArticles.length} Articles
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Storyline Dialog */}
      <StorylineManagementDialog
        open={showEditDialog}
        onClose={() => setShowEditDialog(false)}
        storyline={storyline}
        onStorylineUpdated={handleStorylineUpdated}
      />

      {/* Automation Settings Dialog */}
      <StorylineAutomationDialog
        open={showAutomationDialog}
        onClose={() => setShowAutomationDialog(false)}
        storylineId={id}
        onSettingsUpdated={() => {
          loadStoryline();
          setShowAutomationDialog(false);
        }}
      />

      {/* Article Suggestions Dialog */}
      <ArticleSuggestionsDialog
        open={showSuggestionsDialog}
        onClose={() => setShowSuggestionsDialog(false)}
        storylineId={id}
        onArticleAdded={() => {
          loadStoryline();
        }}
      />

      {/* Full Synthesis Reader Dialog */}
      <Dialog
        open={showFullSynthesis}
        onClose={() => setShowFullSynthesis(false)}
        maxWidth='lg'
        fullWidth
        PaperProps={{ sx: { minHeight: '80vh', maxHeight: '90vh' } }}
      >
        <DialogTitle>
          <Box display='flex' justifyContent='space-between' alignItems='center'>
            <Box>
              <Typography variant='h5'>
                {synthesis?.title || storyline?.title || 'Synthesized Article'}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                {synthesis?.word_count && (
                  <Chip label={`${synthesis.word_count} words`} size='small' />
                )}
                {synthesis?.quality_score && (
                  <Chip
                    label={`Quality: ${Math.round(synthesis.quality_score * 100)}%`}
                    size='small'
                    color={synthesis.quality_score > 0.7 ? 'success' : 'warning'}
                  />
                )}
                {synthesis?.sources?.length && (
                  <Chip label={`${synthesis.sources.length} sources`} size='small' variant='outlined' />
                )}
              </Box>
            </Box>
            <IconButton onClick={() => setShowFullSynthesis(false)}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          <Box sx={{
            maxWidth: '800px',
            mx: 'auto',
            '& h2': { mt: 3, mb: 2, borderBottom: '1px solid #e0e0e0', pb: 1 },
            '& h3': { mt: 2, mb: 1, color: 'primary.main' },
            '& p': { lineHeight: 1.8, textAlign: 'justify', mb: 2 },
          }}>
            {synthesis?.content ? (
              <Typography
                variant='body1'
                component='div'
                sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}
              >
                {synthesis.content}
              </Typography>
            ) : (
              <Typography color='text.secondary'>
                No synthesized content available.
              </Typography>
            )}

            {/* Key Terms Section */}
            {synthesis?.key_terms && Object.keys(synthesis.key_terms).length > 0 && (
              <Box sx={{ mt: 4, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant='h6' gutterBottom>Key Terms</Typography>
                {Object.entries(synthesis.key_terms).map(([term, definition], idx) => (
                  <Box key={idx} sx={{ mb: 1 }}>
                    <Typography variant='subtitle2' component='span' fontWeight='bold'>
                      {term}:
                    </Typography>
                    <Typography variant='body2' component='span' sx={{ ml: 1 }}>
                      {definition}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}

            {/* Timeline Section */}
            {synthesis?.timeline && synthesis.timeline.length > 0 && (
              <Box sx={{ mt: 4, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant='h6' gutterBottom>Timeline</Typography>
                {synthesis.timeline.map((event, idx) => (
                  <Box key={idx} sx={{ mb: 1, display: 'flex', gap: 2 }}>
                    <Typography variant='body2' fontWeight='bold' sx={{ minWidth: 100 }}>
                      {event.date || 'N/A'}
                    </Typography>
                    <Typography variant='body2'>
                      {event.event}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}

            {/* Sources Section */}
            {synthesis?.sources && synthesis.sources.length > 0 && (
              <Box sx={{ mt: 4, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant='h6' gutterBottom>Sources ({synthesis.sources.length})</Typography>
                <List dense>
                  {synthesis.sources.slice(0, 20).map((source, idx) => (
                    <ListItem key={idx} sx={{ py: 0 }}>
                      <ListItemText
                        primary={
                          <a
                            href={source.url}
                            target='_blank'
                            rel='noopener noreferrer'
                            style={{ color: '#1976d2', textDecoration: 'none' }}
                          >
                            {source.title}
                          </a>
                        }
                        secondary={source.source_name}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setShowFullSynthesis(false)}>Close</Button>
          <Button
            variant='outlined'
            onClick={() => handleGenerateSynthesis(true)}
            disabled={synthesisLoading}
            startIcon={<RefreshIcon />}
          >
            Regenerate
          </Button>
          <Button
            variant='contained'
            onClick={() => navigateToDomain(`/storylines/${id}/synthesis`)}
          >
            Open Full View
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StorylineDetail;
