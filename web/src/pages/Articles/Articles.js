import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  CircularProgress,
  Paper,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  Schedule as ScheduleIcon,
  Refresh as RefreshIcon,
  ReadMore as ReadMoreIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../../services/apiService';

const Articles = () => {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [sortBy, setSortBy] = useState('published_at');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalArticles, setTotalArticles] = useState(0);
  const [sources, setSources] = useState([]);
  const [categories, setCategories] = useState([]);
  const navigate = useNavigate();
  // const { showSuccess, showError, showLoading } = useNotifications();

  const fetchArticles = useCallback(async (isManualRefresh = false) => {
    try {
      setLoading(true);

      const params = {
        page,
        limit: 12,
        search: searchTerm,
        category: categoryFilter,
        source: sourceFilter,
        sort: sortBy,
        sort_order: 'desc'
      };

      // Add cache-busting parameter for manual refresh
      if (isManualRefresh) {
        params._t = Date.now();
      }

      const response = await apiService.getArticles(params);
      
      if (response.success) {
        setArticles(response.data?.articles || []);
        // Calculate total pages correctly
        const totalPages = Math.ceil((response.data?.total || 0) / 12);
        setTotalPages(totalPages);
        setTotalArticles(response.data?.total || 0);
      } else {
        console.error('Articles API Error:', response);
        throw new Error(response.message || 'Failed to fetch articles');
      }
    } catch (error) {
      console.error('Error fetching articles:', error);
      
      // Set empty state instead of mock data
      setArticles([]);
      setTotalPages(1);
      setTotalArticles(0);
    } finally {
      setLoading(false);
    }
  }, [page, searchTerm, categoryFilter, sourceFilter, sortBy]);

  const fetchSourcesAndCategories = useCallback(async () => {
    try {
      // Fetch sources and categories for filters
      const [sourcesResponse, categoriesResponse] = await Promise.all([
        apiService.getSources(),
        apiService.getCategories()
      ]);
      
      if (sourcesResponse.success) {
        setSources(sourcesResponse.data || []);
      }
      if (categoriesResponse.success) {
        setCategories(categoriesResponse.data || []);
      }
    } catch (error) {
      console.error('Error fetching sources and categories:', error);
      // Set default values
      setSources(['BBC News', 'Reuters', 'The Guardian', 'CNN', 'Associated Press']);
      setCategories(['Global Events', 'Business', 'Politics', 'Technology', 'Health']);
    }
  }, []);

  useEffect(() => {
    fetchSourcesAndCategories();
  }, [fetchSourcesAndCategories]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  // Auto-search when filters change
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchTerm || categoryFilter || sourceFilter) {
        setPage(1);
        fetchArticles();
      }
    }, 500); // Debounce search

    return () => clearTimeout(timeoutId);
  }, [searchTerm, categoryFilter, sourceFilter, fetchArticles]);

  const handleSearch = () => {
    setPage(1);
    fetchArticles();
  };

  const handleClearFilters = () => {
    setSearchTerm('');
    setCategoryFilter('');
    setSourceFilter('');
    setSortBy('published_at');
    setPage(1);
  };

  const handleArticleClick = (articleId) => {
    navigate(`/articles/${articleId}`);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getSentimentColor = (score) => {
    if (score > 0.1) return 'success';
    if (score < -0.1) return 'error';
    return 'default';
  };

  const getSentimentLabel = (score) => {
    if (score > 0.1) return 'Positive';
    if (score < -0.1) return 'Negative';
    return 'Neutral';
  };

  if (loading && articles.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={60} />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading articles...
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h3" component="h1" gutterBottom>
            Articles
          </Typography>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            {totalArticles} articles found
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={() => fetchArticles(true)}
          disabled={loading}
          sx={{ minWidth: 120 }}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </Button>
      </Box>

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder="Search articles..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
          </Grid>
          
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                label="Category"
              >
                <MenuItem value="">All Categories</MenuItem>
                {categories.map((category) => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                label="Source"
              >
                <MenuItem value="">All Sources</MenuItem>
                {sources.map((source) => (
                  <MenuItem key={source} value={source}>
                    {source}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                label="Sort By"
              >
                <MenuItem value="published_at">Date</MenuItem>
                <MenuItem value="quality_score">Quality</MenuItem>
                <MenuItem value="title">Title</MenuItem>
                <MenuItem value="source">Source</MenuItem>
                <MenuItem value="category">Category</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={2}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                onClick={handleSearch}
                startIcon={<SearchIcon />}
                fullWidth
              >
                Search
              </Button>
              <Button
                variant="outlined"
                onClick={handleClearFilters}
                startIcon={<FilterIcon />}
              >
                Clear
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Articles Grid */}
      <Grid container spacing={3}>
        {articles.map((article) => (
          <Grid item xs={12} md={6} lg={4} key={article.id}>
            <Card 
              sx={{ 
                height: '100%',
                cursor: 'pointer',
                '&:hover': { 
                  boxShadow: 4,
                  transform: 'translateY(-2px)',
                  transition: 'all 0.2s ease-in-out'
                },
                display: 'flex',
                flexDirection: 'column'
              }}
              onClick={() => handleArticleClick(article.id)}
            >
              <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                {/* Header */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Chip 
                    label={article.category} 
                    size="small" 
                    color="primary"
                    variant="outlined"
                  />
                  <Chip 
                    label={getSentimentLabel(article.sentiment_score)}
                    size="small"
                    color={getSentimentColor(article.sentiment_score)}
                  />
                </Box>

                {/* Title */}
                <Typography 
                  variant="h6" 
                  component="h3" 
                  gutterBottom
                  sx={{ 
                    fontWeight: 600,
                    lineHeight: 1.3,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}
                >
                  {article.title}
                </Typography>

                {/* Summary */}
                <Typography 
                  variant="body2" 
                  color="text.secondary" 
                  sx={{ 
                    mb: 2,
                    flexGrow: 1,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}
                >
                  {article.summary || article.content?.substring(0, 200) + '...'}
                </Typography>

                {/* Source and Date */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <SourceIcon sx={{ fontSize: 16, mr: 0.5, color: 'text.secondary' }} />
                    <Typography variant="caption" color="text.secondary">
                      {article.source}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <ScheduleIcon sx={{ fontSize: 16, mr: 0.5, color: 'text.secondary' }} />
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(article.published_date)}
                    </Typography>
                  </Box>
                </Box>

                {/* Quality Score */}
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                    Quality:
                  </Typography>
                  <Box sx={{ 
                    width: '100%', 
                    height: 4, 
                    backgroundColor: 'grey.300', 
                    borderRadius: 2,
                    overflow: 'hidden'
                  }}>
                    <Box sx={{ 
                      width: `${(article.quality_score || 0) * 100}%`, 
                      height: '100%', 
                      backgroundColor: article.quality_score > 0.8 ? 'success.main' : 
                                     article.quality_score > 0.6 ? 'warning.main' : 'error.main'
                    }} />
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                    {Math.round((article.quality_score || 0) * 100)}%
                  </Typography>
                </Box>

                {/* Topics */}
                {article.topics_extracted && article.topics_extracted.length > 0 && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1, mb: 2 }}>
                    {(article.topics_extracted || []).slice(0, 3).map((topic, index) => (
                      <Chip 
                        key={index}
                        label={topic} 
                        size="small" 
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    ))}
                    {article.topics_extracted.length > 3 && (
                      <Chip 
                        label={`+${article.topics_extracted.length - 3}`} 
                        size="small" 
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    )}
                  </Box>
                )}

                {/* Read Full Article Button */}
                <Button
                  variant="contained"
                  fullWidth
                  startIcon={<ReadMoreIcon />}
                  onClick={(e) => {
                    e.stopPropagation(); // Prevent card click
                    handleArticleClick(article.id);
                  }}
                  sx={{ 
                    mt: 'auto',
                    textTransform: 'none',
                    fontWeight: 500
                  }}
                >
                  Read Full Article
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(event, value) => setPage(value)}
            color="primary"
            size="large"
          />
        </Box>
      )}

      {/* No Articles */}
      {!loading && articles.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <ArticleIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No articles found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your search criteria or filters
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default Articles;
