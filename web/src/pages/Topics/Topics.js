import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Badge,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Tabs,
  Tab,
  Paper,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp,
  Article,
  Search,
  Refresh,
  Transform,
  Analytics,
  ExpandMore,
  Visibility,
  Cloud,
  BarChart,
  Timeline,
  Psychology,
} from '@mui/icons-material';
import { apiService } from '../../services/apiService.ts';

const Topics = () => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [topicArticles, setTopicArticles] = useState([]);
  const [topicSummary, setTopicSummary] = useState(null);
  const [clustering, setClustering] = useState(false);
  const [categories, setCategories] = useState([]);
  const [activeTab, setActiveTab] = useState(0);

  // New enhanced data states
  const [wordCloudData, setWordCloudData] = useState(null);
  const [bigPictureData, setBigPictureData] = useState(null);
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [timePeriod, setTimePeriod] = useState(24);

  const loadTopics = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        limit: 50,
        search: searchQuery || undefined,
        category: selectedCategory || undefined,
      };

      const response = await apiService.getTopics(params);

      if (response.success) {
        setTopics(response.data.topics || []);
      } else {
        setError(response.message || 'Failed to load topics');
      }
    } catch (err) {
      setError('Error loading topics: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedCategory]);

  const loadTopicArticles = useCallback(async(topicName) => {
    try {
      const response = await apiService.getTopicArticles(topicName, { limit: 20 });

      if (response.success) {
        setTopicArticles(response.data.articles || []);
      }
    } catch (err) {
      console.error('Error loading topic articles:', err);
    }
  }, []);

  const loadTopicSummary = useCallback(async(topicName) => {
    try {
      const response = await apiService.getTopicSummary(topicName);

      if (response.success) {
        setTopicSummary(response.data);
      }
    } catch (err) {
      console.error('Error loading topic summary:', err);
    }
  }, []);

  const loadCategories = useCallback(async() => {
    try {
      const response = await apiService.getCategoryStats();

      if (response.success) {
        setCategories(response.data.categories || []);
      }
    } catch (err) {
      console.error('Error loading categories:', err);
    }
  }, []);

  // New enhanced data loading functions
  const loadWordCloudData = useCallback(async() => {
    try {
      const response = await fetch(`http://localhost:8001/api/v4/content-analysis/topics/word-cloud?time_period_hours=${timePeriod}&min_frequency=1`);
      if (response.ok) {
        const result = await response.json();
        setWordCloudData(result.data);
      }
    } catch (err) {
      console.error('Error loading word cloud data:', err);
    }
  }, [timePeriod]);

  const loadBigPictureData = useCallback(async() => {
    try {
      const response = await fetch(`http://localhost:8001/api/v4/content-analysis/topics/big-picture?time_period_hours=${timePeriod}`);
      if (response.ok) {
        const result = await response.json();
        setBigPictureData(result.data);
      }
    } catch (err) {
      console.error('Error loading big picture data:', err);
    }
  }, [timePeriod]);

  const loadTrendingTopics = useCallback(async() => {
    try {
      const response = await fetch(`http://localhost:8001/api/v4/content-analysis/topics/trending?time_period_hours=${timePeriod}&limit=20`);
      if (response.ok) {
        const result = await response.json();
        setTrendingTopics(result.data.trending_topics || []);
      }
    } catch (err) {
      console.error('Error loading trending topics:', err);
    }
  }, [timePeriod]);

  const handleTopicSelect = async(topic) => {
    setSelectedTopic(topic);
    await Promise.all([
      loadTopicArticles(topic.name),
      loadTopicSummary(topic.name),
    ]);
  };

  const handleClusterArticles = async() => {
    try {
      setClustering(true);
      const response = await apiService.clusterArticles({ limit: 50 });

      if (response.success) {
        await loadTopics();
        setError(null);
      } else {
        setError(response.message || 'Clustering failed');
      }
    } catch (err) {
      setError('Error clustering articles: ' + err.message);
    } finally {
      setClustering(false);
    }
  };

  const handleTransformToStoryline = async(topicName) => {
    try {
      const response = await apiService.convertTopicToStoryline(topicName);

      if (response.success) {
        setError(null);
        alert(`Successfully converted "${topicName}" to storyline: ${response.data.storyline_title}`);
      } else {
        setError(response.message || 'Conversion failed');
      }
    } catch (err) {
      setError('Error converting to storyline: ' + err.message);
    }
  };

  useEffect(() => {
    loadTopics();
    loadCategories();
    loadWordCloudData();
    loadBigPictureData();
    loadTrendingTopics();
  }, [loadTopics, loadCategories, loadWordCloudData, loadBigPictureData, loadTrendingTopics]);

  const getUrgencyColor = (urgency) => {
    switch (urgency) {
    case 'breaking': return 'error';
    case 'urgent': return 'warning';
    case 'normal': return 'default';
    case 'low': return 'info';
    default: return 'default';
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
    case 'positive': return 'success';
    case 'negative': return 'error';
    case 'neutral': return 'default';
    default: return 'default';
    }
  };

  const getCategoryColor = (category) => {
    const colors = {
      'politics': 'error',
      'economy': 'success',
      'technology': 'info',
      'environment': 'success',
      'health': 'warning',
      'international': 'secondary',
      'social': 'warning',
      'business': 'primary',
      'general': 'default',
      'semantic': 'default',
    };
    return colors[category] || 'default';
  };

  const WordCloudVisualization = ({ words }) => {
    if (!words || words.length === 0) {
      return (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Cloud sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No topics found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try triggering article clustering or expanding the time period.
          </Typography>
        </Box>
      );
    }

    return (
      <Box sx={{ p: 3, display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
        {words.map((word, index) => {
          const size = Math.max(12, Math.min(24, word.size / 3));
          const opacity = Math.max(0.6, word.relevance);

          return (
            <Chip
              key={index}
              label={word.text}
              size="small"
              color={getCategoryColor(word.category || 'general')}
              sx={{
                fontSize: `${size}px`,
                opacity: opacity,
                fontWeight: word.frequency > 5 ? 'bold' : 'normal',
                cursor: 'pointer',
                '&:hover': { transform: 'scale(1.05)' },
                transition: 'transform 0.2s',
              }}
              title={`${word.text}: ${word.frequency} articles, ${(word.relevance * 100).toFixed(1)}% relevance`}
            />
          );
        })}
      </Box>
    );
  };

  const BigPictureInsights = ({ data }) => {
    if (!data) return null;

    const { insights, topic_distribution, source_diversity } = data;

    return (
      <Box sx={{ space: 3 }}>
        {/* Key Insights */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={3}>
            <Card variant="outlined">
              <CardContent sx={{ textAlign: 'center' }}>
                <BarChart sx={{ fontSize: 32, color: 'primary.main', mb: 1 }} />
                <Typography variant="h4" color="primary" gutterBottom>
                  {insights.total_articles}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Total Articles
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant="outlined">
              <CardContent sx={{ textAlign: 'center' }}>
                <Cloud sx={{ fontSize: 32, color: 'success.main', mb: 1 }} />
                <Typography variant="h4" color="success.main" gutterBottom>
                  {insights.active_topics}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Active Topics
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant="outlined">
              <CardContent sx={{ textAlign: 'center' }}>
                <Psychology sx={{ fontSize: 32, color: 'warning.main', mb: 1 }} />
                <Typography variant="h6" color="warning.main" gutterBottom>
                  {insights.top_category}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Top Category
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant="outlined">
              <CardContent sx={{ textAlign: 'center' }}>
                <Timeline sx={{ fontSize: 32, color: 'info.main', mb: 1 }} />
                <Typography variant="h4" color="info.main" gutterBottom>
                  {insights.source_diversity}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Sources
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Topic Distribution */}
        {topic_distribution && topic_distribution.length > 0 && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <BarChart />
                Topic Distribution
              </Typography>
              <Box sx={{ space: 2 }}>
                {topic_distribution.map((topic, index) => (
                  <Box key={index} sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip label={topic.category} size="small" color={getCategoryColor(topic.category)} />
                        <Typography variant="body2" color="text.secondary">
                          {topic.article_count} articles
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        {topic.percentage}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={topic.percentage}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        )}

        {/* Source Diversity */}
        {source_diversity && source_diversity.length > 0 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Timeline />
                Source Diversity
              </Typography>
              <List dense>
                {source_diversity.slice(0, 5).map((source, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={source.source}
                      secondary={`${source.article_count} articles (${source.percentage}%)`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        )}
      </Box>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        📊 Topic Clustering & Analysis
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Discover and explore topics automatically extracted from news articles using AI-powered clustering.
        See the big picture with word clouds, trending topics, and comprehensive analysis.
      </Typography>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Search Topics"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
                placeholder="Search for topics, categories, or keywords..."
              />
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  label="Category"
                >
                  <MenuItem value="">All Categories</MenuItem>
                  {categories.map((category) => (
                    <MenuItem key={category.category} value={category.category}>
                      {category.category} ({category.article_count})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Time Period</InputLabel>
                <Select
                  value={timePeriod}
                  onChange={(e) => setTimePeriod(e.target.value)}
                  label="Time Period"
                >
                  <MenuItem value={1}>Last Hour</MenuItem>
                  <MenuItem value={24}>Last 24 Hours</MenuItem>
                  <MenuItem value={168}>Last 7 Days</MenuItem>
                  <MenuItem value={720}>Last 30 Days</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Refresh />}
                onClick={() => {
                  loadTopics();
                  loadWordCloudData();
                  loadBigPictureData();
                  loadTrendingTopics();
                }}
                disabled={loading}
              >
                Refresh
              </Button>
            </Grid>

            <Grid item xs={12} md={3}>
              <Button
                fullWidth
                variant="contained"
                startIcon={clustering ? <CircularProgress size={20} /> : <Analytics />}
                onClick={handleClusterArticles}
                disabled={clustering}
              >
                {clustering ? 'Clustering...' : 'Cluster Articles'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Enhanced Tabs Interface */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
          variant="fullWidth"
        >
          <Tab
            icon={<Cloud />}
            label="Word Cloud"
            iconPosition="start"
          />
          <Tab
            icon={<BarChart />}
            label="Big Picture"
            iconPosition="start"
          />
          <Tab
            icon={<TrendingUp />}
            label="Trending Topics"
            iconPosition="start"
          />
          <Tab
            icon={<Article />}
            label="All Topics"
            iconPosition="start"
          />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {activeTab === 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Cloud />
              Word Cloud - What's Happening
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Visual representation of topics based on article frequency. Larger words indicate more coverage.
            </Typography>
            <WordCloudVisualization words={wordCloudData?.words || []} />
          </CardContent>
        </Card>
      )}

      {activeTab === 1 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <BarChart />
              Big Picture Analysis
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              High-level overview of the current news landscape and topic distribution.
            </Typography>
            <BigPictureInsights data={bigPictureData} />
          </CardContent>
        </Card>
      )}

      {activeTab === 2 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingUp />
              Trending Topics
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Topics gaining momentum based on recent article activity and relevance.
            </Typography>
            {trendingTopics.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <TrendingUp sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No trending topics found
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Try expanding the time period or triggering clustering.
                </Typography>
              </Box>
            ) : (
              <Grid container spacing={2}>
                {trendingTopics.map((topic, index) => (
                  <Grid item xs={12} md={6} key={index}>
                    <Card variant="outlined" sx={{ height: '100%' }}>
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                          <Typography variant="h6" component="div">
                            {topic.name}
                          </Typography>
                          <Chip
                            label={topic.category}
                            size="small"
                            color={getCategoryColor(topic.category)}
                          />
                        </Box>

                        {topic.description && (
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {topic.description}
                          </Typography>
                        )}

                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Box sx={{ display: 'flex', gap: 2 }}>
                            <Typography variant="body2" color="text.secondary">
                              {topic.recent_articles} articles
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {(topic.avg_relevance * 100).toFixed(1)}% relevance
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {topic.source_diversity} sources
                            </Typography>
                          </Box>
                          <Typography variant="body2" color="primary" fontWeight="bold">
                            Score: {topic.trend_score}
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 3 && (
        <>
          {/* Loading */}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {/* Topics Grid */}
          {!loading && (
            <Grid container spacing={3}>
              {topics.map((topic) => (
                <Grid item xs={12} md={6} lg={4} key={topic.name}>
                  <Card
                    sx={{
                      height: '100%',
                      cursor: 'pointer',
                      '&:hover': { boxShadow: 3 },
                      border: selectedTopic?.name === topic.name ? '2px solid' : 'none',
                      borderColor: 'primary.main',
                    }}
                    onClick={() => handleTopicSelect(topic)}
                  >
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                        <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
                          {topic.name}
                        </Typography>
                        <Badge badgeContent={topic.article_count} color="primary">
                          <Article />
                        </Badge>
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Chip
                          label={topic.category}
                          size="small"
                          color="primary"
                          variant="outlined"
                          sx={{ mr: 1 }}
                        />
                        {topic.subcategory && (
                          <Chip
                            label={topic.subcategory}
                            size="small"
                            variant="outlined"
                          />
                        )}
                      </Box>

                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {topic.article_count} articles • {topic.avg_confidence?.toFixed(1) || '0.0'}% confidence
                      </Typography>

                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="caption" color="text.secondary">
                          Latest: {topic.latest_article ? new Date(topic.latest_article).toLocaleDateString() : 'N/A'}
                        </Typography>

                        <Box>
                          <Tooltip title="View Articles">
                            <IconButton size="small" onClick={(e) => {
                              e.stopPropagation();
                              handleTopicSelect(topic);
                            }}>
                              <Visibility />
                            </IconButton>
                          </Tooltip>

                          <Tooltip title="Transform to Storyline">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleTransformToStoryline(topic.name);
                              }}
                            >
                              <Transform />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}

      {/* Topic Details */}
      {selectedTopic && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              📈 {selectedTopic.name} - Topic Analysis
            </Typography>

            {topicSummary && (
              <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" color="primary">
                        {topicSummary.total_articles}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Articles
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" color="primary">
                        {topicSummary.unique_sources}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Unique Sources
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" color="primary">
                        {topicSummary.breaking_news}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Breaking News
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" color="primary">
                        {topicSummary.avg_confidence?.toFixed(1)}%
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Avg Confidence
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            )}

            {/* Topic Articles */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">
                  📰 Recent Articles ({topicArticles.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <List>
                  {topicArticles.map((article) => (
                    <ListItem key={article.id} divider>
                      <ListItemText
                        primary={article.title}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {article.source} • {new Date(article.created_at).toLocaleDateString()}
                            </Typography>
                            <Box sx={{ mt: 1 }}>
                              <Chip
                                label={article.sentiment}
                                size="small"
                                color={getSentimentColor(article.sentiment)}
                                sx={{ mr: 1 }}
                              />
                              <Chip
                                label={article.urgency}
                                size="small"
                                color={getUrgencyColor(article.urgency)}
                                sx={{ mr: 1 }}
                              />
                              {article.topic_confidence && (
                                <Chip
                                  label={`${(article.topic_confidence * 100).toFixed(0)}% confidence`}
                                  size="small"
                                  variant="outlined"
                                />
                              )}
                            </Box>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Button
                          size="small"
                          startIcon={<Visibility />}
                          onClick={() => window.open(article.url, '_blank')}
                        >
                          Read
                        </Button>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default Topics;
