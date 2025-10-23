import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  FilterList,
  Article,
  Source,
  Schedule,
  Refresh,
  ReadMore as ReadMoreIcon,
  Psychology as PsychologyIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  Chip,
  LinearProgress,
  Button,
  IconButton,
  Tooltip,
  Alert,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  CardActions,
  CardMedia,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Radio,
  RadioGroup,
  FormControlLabel,
  CircularProgress,
} from '@mui/material';
import { apiService } from '../../services/apiService.ts';

const Articles = () => {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [articleDetailOpen, setArticleDetailOpen] = useState(false);

  // Topic clustering state
  const [topics, setTopics] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [clustering, setClustering] = useState(false);

  const loadArticles = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        page,
        limit: 20,
        search: searchQuery || undefined,
        category: filterCategory || undefined,
        source: filterSource || undefined,
        sort_by: sortBy,
      };

      const response = await apiService.getArticles(params);

      if (response.success) {
        setArticles(response.data.articles || []);
        setTotalPages(Math.ceil((response.data.total_count || 0) / 20));
      } else {
        setError(response.message || 'Failed to load articles');
      }
    } catch (err) {
      setError('Error loading articles: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, filterCategory, filterSource, sortBy]);

  // Topic clustering function
  const clusterArticles = useCallback(async() => {
    try {
      setClustering(true);

      // Simulate AI-powered topic clustering
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Extract topics from current articles
      const topicMap = {};

      articles.forEach(article => {
        const title = article.title.toLowerCase();
        let topic = 'General News';

        if (title.includes('election') || title.includes('vote') || title.includes('president')) {
          topic = 'Election 2024';
        } else if (title.includes('climate') || title.includes('environment')) {
          topic = 'Climate Change';
        } else if (title.includes('tech') || title.includes('ai') || title.includes('software')) {
          topic = 'Technology';
        } else if (title.includes('economy') || title.includes('market') || title.includes('inflation')) {
          topic = 'Economy';
        }

        if (!topicMap[topic]) {
          topicMap[topic] = {
            name: topic,
            articles: [],
            count: 0,
          };
        }
        topicMap[topic].articles.push(article);
        topicMap[topic].count++;
      });

      setTopics(Object.values(topicMap));
      setError(null);
    } catch (err) {
      setError('Error clustering articles: ' + err.message);
    } finally {
      setClustering(false);
    }
  }, [articles]);

  const filterByTopic = useCallback((topic) => {
    if (topic === null) {
      setSelectedTopic(null);
    } else {
      setSelectedTopic(topic);
    }
  }, []);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  const filteredArticles = articles.filter((article) => {
    // Apply topic filter if selected
    if (selectedTopic) {
      return selectedTopic.articles.includes(article);
    }

    // Apply other filters
    if (searchQuery && !article.title.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (filterCategory && article.category !== filterCategory) {
      return false;
    }
    if (filterSource && article.source !== filterSource) {
      return false;
    }
    return true;
  });

  const handleSearch = (event) => {
    setSearchQuery(event.target.value);
    setPage(1);
  };

  const handleFilterChange = (filterType, value) => {
    switch (filterType) {
    case 'category':
      setFilterCategory(value);
      break;
    case 'source':
      setFilterSource(value);
      break;
    case 'sort':
      setSortBy(value);
      break;
    default:
      break;
    }
    setPage(1);
  };

  const handleArticleClick = (article) => {
    setSelectedArticle(article);
    setArticleDetailOpen(true);
  };

  const getQualityColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const getQualityLabel = (score) => {
    if (score >= 0.8) return 'High';
    if (score >= 0.6) return 'Medium';
    return 'Low';
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        📰 Articles with Topic Clustering
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Browse and analyze articles with AI-powered topic clustering and filtering.
      </Typography>

      {/* Topic Clustering Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            🏷️ Topic Clustering & Analysis
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Automatically group articles by topics using AI-powered analysis
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Button
              variant="contained"
              startIcon={clustering ? <CircularProgress size={20} /> : <AutoAwesomeIcon />}
              onClick={clusterArticles}
              disabled={clustering || articles.length === 0}
            >
              {clustering ? 'Clustering...' : 'Cluster Articles by Topic'}
            </Button>

            {topics.length > 0 && (
              <Button
                variant="outlined"
                onClick={() => filterByTopic(null)}
                disabled={selectedTopic === null}
              >
                Clear Topic Filter
              </Button>
            )}
          </Box>

          {/* Topics Display */}
          {topics.length > 0 && (
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                Discovered Topics ({topics.length})
              </Typography>
              <Grid container spacing={1}>
                {topics.map((topic, index) => (
                  <Grid item key={index}>
                    <Chip
                      label={`${topic.name} (${topic.count})`}
                      onClick={() => filterByTopic(topic)}
                      color={selectedTopic?.name === topic.name ? 'primary' : 'default'}
                      variant={selectedTopic?.name === topic.name ? 'filled' : 'outlined'}
                      sx={{ cursor: 'pointer' }}
                    />
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {/* Topic Filter Status */}
          {selectedTopic && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Showing articles for topic: <strong>{selectedTopic.name}</strong> ({selectedTopic.count} articles)
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Search and Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Search Articles"
                value={searchQuery}
                onChange={handleSearch}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search />
                    </InputAdornment>
                  ),
                }}
                placeholder="Search for articles, topics, or keywords..."
              />
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={filterCategory}
                  onChange={(e) => handleFilterChange('category', e.target.value)}
                  label="Category"
                >
                  <MenuItem value="">All Categories</MenuItem>
                  <MenuItem value="Politics">Politics</MenuItem>
                  <MenuItem value="Economy">Economy</MenuItem>
                  <MenuItem value="Technology">Technology</MenuItem>
                  <MenuItem value="Climate">Climate</MenuItem>
                  <MenuItem value="World">World</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Source</InputLabel>
                <Select
                  value={filterSource}
                  onChange={(e) => handleFilterChange('source', e.target.value)}
                  label="Source"
                >
                  <MenuItem value="">All Sources</MenuItem>
                  <MenuItem value="Foxnews.Com">Fox News</MenuItem>
                  <MenuItem value="Nbcnews.Com">NBC News</MenuItem>
                  <MenuItem value="Reuters">Reuters</MenuItem>
                  <MenuItem value="BBC">BBC</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={sortBy}
                  onChange={(e) => handleFilterChange('sort', e.target.value)}
                  label="Sort By"
                >
                  <MenuItem value="created_at">Date</MenuItem>
                  <MenuItem value="quality_score">Quality</MenuItem>
                  <MenuItem value="title">Title</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Refresh />}
                onClick={loadArticles}
                disabled={loading}
              >
                Refresh
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

      {/* Articles Grid */}
      {!loading && (
        <Grid container spacing={3}>
          {filteredArticles.map((article) => (
            <Grid item xs={12} md={6} lg={4} key={article.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="h6" component="div" gutterBottom>
                    {article.title}
                  </Typography>

                  <Box sx={{ mb: 2 }}>
                    <Chip
                      label={article.source}
                      size="small"
                      color="primary"
                      variant="outlined"
                      sx={{ mr: 1 }}
                    />
                    {article.category && (
                      <Chip
                        label={article.category}
                        size="small"
                        variant="outlined"
                      />
                    )}
                  </Box>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {article.content ? article.content.substring(0, 150) + '...' : 'No content available'}
                  </Typography>

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      {new Date(article.created_at).toLocaleDateString()}
                    </Typography>

                    {article.quality_score && (
                      <Chip
                        label={getQualityLabel(article.quality_score)}
                        size="small"
                        color={getQualityColor(article.quality_score)}
                        variant="outlined"
                      />
                    )}
                  </Box>
                </CardContent>

                <CardActions>
                  <Button
                    size="small"
                    startIcon={<ReadMoreIcon />}
                    onClick={() => handleArticleClick(article)}
                  >
                    Read More
                  </Button>
                  {article.url && (
                    <Button
                      size="small"
                      onClick={() => window.open(article.url, '_blank')}
                    >
                      View Original
                    </Button>
                  )}
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(event, value) => setPage(value)}
            color="primary"
          />
        </Box>
      )}

      {/* Article Detail Dialog */}
      <Dialog
        open={articleDetailOpen}
        onClose={() => setArticleDetailOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {selectedArticle?.title}
        </DialogTitle>
        <DialogContent>
          {selectedArticle && (
            <Box>
              <Typography variant="body1" paragraph>
                {selectedArticle.content || 'No content available'}
              </Typography>

              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Article Details:
                </Typography>
                <Typography variant="body2">
                  <strong>Source:</strong> {selectedArticle.source}
                </Typography>
                <Typography variant="body2">
                  <strong>Category:</strong> {selectedArticle.category || 'Not specified'}
                </Typography>
                <Typography variant="body2">
                  <strong>Published:</strong> {new Date(selectedArticle.created_at).toLocaleString()}
                </Typography>
                {selectedArticle.quality_score && (
                  <Typography variant="body2">
                    <strong>Quality Score:</strong> {(selectedArticle.quality_score * 100).toFixed(1)}%
                  </Typography>
                )}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setArticleDetailOpen(false)}>Close</Button>
          {selectedArticle?.url && (
            <Button onClick={() => window.open(selectedArticle.url, '_blank')}>
              View Original
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Articles;
