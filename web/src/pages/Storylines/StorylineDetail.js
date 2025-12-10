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

import { apiService } from '../../services/apiService.ts';
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

  useEffect(() => {
    if (id) {
      loadStoryline();
    }
  }, [id]);

  const loadStoryline = async() => {
    try {
      setLoading(true);
      setError(null);

      console.log('Loading storyline with ID:', id);
      const storylineResponse = await apiService.getStoryline(id, domain);
      console.log('Storyline response:', storylineResponse);
      console.log('Response success:', storylineResponse.success);
      console.log('Response data:', storylineResponse.data);

      // Handle both success: true and success: True (Python boolean)
      if (storylineResponse.success === true || storylineResponse.success === 'True') {
        const responseData = storylineResponse.data || {};
        const storylineData = responseData.storyline || responseData;
        const articlesData = responseData.articles || [];

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
      } else {
        console.error('Storyline response not successful:', storylineResponse);
        setError('Failed to load storyline');
      }
    } catch (err) {
      console.error('Error loading storyline:', err);
      setError('Failed to load storyline');
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
    </Box>
  );
};

export default StorylineDetail;
