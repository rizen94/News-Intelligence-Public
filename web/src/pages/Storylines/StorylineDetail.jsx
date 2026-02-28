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
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import apiService from '../../services/apiService';
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
  const effectiveDomain = domain || 'politics';
  const [storyline, setStoryline] = useState(null);
  const [articles, setArticles] = useState([]);
  const [timelineData, setTimelineData] = useState(null); // { events, gaps, milestones, time_span, event_count, source_count }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showAutomationDialog, setShowAutomationDialog] = useState(false);
  const [showSuggestionsDialog, setShowSuggestionsDialog] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [isWatched, setIsWatched] = useState(false);
  const [watchLoading, setWatchLoading] = useState(false);

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
  const [processingStatus, setProcessingStatus] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStartTime, setProcessingStartTime] = useState(null);
  const [, setElapsedTick] = useState(0);
  const mountedRef = useRef(true);

  const startProcessingPoll = () => {
    if (!id) return null;
    const pollInterval = setInterval(async() => {
      if (!mountedRef.current) return;
      try {
        const response = await apiService.getStoryline(id, effectiveDomain);
        const storylineData = response.data?.storyline || response.storyline || response;
        if (!storylineData || typeof storylineData !== 'object' || response?.error) return;
        if (storylineData.ml_processing_status === 'pending' || storylineData.ml_processing_status === 'processing') {
          setIsProcessing(true);
          setProcessingStatus('LLM processing in progress...');
          if (Math.random() < 0.3) await loadStoryline();
        } else if (storylineData.ml_processing_status === 'completed' && storylineData.analysis_summary) {
          setIsProcessing(false);
          setProcessingStatus(null);
          await loadStoryline();
          clearInterval(pollInterval);
        } else if (storylineData.ml_processing_status === 'failed') {
          setIsProcessing(false);
          setProcessingStatus(null);
          setError('LLM processing failed. Please try analyzing again.');
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error('Error polling processing status:', err);
      }
    }, 10000);
    setTimeout(() => {
      clearInterval(pollInterval);
      setIsProcessing(false);
    }, 600000);
    return pollInterval;
  };

  // Track when processing starts so we can show elapsed time
  const prevProcessingRef = useRef(false);
  useEffect(() => {
    if (isProcessing && !prevProcessingRef.current) {
      setProcessingStartTime(Date.now());
    }
    if (!isProcessing) {
      setProcessingStartTime(null);
    }
    prevProcessingRef.current = isProcessing;
  }, [isProcessing]);

  // Elapsed-time updater: every 1 min for first 10 min, then every 5 min
  const elapsedIntervalRef = useRef(null);
  useEffect(() => {
    if (!isProcessing || !processingStartTime) return;
    const tick = () => {
      if (!mountedRef.current) return;
      const elapsedMs = Date.now() - processingStartTime;
      const elapsedMin = Math.floor(elapsedMs / 60000);
      if (elapsedMin >= 10 && elapsedIntervalRef.current) {
        clearInterval(elapsedIntervalRef.current);
        elapsedIntervalRef.current = setInterval(() => {
          if (!mountedRef.current) return;
          setElapsedTick(t => t + 1);
        }, 300000);
      }
      setElapsedTick(t => t + 1);
    };
    elapsedIntervalRef.current = setInterval(tick, 60000);
    return () => {
      if (elapsedIntervalRef.current) {
        clearInterval(elapsedIntervalRef.current);
        elapsedIntervalRef.current = null;
      }
    };
  }, [isProcessing, processingStartTime]);

  useEffect(() => {
    mountedRef.current = true;
    if (id) {
      loadStoryline();
      const pollInterval = startProcessingPoll();
      return () => {
        mountedRef.current = false;
        if (pollInterval) clearInterval(pollInterval);
      };
    } else {
      setLoading(false);
    }
  }, [id]);

  const loadStoryline = async() => {
    try {
      setLoading(true);
      setError(null);

      // Load storyline and timeline in parallel for coordinated data
      const [storylineResponse, timelineResponse] = await Promise.all([
        apiService.getStoryline(id, effectiveDomain),
        apiService.getStorylineTimeline(id, effectiveDomain),
      ]);

      // Check for error in storyline response
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

      if (!mountedRef.current) return;
      setStoryline(storylineData);
      setArticles(articlesData);

      // Set timeline data from parallel fetch (events, gaps, milestones, time_span)
      if (timelineResponse?.success && timelineResponse.data) {
        setTimelineData({
          events: timelineResponse.data.events || [],
          gaps: timelineResponse.data.gaps || [],
          milestones: timelineResponse.data.milestones || [],
          time_span: timelineResponse.data.time_span || null,
          event_count: timelineResponse.data.event_count ?? (timelineResponse.data.events?.length || 0),
          source_count: timelineResponse.data.source_count ?? 1,
        });
      } else {
        if (mountedRef.current) setTimelineData(null);
      }

      if (!mountedRef.current) return;

      // Load watchlist status (non-blocking)
      try {
        const wl = await apiService.getWatchlist();
        if (wl?.data) {
          setIsWatched(wl.data.some(w => w.storyline_id === storylineData.id));
        }
      } catch { /* non-critical */ }

      // Check if storyline is being processed
      if (storylineData.ml_processing_status === 'pending' || storylineData.ml_processing_status === 'processing') {
        setIsProcessing(true);
        setProcessingStatus('LLM processing in progress...');
      } else if (storylineData.ml_processing_status === 'completed') {
        setIsProcessing(false);
        setProcessingStatus(null);
      }
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

  const refreshTimeline = async() => {
    try {
      const tl = await apiService.getStorylineTimeline(id, effectiveDomain);
      if (tl?.success && tl.data) {
        setTimelineData({
          events: tl.data.events || [],
          gaps: tl.data.gaps || [],
          milestones: tl.data.milestones || [],
          time_span: tl.data.time_span || null,
          event_count: tl.data.event_count ?? (tl.data.events?.length || 0),
          source_count: tl.data.source_count ?? 1,
        });
      }
    } catch { /* non-critical */ }
  };

  const loadAvailableArticles = async(searchTerm = '') => {
    try {
      setAddArticlesLoading(true);
      const response = await apiService.getAvailableArticles(
        id,
        { page_size: 100, search: searchTerm || undefined },
        effectiveDomain,
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
        effectiveDomain,
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
        apiService.addArticleToStoryline(id, articleId, effectiveDomain),
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

  const handleToggleWatch = async () => {
    setWatchLoading(true);
    try {
      if (isWatched) {
        await apiService.removeFromWatchlist(storyline.id);
        setIsWatched(false);
      } else {
        await apiService.addToWatchlist(storyline.id);
        setIsWatched(true);
      }
    } catch (err) {
      console.error('Watchlist toggle failed:', err);
    } finally {
      setWatchLoading(false);
    }
  };

  const handleAnalyzeStoryline = async() => {
    try {
      setAnalyzing(true);
      setError(null);
      console.log(`Starting analysis for storyline ${id} in domain ${domain}`);
      const response = await apiService.analyzeStoryline(id, effectiveDomain);
      console.log('Analyze response:', response);
      if (response && response.success) {
        // Show success message
        setError(null);
        setIsProcessing(true);
        setProcessingStatus('Analysis started! Generating comprehensive summary, timeline, and breakdown...');
        // Don't show alert - let the processing status indicator handle it

        // Poll for updated analysis summary (check every 5 seconds for up to 2 minutes)
        let attempts = 0;
        const maxAttempts = 24; // 2 minutes max
        const pollInterval = setInterval(async() => {
          attempts++;
          try {
            const response = await apiService.getStoryline(id, effectiveDomain);
            if (
              response.success &&
              response.data?.storyline?.analysis_summary
            ) {
              clearInterval(pollInterval);
              await loadStoryline(); // Reload to show the new summary and timeline
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
        const errorMsg = response?.error || response?.message || 'Failed to start analysis';
        console.error('Analysis failed:', errorMsg, response);
        setError(errorMsg);
      }
    } catch (err) {
      console.error('Error analyzing storyline:', err);
      const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to analyze storyline';
      setError(errorMsg);
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
      const response = await fetch(`/api/v4/${effectiveDomain}/synthesis/storyline/${id}/cached`);
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
      const response = await fetch(`/api/v4/${effectiveDomain}/synthesis/storyline/${id}`, {
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

  const getEstimatedProcessingTime = articleCount => {
    const n = articleCount || 0;
    if (n <= 10) return '2–4 minutes';
    if (n <= 25) return '4–6 minutes';
    if (n <= 50) return '6–9 minutes';
    return '8–12 minutes';
  };

  const getStatusColor = status => {
    switch (status) {
    case 'active':
      return 'success';
    case 'developing':
      return 'warning';
    case 'dormant':
      return 'warning';
    case 'watching':
      return 'info';
    case 'concluded':
    case 'archived':
    default:
      return 'primary'; // use primary instead of 'default' (not in theme palette)
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

  // Guard: no storyline id in route (invalid route)
  if (!id) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        Invalid storyline route. Please select a storyline from the list.
      </Alert>
    );
  }

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
          variant='outlined'
          color='info'
          onClick={() => navigate(`/${effectiveDomain}/storylines/${id}/timeline`)}
        >
          Interactive Timeline
        </Button>
        <Button
          variant={isWatched ? 'contained' : 'outlined'}
          color={isWatched ? 'warning' : 'inherit'}
          onClick={handleToggleWatch}
          disabled={watchLoading}
        >
          {watchLoading ? 'Updating...' : isWatched ? 'Watching' : 'Watch'}
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
            <span>
              <IconButton onClick={() => handleGenerateSynthesis(true)} disabled={synthesisLoading}>
                <RefreshIcon />
              </IconButton>
            </span>
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

              {/* Processing Status */}
              {isProcessing && (
                <Alert severity='info' sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <CircularProgress size={20} />
                      <Typography variant='body2'>
                        {processingStatus || 'Generating comprehensive analysis, timeline, and breakdown...'}
                      </Typography>
                    </Box>
                    <Typography variant='caption' color='text.secondary' sx={{ ml: 4.5 }}>
                      Estimated time: {getEstimatedProcessingTime(articles.length || storyline?.article_count)} (based on {articles.length || storyline?.article_count || 0} articles)
                    </Typography>
                    {processingStartTime && (
                      <Typography variant='caption' color='text.secondary' sx={{ ml: 4.5 }}>
                        Elapsed: {Math.floor((Date.now() - processingStartTime) / 60000)} min
                      </Typography>
                    )}
                  </Box>
                </Alert>
              )}

              {/* Analysis Summary Section */}
              {storyline.analysis_summary ? (
                <Box
                  sx={{
                    mb: 2,
                    p: 3,
                    bgcolor: 'background.default',
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <AutoAwesomeIcon color='primary' />
                    <Typography variant='h6'>
                      Comprehensive Analysis
                    </Typography>
                    {storyline.ml_processing_status === 'completed' && (
                      <Chip label='LLM Generated' size='small' color='success' />
                    )}
                  </Box>
                  <Typography 
                    variant='body1' 
                    component='div'
                    sx={{ 
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.8,
                      '& h2': { 
                        mt: 3, 
                        mb: 2, 
                        fontSize: '1.5rem',
                        fontWeight: 600,
                        borderBottom: '2px solid',
                        borderColor: 'primary.main',
                        pb: 1 
                      },
                      '& h3': { 
                        mt: 2, 
                        mb: 1, 
                        fontSize: '1.25rem',
                        color: 'primary.main' 
                      },
                      '& p': { 
                        lineHeight: 1.8, 
                        textAlign: 'justify', 
                        mb: 2 
                      },
                      '& ul, & ol': {
                        pl: 3,
                        mb: 2,
                      },
                      '& li': {
                        mb: 1,
                        lineHeight: 1.7,
                      },
                      '& strong': {
                        fontWeight: 600,
                        color: 'text.primary',
                      },
                    }}
                  >
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

        {/* Timeline Section - temporal and extracted events */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 2,
                  mb: 2,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TimelineIcon color='primary' />
                  <Typography variant='h6'>
                    Timeline
                    {timelineData?.event_count != null && ` (${timelineData.event_count} events)`}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {timelineData?.time_span && (
                    <Chip
                      label={`${timelineData.time_span.days} days (${formatDate(timelineData.time_span.start)} → ${formatDate(timelineData.time_span.end)})`}
                      size='small'
                      variant='outlined'
                      color='primary'
                    />
                  )}
                  {timelineData?.source_count > 1 && (
                    <Chip
                      label={`${timelineData.source_count} sources`}
                      size='small'
                      variant='outlined'
                      color='secondary'
                    />
                  )}
                  {timelineData?.milestones?.length > 0 && (
                    <Chip
                      label={`${timelineData.milestones.length} milestones`}
                      size='small'
                      variant='outlined'
                    />
                  )}
                  <Button
                    size='small'
                    variant='outlined'
                    onClick={() => navigate(`/${effectiveDomain}/storylines/${id}/timeline`)}
                  >
                    Interactive Timeline
                  </Button>
                </Box>
              </Box>

              {timelineData?.milestones?.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant='caption' color='text.secondary' sx={{ display: 'block', mb: 0.5 }}>
                    Key Milestones
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {timelineData.milestones.map((m, i) => (
                      <Chip
                        key={i}
                        label={m.label}
                        size='small'
                        variant='outlined'
                        color={m.type === 'resolution' ? 'success' : m.type === 'escalation' ? 'warning' : 'info'}
                      />
                    ))}
                  </Box>
                </Box>
              )}

              {timelineData?.events?.length > 0 ? (
                <Timeline position='right'>
                  {timelineData.events.map((evt, index) => {
                    const evtId = evt.id ?? evt.event_id ?? index;
                    const gap = timelineData.gaps?.find(g => String(g.after_event_id) === String(evtId));
                    return (
                      <React.Fragment key={evtId}>
                        <TimelineItem>
                          <TimelineOppositeContent sx={{ m: 'auto 0' }} align='right' variant='body2' color='text.secondary'>
                            {evt.event_date ? formatDate(evt.event_date) : 'No date'}
                          </TimelineOppositeContent>
                          <TimelineSeparator>
                            <TimelineConnector />
                            <TimelineDot color='primary'>
                              <EventIcon />
                            </TimelineDot>
                            <TimelineConnector />
                          </TimelineSeparator>
                          <TimelineContent sx={{ py: '12px', px: 2 }}>
                            <Typography variant='subtitle1' component='span'>
                              {evt.title || 'Untitled Event'}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                              {(evt.event_type || 'general') !== 'general' && (
                                <Chip label={(evt.event_type || '').replace(/_/g, ' ')} size='small' />
                              )}
                              {evt.location && evt.location !== 'unknown' && (
                                <Chip label={evt.location} size='small' variant='outlined' />
                              )}
                              {evt.source_count > 1 && (
                                <Chip label={`${evt.source_count} sources`} size='small' color='info' variant='outlined' />
                              )}
                              {evt.is_ongoing && (
                                <Chip label='ongoing' size='small' color='warning' variant='outlined' />
                              )}
                            </Box>
                            {evt.description && (
                              <Typography variant='body2' sx={{ mt: 1 }} color='text.secondary'>
                                {evt.description.length > 200 ? `${evt.description.substring(0, 200)}...` : evt.description}
                              </Typography>
                            )}
                          </TimelineContent>
                        </TimelineItem>
                        {gap && (
                          <TimelineItem>
                            <TimelineOppositeContent sx={{ flex: 0.25 }} />
                            <TimelineSeparator>
                              <TimelineDot sx={{ bgcolor: 'transparent', border: '2px dashed', borderColor: 'divider' }} />
                              <TimelineConnector sx={{ borderStyle: 'dashed' }} />
                            </TimelineSeparator>
                            <TimelineContent>
                              <Chip
                                label={`${gap.gap_days}-day gap`}
                                size='small'
                                variant='outlined'
                                sx={{ fontStyle: 'italic' }}
                              />
                            </TimelineContent>
                          </TimelineItem>
                        )}
                      </React.Fragment>
                    );
                  })}
                </Timeline>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  No timeline events yet. Run &quot;Analyze Storyline&quot; to extract events from articles.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

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
        domain={effectiveDomain}
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
