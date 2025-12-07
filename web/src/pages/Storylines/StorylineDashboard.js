import {
  Add,
  Timeline as TimelineIcon,
  Article,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  Assessment as AssessmentIcon,
  Refresh,
  Visibility,
  Edit,
  Share as ShareIcon,
  Bookmark,
  AutoAwesome as AutoAwesomeIcon,
  Schedule,
  Group as GroupIcon,
  Analytics,
  ExpandMore,
  PlayArrow as PlayArrowIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  Chip,
  Button,
  IconButton,
  Tooltip,
  Alert,
  LinearProgress,
  CircularProgress,
  Fab,
  Badge,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiService, api } from '../../services/apiService.ts';

const StorylineDashboard = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [storylines, setStorylines] = useState([]);
  const [recentArticles, setRecentArticles] = useState([]);
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [topicClusters, setTopicClusters] = useState([]);
  const [systemStats, setSystemStats] = useState(null);

  const loadDashboardData = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);

      const [
        storylinesResponse,
        articlesResponse,
        topicsResponse,
        clustersResponse,
        statsResponse,
      ] = await Promise.all([
        apiService.getStorylines({ limit: 10 }),
        apiService.getArticles({ limit: 8 }),
        apiService.getTrendingTopics(24, 5),
        apiService.getBigPicture(168),
        api.get('/api/v4/system-monitoring/health'),
      ]);

      if (storylinesResponse.success) {
        setStorylines(storylinesResponse.data?.storylines || []);
      }

      if (articlesResponse.success) {
        setRecentArticles(articlesResponse.data?.articles || []);
      }

      if (topicsResponse.success) {
        setTrendingTopics(topicsResponse.data || []);
      }

      if (clustersResponse.success) {
        const dist = clustersResponse.data?.topic_distribution || [];
        const clusters = dist.map((d, idx) => ({
          id: idx + 1,
          name: d.category,
          article_count: d.article_count,
          sources: [],
          avg_quality: 0,
        }));
        setTopicClusters(clusters);
      }

      if (statsResponse.data?.success) {
        setSystemStats({
          article_stats: {
            total_articles: (articlesResponse.data?.articles || []).length,
          },
          rss_stats: { total_feeds: 52 },
          system_health: { status: 'healthy' },
        });
      }
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const handleCreateStoryline = () => {
    navigate('/storylines/new');
  };

  const handleViewStoryline = storylineId => {
    navigate(`/storylines/${storylineId}`);
  };

  const handleViewArticle = articleId => {
    navigate(`/articles/${articleId}`);
  };

  const formatDate = dateString => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = status => {
    switch (status?.toLowerCase()) {
    case 'active':
      return 'success';
    case 'developing':
      return 'warning';
    case 'resolved':
      return 'info';
    case 'archived':
      return 'default';
    default:
      return 'default';
    }
  };

  const getPriorityColor = priority => {
    switch (priority?.toLowerCase()) {
    case 'high':
      return 'error';
    case 'medium':
      return 'warning';
    case 'low':
      return 'success';
    default:
      return 'default';
    }
  };

  if (loading) {
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress size={60} />
        <Typography variant='h6' sx={{ ml: 2 }}>
          Loading your investigative workspace...
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box
        sx={{
          mb: 4,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Box>
          <Typography
            variant='h4'
            component='h1'
            sx={{ fontWeight: 'bold', mb: 1 }}
          >
            My Investigative Workspace
          </Typography>
          <Typography variant='h6' color='text.secondary'>
            Track developing stories, curate evidence, and build comprehensive
            reports
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant='outlined'
            startIcon={<Refresh />}
            onClick={loadDashboardData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant='contained'
            startIcon={<Add />}
            onClick={handleCreateStoryline}
            sx={{ minWidth: 160 }}
          >
            New Storyline
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Active Storylines */}
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  mb: 3,
                }}
              >
                <Typography variant='h6' component='h2'>
                  <TimelineIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Active Storylines
                </Typography>
                <Chip
                  label={`${storylines.length} active`}
                  color='primary'
                  size='small'
                />
              </Box>

              {storylines.length === 0 ? (
                <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'grey.50' }}>
                  <TimelineIcon
                    sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }}
                  />
                  <Typography variant='h6' color='text.secondary' gutterBottom>
                    No active storylines yet
                  </Typography>
                  <Typography
                    variant='body2'
                    color='text.secondary'
                    sx={{ mb: 3 }}
                  >
                    Start your investigation by creating a new storyline or
                    browsing the article queue
                  </Typography>
                  <Box
                    sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}
                  >
                    <Button
                      variant='contained'
                      startIcon={<Add />}
                      onClick={handleCreateStoryline}
                    >
                      Create Storyline
                    </Button>
                    <Button
                      variant='outlined'
                      startIcon={<Article />}
                      onClick={() => navigate('/articles')}
                    >
                      Browse Articles
                    </Button>
                  </Box>
                </Paper>
              ) : (
                <List>
                  {storylines.map((storyline, index) => (
                    <React.Fragment key={storyline.id}>
                      <ListItem
                        sx={{
                          border: 1,
                          borderColor: 'divider',
                          borderRadius: 1,
                          mb: 1,
                          bgcolor: 'background.paper',
                          '&:hover': { bgcolor: 'action.hover' },
                        }}
                      >
                        <ListItemIcon>
                          <Avatar sx={{ bgcolor: 'primary.main' }}>
                            <TimelineIcon />
                          </Avatar>
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                mb: 1,
                              }}
                            >
                              <Typography variant='h6' sx={{ flexGrow: 1 }}>
                                {storyline.title || 'Untitled Storyline'}
                              </Typography>
                              <Box sx={{ display: 'flex', gap: 1 }}>
                                {storyline.status && (
                                  <Chip
                                    label={storyline.status}
                                    color={getStatusColor(storyline.status)}
                                    size='small'
                                  />
                                )}
                                {storyline.priority && (
                                  <Chip
                                    label={storyline.priority}
                                    color={getPriorityColor(storyline.priority)}
                                    size='small'
                                    variant='outlined'
                                  />
                                )}
                              </Box>
                            </Box>
                          }
                          secondary={
                            <Box>
                              <Typography
                                variant='body2'
                                color='text.secondary'
                                sx={{ mb: 1 }}
                              >
                                {storyline.description ||
                                  'No description available'}
                              </Typography>
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 2,
                                }}
                              >
                                <Box
                                  sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 0.5,
                                  }}
                                >
                                  <Article fontSize='small' />
                                  <Typography variant='caption'>
                                    {storyline.article_count || 0} articles
                                  </Typography>
                                </Box>
                                <Typography variant='caption'>
                                  Updated:{' '}
                                  {formatDate(
                                    storyline.updated_at || storyline.created_at,
                                  )}
                                </Typography>
                                {storyline.impact_score && (
                                  <Chip
                                    label={`Impact: ${Math.round(
                                      storyline.impact_score * 100,
                                    )}%`}
                                    size='small'
                                    color='primary'
                                    variant='outlined'
                                  />
                                )}
                              </Box>
                            </Box>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Tooltip title='View Details'>
                              <IconButton
                                size='small'
                                onClick={() =>
                                  handleViewStoryline(storyline.id)
                                }
                              >
                                <Visibility />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title='Edit'>
                              <IconButton size='small'>
                                <Edit />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title='Share'>
                              <IconButton size='small'>
                                <ShareIcon />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < storylines.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions & Stats */}
        <Grid item xs={12} lg={4}>
          <Grid container spacing={2}>
            {/* System Stats */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    <Analytics sx={{ mr: 1, verticalAlign: 'middle' }} />
                    System Overview
                  </Typography>
                  {systemStats ? (
                    <Box>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          mb: 1,
                        }}
                      >
                        <Typography variant='body2'>
                          Articles Available
                        </Typography>
                        <Typography
                          variant='body2'
                          color='primary'
                          fontWeight='bold'
                        >
                          {systemStats.article_stats?.total_articles || 0}
                        </Typography>
                      </Box>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          mb: 1,
                        }}
                      >
                        <Typography variant='body2'>RSS Sources</Typography>
                        <Typography
                          variant='body2'
                          color='primary'
                          fontWeight='bold'
                        >
                          {systemStats.rss_stats?.total_feeds || 0}
                        </Typography>
                      </Box>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          mb: 1,
                        }}
                      >
                        <Typography variant='body2'>System Status</Typography>
                        <Chip
                          label={systemStats.system_health?.status || 'Unknown'}
                          color={
                            systemStats.system_health?.status === 'healthy'
                              ? 'success'
                              : 'error'
                          }
                          size='small'
                        />
                      </Box>
                    </Box>
                  ) : (
                    <Typography variant='body2' color='text.secondary'>
                      Loading system stats...
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* Recent Articles */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      mb: 2,
                    }}
                  >
                    <Typography variant='h6'>
                      <Article sx={{ mr: 1, verticalAlign: 'middle' }} />
                      Recent Articles
                    </Typography>
                    <Button size='small' onClick={() => navigate('/articles')}>
                      View All
                    </Button>
                  </Box>
                  {recentArticles.length > 0 ? (
                    <List dense>
                      {recentArticles.slice(0, 4).map(article => (
                        <ListItem
                          key={article.id}
                          sx={{ px: 0, py: 0.5 }}
                          button
                          onClick={() => handleViewArticle(article.id)}
                        >
                          <ListItemText
                            primary={
                              <Typography
                                variant='body2'
                                sx={{
                                  display: '-webkit-box',
                                  WebkitLineClamp: 2,
                                  WebkitBoxOrient: 'vertical',
                                  overflow: 'hidden',
                                  lineHeight: 1.3,
                                }}
                              >
                                {article.title}
                              </Typography>
                            }
                            secondary={
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 1,
                                  mt: 0.5,
                                }}
                              >
                                <Chip
                                  label={article.category || 'Uncategorized'}
                                  size='small'
                                  color='primary'
                                  variant='outlined'
                                />
                                <Typography
                                  variant='caption'
                                  color='text.secondary'
                                >
                                  {formatDate(article.published_at)}
                                </Typography>
                              </Box>
                            }
                          />
                        </ListItem>
                      ))}
                    </List>
                  ) : (
                    <Typography variant='body2' color='text.secondary'>
                      No recent articles available
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* Trending Topics */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                    Trending Topics
                  </Typography>
                  {trendingTopics.length > 0 ? (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {trendingTopics.slice(0, 6).map(topic => (
                        <Chip
                          key={topic.name}
                          label={`${topic.name} (${topic.article_count || 0})`}
                          size='small'
                          color='primary'
                          variant='outlined'
                          onClick={() => navigate('/intelligence')}
                        />
                      ))}
                    </Box>
                  ) : (
                    <Typography variant='body2' color='text.secondary'>
                      No trending topics available
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      {/* Floating Action Button for Quick Storyline Creation */}
      <Fab
        color='primary'
        aria-label='create storyline'
        sx={{
          position: 'fixed',
          bottom: 16,
          right: 16,
        }}
        onClick={handleCreateStoryline}
      >
        <Add />
      </Fab>
    </Box>
  );
};

export default StorylineDashboard;
