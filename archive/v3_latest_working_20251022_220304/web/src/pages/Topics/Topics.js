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
} from '@mui/material';
import {
  TrendingUpIcon,
  Article,
  Search,
  Refresh,
  Transform,
  Analytics,
  ExpandMore,
  Visibility,
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
  }, [loadTopics, loadCategories]);

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

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        📊 Topic Clustering & Analysis
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Discover and explore topics automatically extracted from news articles using AI-powered clustering.
      </Typography>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
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

            <Grid item xs={12} md={3}>
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

            <Grid item xs={12} md={3}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Refresh />}
                onClick={loadTopics}
                disabled={loading}
              >
                Refresh
              </Button>
            </Grid>

            <Grid item xs={12} md={2}>
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
                    {topic.article_count} articles • {topic.avg_confidence.toFixed(1)}% confidence
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
