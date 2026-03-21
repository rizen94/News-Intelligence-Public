import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDomainNavigation } from '../../hooks/useDomainNavigation';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Badge,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Paper,
  Divider,
  Avatar,
  Link,
  Pagination,
} from '@mui/material';
import {
  ArrowBack,
  Article,
  Search,
  Refresh,
  TrendingUp,
  Visibility,
  OpenInNew,
  CalendarToday,
  Source,
  Psychology,
  BarChart,
} from '@mui/icons-material';
// Import with explicit default to avoid webpack issues
import apiServiceDefault, { getApiService } from '../../services/apiService';
const apiService = apiServiceDefault || getApiService();

const TopicArticles = () => {
  const { topicName } = useParams();
  const navigate = useNavigate();
  const { navigateToDomain } = useDomainNavigation();
  const { domain } = useDomainRoute();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [topicSummary, setTopicSummary] = useState(null);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [limit] = useState(20);

  const loadTopicArticles = async (page = 1) => {
    try {
      setLoading(true);
      setError(null);

      const offset = (page - 1) * limit;
      const response = await apiService.getTopicArticles(
        topicName,
        limit,
        offset,
        domain
      );
      if (response.success) {
        setArticles(response.data.articles);
        setTotalCount(response.data.total);
        setCurrentPage(response.data.page);
      } else {
        setError('Failed to load articles for this topic');
      }
    } catch (err) {
      console.error('Error loading topic articles:', err);
      setError('Failed to load articles for this topic');
    } finally {
      setLoading(false);
    }
  };

  const loadTopicSummary = async () => {
    try {
      const response = await apiService.getTopicSummary(topicName, domain);
      if (response.success) {
        setTopicSummary(response.data);
      }
    } catch (err) {
      console.error('Error loading topic summary:', err);
    }
  };

  useEffect(() => {
    if (topicName) {
      loadTopicArticles();
      loadTopicSummary();
    }
  }, [topicName]);

  const handleRefresh = () => {
    loadTopicArticles(currentPage);
    loadTopicSummary();
  };

  const handleLoadMore = () => {
    const nextPage = currentPage + 1;
    loadTopicArticles(nextPage);
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

  const getSentimentColor = sentiment => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'success';
      case 'negative':
        return 'error';
      case 'neutral':
        return 'default';
      default:
        return 'default';
    }
  };

  const getQualityColor = score => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  if (loading && articles.length === 0) {
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={3}>
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
        <Button
          onClick={() => navigateToDomain('/topics')}
          startIcon={<ArrowBack />}
        >
          Back to Topics
        </Button>
      </Box>
    );
  }

  return (
    <Box p={3}>
      {/* Header */}
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Box display='flex' alignItems='center' gap={2}>
          <IconButton
            onClick={() => navigateToDomain('/topics')}
            color='primary'
          >
            <ArrowBack />
          </IconButton>
          <Box>
            <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
              Topic: {topicName}
            </Typography>
            <Typography variant='body2' color='text.secondary'>
              {totalCount} articles found
            </Typography>
          </Box>
        </Box>
        <Box display='flex' gap={2}>
          <Tooltip title='Refresh'>
            <span>
              <IconButton onClick={handleRefresh} disabled={loading}>
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      {/* Topic Summary */}
      {topicSummary && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box display='flex' alignItems='center' gap={2} mb={2}>
              <Psychology color='primary' />
              <Typography variant='h6' component='h2'>
                Topic Summary
              </Typography>
            </Box>
            <Typography variant='body1' paragraph>
              {topicSummary.summary}
            </Typography>
            <Box display='flex' gap={2} flexWrap='wrap'>
              <Chip
                icon={<BarChart />}
                label={`${topicSummary.article_count} articles`}
                color='primary'
                variant='outlined'
              />
              <Chip
                icon={<TrendingUp />}
                label={`${(topicSummary.avg_relevance * 100).toFixed(
                  1
                )}% avg relevance`}
                color='secondary'
                variant='outlined'
              />
              <Chip
                label={topicSummary.cluster_type || 'General'}
                color='default'
                variant='outlined'
              />
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Articles List */}
      <Grid container spacing={3}>
        {articles.map(article => (
          <Grid item xs={12} key={article.id}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Box
                  display='flex'
                  justifyContent='space-between'
                  alignItems='flex-start'
                  mb={2}
                >
                  <Typography
                    variant='h6'
                    component='h3'
                    sx={{ fontWeight: 'bold', flex: 1, mr: 2 }}
                  >
                    {article.title}
                  </Typography>
                  <Box display='flex' gap={1}>
                    <Tooltip title='View Article'>
                      <IconButton
                        size='small'
                        onClick={() => window.open(article.url, '_blank')}
                      >
                        <OpenInNew />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>

                {article.summary && (
                  <Typography variant='body2' color='text.secondary' paragraph>
                    {article.summary}
                  </Typography>
                )}

                <Box
                  display='flex'
                  alignItems='center'
                  gap={2}
                  mb={2}
                  flexWrap='wrap'
                >
                  <Box display='flex' alignItems='center' gap={1}>
                    <Source fontSize='small' color='action' />
                    <Typography variant='body2' color='text.secondary'>
                      {article.source_domain}
                    </Typography>
                  </Box>
                  <Box display='flex' alignItems='center' gap={1}>
                    <CalendarToday fontSize='small' color='action' />
                    <Typography variant='body2' color='text.secondary'>
                      {formatDate(article.published_at)}
                    </Typography>
                  </Box>
                </Box>

                <Box display='flex' gap={1} flexWrap='wrap' alignItems='center'>
                  <Chip
                    label={`${(article.relevance_score * 100).toFixed(
                      1
                    )}% relevance`}
                    color='primary'
                    size='small'
                    variant='outlined'
                  />
                  <Chip
                    label={article.sentiment_label || 'Neutral'}
                    color={getSentimentColor(article.sentiment_label)}
                    size='small'
                    variant='outlined'
                  />
                  <Chip
                    label={`Quality: ${(article.quality_score * 100).toFixed(
                      0
                    )}%`}
                    color={getQualityColor(article.quality_score)}
                    size='small'
                    variant='outlined'
                  />
                </Box>

                {article.content && (
                  <Box mt={2}>
                    <Typography variant='body2' color='text.secondary'>
                      {article.content}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Load More Button */}
      {articles.length < totalCount && (
        <Box display='flex' justifyContent='center' mt={4}>
          <Button
            variant='outlined'
            onClick={handleLoadMore}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : <Article />}
          >
            Load More Articles
          </Button>
        </Box>
      )}

      {/* Back to Topics */}
      <Box display='flex' justifyContent='center' mt={4}>
        <Button
          variant='contained'
          onClick={() => navigateToDomain('/topics')}
          startIcon={<ArrowBack />}
        >
          Back to Topics
        </Button>
      </Box>
    </Box>
  );
};

export default TopicArticles;
