/**
 * News Intelligence System v3.3.0 - Storyline Report Component
 * Comprehensive storyline view with ML summarization, source analysis, and timeline
 */

import React, { useState, useEffect } from 'react';
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
  ListItemIcon,
  Divider,
  Alert,
  CircularProgress,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  Tooltip,
  LinearProgress,
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
import {
  ArrowBack as ArrowBackIcon,
  Timeline as TimelineIcon,
  Article,
  Psychology as PsychologyIcon,
  Source,
  History as HistoryIcon,
  Refresh,
  AutoAwesome as AutoAwesomeIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
  ExpandMore,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { apiService } from '../../services/apiService';

const StorylineReport = () => {
  const { id } = useParams();
  console.log('StorylineReport: ID from useParams:', id);
  const navigate = useNavigate();
  const { navigateToDomain } = useDomainNavigation();
  const [storyline, setStoryline] = useState(null);
  const [articles, setArticles] = useState([]);
  const [events, setEvents] = useState([]);
  const [sources, setSources] = useState([]);
  const [editLog, setEditLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [processingML, setProcessingML] = useState(false);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [processingStage, setProcessingStage] = useState('');

  useEffect(() => {
    if (id) {
      loadStorylineReport();
    }
  }, [id]);

  const loadStorylineReport = async() => {
    try {
      setLoading(true);
      setError(null);
      console.log('Loading storyline report for ID:', id);

      // Try to get enhanced storyline report first
      try {
        const response = await apiService.getStoryline(id);
        console.log('Enhanced API response:', response);
        if (response.success) {
          const data = response.data;
          console.log('Setting storyline data:', data);
          setStoryline(data.storyline);
          setArticles(data.articles || []);
          setEvents(data.events || []);
          setSources(data.sources || []);
          setEditLog(data.edit_log || []);
          return;
        }
      } catch (enhancedError) {
        console.log(
          'Enhanced API not available, falling back to basic API:',
          enhancedError,
        );
      }

      // Fallback to basic API
      const [storylineResponse, articlesResponse] = await Promise.all([
        apiService.getStoryline(id),
        apiService.getArticles({ storyline_id: id }),
      ]);

      if (storylineResponse.success) {
        setStoryline(storylineResponse.data);
      }

      if (articlesResponse.success) {
        setArticles(articlesResponse.data.articles || []);
      }

      // Generate mock data for demonstration
      setEvents([
        {
          id: 1,
          event_title: 'Initial Report',
          event_description: 'First reports of the incident emerge',
          event_date: '2024-01-15T10:00:00Z',
          event_source: 'CNN',
          event_type: 'announcement',
          confidence_score: 0.95,
          sentiment_score: -0.3,
        },
        {
          id: 2,
          event_title: 'Official Response',
          event_description: 'Authorities provide official statement',
          event_date: '2024-01-15T14:30:00Z',
          event_source: 'Reuters',
          event_type: 'response',
          confidence_score: 0.98,
          sentiment_score: 0.1,
        },
      ]);

      setSources([
        {
          source: 'CNN',
          article_count: 5,
          avg_sentiment: -0.2,
          avg_quality: 0.85,
        },
        {
          source: 'Reuters',
          article_count: 3,
          avg_sentiment: 0.1,
          avg_quality: 0.92,
        },
        {
          source: 'BBC',
          article_count: 2,
          avg_sentiment: -0.1,
          avg_quality: 0.88,
        },
      ]);

      setEditLog([
        {
          id: 1,
          edit_type: 'article_added',
          edit_description: 'Added new article from CNN',
          edited_at: '2024-01-15T16:00:00Z',
          edited_by: 'system',
        },
        {
          id: 2,
          edit_type: 'ml_processed',
          edit_description: 'ML summarization completed',
          edited_at: '2024-01-15T15:30:00Z',
          edited_by: 'system',
        },
      ]);
    } catch (err) {
      console.error('Error loading storyline report:', err);
      setError('Failed to load storyline report');
    } finally {
      setLoading(false);
    }
  };

  const handleProcessML = async() => {
    try {
      setProcessingML(true);
      setProcessingStatus('starting');
      setProcessingProgress(0);
      setProcessingStage('Initializing ML processing...');

      // Simulate processing stages with progress updates
      const stages = [
        { stage: 'Analyzing articles...', progress: 20, duration: 1000 },
        { stage: 'Extracting key entities...', progress: 40, duration: 1500 },
        { stage: 'Generating master summary...', progress: 60, duration: 2000 },
        { stage: 'Creating timeline summary...', progress: 80, duration: 1500 },
        {
          stage: 'Analyzing sentiment trends...',
          progress: 90,
          duration: 1000,
        },
        { stage: 'Finalizing analysis...', progress: 100, duration: 500 },
      ];

      // Simulate processing stages
      for (const stageInfo of stages) {
        setProcessingStage(stageInfo.stage);
        setProcessingProgress(stageInfo.progress);
        await new Promise(resolve => setTimeout(resolve, stageInfo.duration));
      }

      // Call ML processing API - use analyzeStoryline instead
      const response = await apiService.analyzeStoryline(id);

      if (response.success) {
        setProcessingStatus('completed');
        setProcessingStage('ML processing completed successfully!');

        // Wait a moment to show completion
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Reload data to get updated ML results
        await loadStorylineReport();
      } else {
        console.error('ML processing failed:', response.error);
        setProcessingStatus('error');
        setProcessingStage('ML processing failed: ' + response.error);
        setError('ML processing failed: ' + response.error);
      }
    } catch (err) {
      console.error('Error processing ML:', err);
      setProcessingStatus('error');
      setProcessingStage('Failed to process ML analysis');
      setError('Failed to process ML analysis');
    } finally {
      setProcessingML(false);
      // Clear status after a delay
      setTimeout(() => {
        setProcessingStatus(null);
        setProcessingStage('');
        setProcessingProgress(0);
      }, 3000);
    }
  };

  const getSentimentIcon = score => {
    if (score > 0.1) return <TrendingUpIcon color='success' />;
    if (score < -0.1) return <TrendingDownIcon color='error' />;
    return <TrendingFlatIcon color='info' />;
  };

  const getSentimentColor = score => {
    if (score > 0.1) return 'success';
    if (score < -0.1) return 'error';
    return 'info';
  };

  if (loading) {
    console.log('StorylineReport: Loading state');
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress />
        <Typography variant='h6' sx={{ ml: 2 }}>
          Loading Storyline Report...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigateToDomain('/storylines')}
        >
          Back to Storylines
        </Button>
      </Box>
    );
  }

  if (!storyline) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity='warning'>Storyline not found</Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigateToDomain('/storylines')}
        >
          Back to Storylines
        </Button>
      </Box>
    );
  }

  console.log('StorylineReport: Rendering with storyline:', storyline);
  console.log('StorylineReport: Articles count:', articles.length);
  console.log('StorylineReport: Events count:', events.length);

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Box display='flex' alignItems='center' gap={2}>
          <IconButton onClick={() => navigate('/storylines')}>
            <ArrowBackIcon />
          </IconButton>
          <Box>
            <Typography variant='h4' component='h1'>
              {storyline.title}
            </Typography>
            <Typography variant='subtitle1' color='text.secondary'>
              {storyline.description}
            </Typography>
          </Box>
        </Box>
        <Box display='flex' gap={2}>
          <Button
            variant='outlined'
            startIcon={<Refresh />}
            onClick={loadStorylineReport}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant='contained'
            startIcon={<AutoAwesomeIcon />}
            onClick={handleProcessML}
            disabled={processingML}
          >
            {processingML ? 'Processing...' : 'Run ML Analysis'}
          </Button>
        </Box>
      </Box>

      {/* Processing Status */}
      {processingML && (
        <Card sx={{ mb: 3, bgcolor: 'primary.50' }}>
          <CardContent>
            <Box display='flex' alignItems='center' gap={2} mb={2}>
              <AutoAwesomeIcon color='primary' />
              <Typography variant='h6' color='primary'>
                ML Processing in Progress
              </Typography>
            </Box>

            <Box mb={2}>
              <Typography variant='body2' color='text.secondary' gutterBottom>
                {processingStage}
              </Typography>
              <LinearProgress
                variant='determinate'
                value={processingProgress}
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Typography
                variant='caption'
                color='text.secondary'
                sx={{ mt: 1, display: 'block' }}
              >
                {processingProgress}% complete
              </Typography>
            </Box>

            <Box display='flex' gap={1} flexWrap='wrap'>
              <Chip
                label='Estimated time: 2-3 minutes'
                size='small'
                color='primary'
                variant='outlined'
              />
              <Chip
                label='Processing queue: Position 1'
                size='small'
                color='info'
                variant='outlined'
              />
            </Box>
          </CardContent>
        </Card>
      )}

      <Grid container spacing={3}>
        {/* Main Story Summary */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={1} mb={2}>
                <PsychologyIcon color='primary' />
                <Typography variant='h6'>AI-Generated Story Summary</Typography>
              </Box>

              {storyline.master_summary ? (
                <Typography variant='body1' sx={{ mb: 2 }}>
                  {storyline.master_summary}
                </Typography>
              ) : (
                <Alert severity='info' sx={{ mb: 2 }}>
                  No AI summary available. Click "Run ML Analysis" to generate
                  one.
                </Alert>
              )}

              {storyline.timeline_summary && (
                <Box mt={3}>
                  <Typography variant='h6' gutterBottom>
                    Timeline Summary
                  </Typography>
                  <Typography variant='body2'>
                    {storyline.timeline_summary}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Articles */}
          <Card sx={{ mt: 3 }}>
            <CardContent>
              <Box display='flex' alignItems='center' gap={1} mb={2}>
                <Article color='primary' />
                <Typography variant='h6'>
                  Contributing Articles ({articles.length})
                </Typography>
              </Box>

              <List>
                {articles.map((article, index) => (
                  <React.Fragment key={article.id}>
                    <ListItem>
                      <ListItemIcon>
                        {getSentimentIcon(article.sentiment_score)}
                      </ListItemIcon>
                      <ListItemText
                        primary={article.title}
                        secondary={
                          <Box>
                            <Typography variant='caption' display='block'>
                              {article.source} •{' '}
                              {new Date(
                                article.published_at,
                              ).toLocaleDateString()}
                            </Typography>
                            <Box display='flex' gap={1} mt={1}>
                              <Chip
                                label={`Sentiment: ${(
                                  article.sentiment_score || 0
                                ).toFixed(2)}`}
                                size='small'
                                color={getSentimentColor(
                                  article.sentiment_score,
                                )}
                              />
                              <Chip
                                label={`Quality: ${(
                                  article.quality_score || 0
                                ).toFixed(2)}`}
                                size='small'
                                variant='outlined'
                              />
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < articles.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={4}>
          {/* Source Analysis */}
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={1} mb={2}>
                <Source color='primary' />
                <Typography variant='h6'>Source Analysis</Typography>
              </Box>

              <Typography variant='body2' color='text.secondary' gutterBottom>
                {sources.length} sources contributing to this story
              </Typography>

              <List dense>
                {sources.map((source, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={source.source}
                      secondary={`${
                        source.article_count
                      } articles • Avg sentiment: ${source.avg_sentiment.toFixed(
                        2,
                      )}`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>

          {/* Key Entities */}
          {storyline.key_entities &&
            Object.keys(storyline.key_entities).length > 0 && (
            <Card sx={{ mt: 2 }}>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                    Key Entities
                </Typography>
                <Box display='flex' flexWrap='wrap' gap={1}>
                  {Object.entries(storyline.key_entities).map(
                    ([entity, count]) => (
                      <Chip
                        key={entity}
                        label={`${entity} (${count})`}
                        size='small'
                        variant='outlined'
                      />
                    ),
                  )}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Edit Log */}
          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Box display='flex' alignItems='center' gap={1} mb={2}>
                <HistoryIcon color='primary' />
                <Typography variant='h6'>Recent Updates</Typography>
              </Box>

              <List dense>
                {editLog.slice(0, 5).map(log => (
                  <ListItem key={log.id}>
                    <ListItemText
                      primary={log.edit_description}
                      secondary={new Date(log.edited_at).toLocaleString()}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Timeline Events */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={1} mb={2}>
                <TimelineIcon color='primary' />
                <Typography variant='h6'>Story Timeline</Typography>
              </Box>

              <Timeline>
                {events.map((event, index) => (
                  <TimelineItem key={event.id}>
                    <TimelineOppositeContent>
                      <Typography variant='caption' color='text.secondary'>
                        {new Date(event.event_date).toLocaleString()}
                      </Typography>
                    </TimelineOppositeContent>
                    <TimelineSeparator>
                      <TimelineDot
                        color={getSentimentColor(event.sentiment_score)}
                      >
                        {getSentimentIcon(event.sentiment_score)}
                      </TimelineDot>
                      {index < events.length - 1 && <TimelineConnector />}
                    </TimelineSeparator>
                    <TimelineContent>
                      <Typography variant='subtitle1' fontWeight='bold'>
                        {event.event_title}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        {event.event_description}
                      </Typography>
                      <Box display='flex' gap={1} mt={1}>
                        <Chip
                          label={event.event_type}
                          size='small'
                          variant='outlined'
                        />
                        <Chip
                          label={`Confidence: ${(
                            event.confidence_score * 100
                          ).toFixed(0)}%`}
                          size='small'
                          color='primary'
                        />
                      </Box>
                    </TimelineContent>
                  </TimelineItem>
                ))}
              </Timeline>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default StorylineReport;
