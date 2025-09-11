import React, { useState, useEffect, useCallback } from 'react';
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
  CardMedia
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  Article as ArticleIcon,
  TrendingUp as TrendingUpIcon,
  Source as SourceIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Timeline as TimelineIcon,
  Visibility as VisibilityIcon,
  Share as ShareIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  ViewList as ViewListIcon,
  ViewModule as ViewModuleIcon
} from '@mui/icons-material';
import { apiService } from '../../services/apiService';

const EnhancedArticles = () => {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [filterSentiment, setFilterSentiment] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [viewMode, setViewMode] = useState('grid');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [bookmarkedArticles, setBookmarkedArticles] = useState(new Set());

  const loadArticles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticles({
        page,
        limit: 12,
        search: searchQuery,
        source: filterSource,
        sentiment: filterSentiment,
        sort: sortBy
      });
      
      if (response.success) {
        setArticles(response.data.articles || []);
        setTotalPages(Math.ceil((response.data.total || 0) / 12));
      } else {
        setArticles([]);
        setTotalPages(1);
      }
    } catch (err) {
      console.error('Error loading articles:', err);
      setError('Failed to load articles');
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, filterSource, filterSentiment, sortBy]);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  const handleSearch = (event) => {
    setSearchQuery(event.target.value);
    setPage(1);
  };

  const handleFilterChange = (filterType, value) => {
    switch (filterType) {
      case 'source':
        setFilterSource(value);
        break;
      case 'sentiment':
        setFilterSentiment(value);
        break;
      case 'sort':
        setSortBy(value);
        break;
      default:
        console.warn('Unknown filter type:', filterType);
        break;
    }
    setPage(1);
  };

  const handleRefresh = () => {
    loadArticles();
  };

  const toggleBookmark = (articleId) => {
    const newBookmarked = new Set(bookmarkedArticles);
    if (newBookmarked.has(articleId)) {
      newBookmarked.delete(articleId);
    } else {
      newBookmarked.add(articleId);
    }
    setBookmarkedArticles(newBookmarked);
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive': return 'success';
      case 'negative': return 'error';
      case 'neutral': return 'default';
      default: return 'default';
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const truncateText = (text, maxLength = 150) => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const ArticleCard = ({ article }) => (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {article.image_url && (
        <CardMedia
          component="img"
          height="200"
          image={article.image_url}
          alt={article.title}
          sx={{ objectFit: 'cover' }}
        />
      )}
      <CardContent sx={{ flexGrow: 1 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Typography variant="h6" component="h3" sx={{ 
            fontWeight: 'bold',
            lineHeight: 1.2,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden'
          }}>
            {article.title || 'Untitled Article'}
          </Typography>
          <IconButton 
            size="small" 
            onClick={() => toggleBookmark(article.id)}
            sx={{ ml: 1 }}
          >
            {bookmarkedArticles.has(article.id) ? 
              <BookmarkIcon color="primary" /> : 
              <BookmarkBorderIcon />
            }
          </IconButton>
        </Box>

        <Typography 
          variant="body2" 
          color="text.secondary" 
          sx={{ 
            mb: 2,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden'
          }}
        >
          {truncateText(article.summary || article.content)}
        </Typography>

        <Box display="flex" flexWrap="wrap" gap={1} mb={2}>
          {article.sentiment && (
            <Chip
              label={article.sentiment}
              color={getSentimentColor(article.sentiment)}
              size="small"
            />
          )}
          {article.quality_score && (
            <Chip
              label={`Quality: ${Math.round(article.quality_score * 100)}%`}
              color="primary"
              size="small"
            />
          )}
          {article.category && (
            <Chip
              label={article.category}
              color="secondary"
              size="small"
            />
          )}
        </Box>

        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Box display="flex" alignItems="center" gap={1}>
            <SourceIcon fontSize="small" color="action" />
            <Typography variant="caption" color="text.secondary">
              {article.source || 'Unknown Source'}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            {formatDate(article.published_at || article.created_at)}
          </Typography>
        </Box>

        {article.entities && article.entities.length > 0 && (
          <Box mt={1}>
            <Typography variant="caption" color="text.secondary" display="block">
              Key Entities: {article.entities.slice(0, 3).join(', ')}
              {article.entities.length > 3 && ` +${article.entities.length - 3} more`}
            </Typography>
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button 
          size="small" 
          startIcon={<VisibilityIcon />}
          onClick={() => window.open(article.url, '_blank')}
        >
          Read Full Article
        </Button>
        <Button size="small" startIcon={<ShareIcon />}>
          Share
        </Button>
        <Button size="small" startIcon={<TimelineIcon />}>
          View in Storyline
        </Button>
      </CardActions>
    </Card>
  );

  const ArticleListItem = ({ article }) => (
    <ListItem
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        mb: 1,
        bgcolor: 'background.paper'
      }}
    >
      <ListItemText
        primary={
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              {article.title || 'Untitled Article'}
            </Typography>
            <Box display="flex" gap={1}>
              {article.sentiment && (
                <Chip
                  label={article.sentiment}
                  color={getSentimentColor(article.sentiment)}
                  size="small"
                />
              )}
              {article.quality_score && (
                <Chip
                  label={`${Math.round(article.quality_score * 100)}%`}
                  color="primary"
                  size="small"
                />
              )}
            </Box>
          </Box>
        }
        secondary={
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {truncateText(article.summary || article.content, 200)}
            </Typography>
            <Box display="flex" alignItems="center" gap={2}>
              <Box display="flex" alignItems="center" gap={0.5}>
                <SourceIcon fontSize="small" />
                <Typography variant="caption">
                  {article.source || 'Unknown Source'}
                </Typography>
              </Box>
              <Typography variant="caption">
                {formatDate(article.published_at || article.created_at)}
              </Typography>
              {article.entities && article.entities.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  Entities: {article.entities.slice(0, 3).join(', ')}
                </Typography>
              )}
            </Box>
          </Box>
        }
      />
      <ListItemSecondaryAction>
        <Box display="flex" gap={1}>
          <IconButton 
            size="small" 
            onClick={() => toggleBookmark(article.id)}
          >
            {bookmarkedArticles.has(article.id) ? 
              <BookmarkIcon color="primary" /> : 
              <BookmarkBorderIcon />
            }
          </IconButton>
          <Button 
            size="small" 
            startIcon={<VisibilityIcon />}
            onClick={() => window.open(article.url, '_blank')}
          >
            View
          </Button>
        </Box>
      </ListItemSecondaryAction>
    </ListItem>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          Articles
        </Typography>
        <Box display="flex" gap={2} alignItems="center">
          <Tooltip title="Refresh Articles">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant={viewMode === 'grid' ? 'contained' : 'outlined'}
            startIcon={<ViewModuleIcon />}
            onClick={() => setViewMode('grid')}
            size="small"
          >
            Grid
          </Button>
          <Button
            variant={viewMode === 'list' ? 'contained' : 'outlined'}
            startIcon={<ViewListIcon />}
            onClick={() => setViewMode('list')}
            size="small"
          >
            List
          </Button>
        </Box>
      </Box>

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder="Search articles..."
              value={searchQuery}
              onChange={handleSearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={filterSource}
                label="Source"
                onChange={(e) => handleFilterChange('source', e.target.value)}
              >
                <MenuItem value="">All Sources</MenuItem>
                <MenuItem value="bbc">BBC</MenuItem>
                <MenuItem value="cnn">CNN</MenuItem>
                <MenuItem value="reuters">Reuters</MenuItem>
                <MenuItem value="ap">Associated Press</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sentiment</InputLabel>
              <Select
                value={filterSentiment}
                label="Sentiment"
                onChange={(e) => handleFilterChange('sentiment', e.target.value)}
              >
                <MenuItem value="">All Sentiments</MenuItem>
                <MenuItem value="positive">Positive</MenuItem>
                <MenuItem value="negative">Negative</MenuItem>
                <MenuItem value="neutral">Neutral</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={(e) => handleFilterChange('sort', e.target.value)}
              >
                <MenuItem value="date">Date</MenuItem>
                <MenuItem value="relevance">Relevance</MenuItem>
                <MenuItem value="quality">Quality Score</MenuItem>
                <MenuItem value="sentiment">Sentiment</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<FilterIcon />}
              onClick={() => {
                setSearchQuery('');
                setFilterSource('');
                setFilterSentiment('');
                setSortBy('date');
                setPage(1);
              }}
            >
              Clear Filters
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Articles Display */}
      {articles.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <ArticleIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No articles found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {searchQuery || filterSource || filterSentiment 
              ? 'Try adjusting your search criteria or filters'
              : 'Articles will appear here once the system starts collecting data'
            }
          </Typography>
        </Paper>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {articles.map((article) => (
                <Grid item xs={12} sm={6} md={4} key={article.id}>
                  <ArticleCard article={article} />
                </Grid>
              ))}
            </Grid>
          ) : (
            <List>
              {articles.map((article) => (
                <ArticleListItem key={article.id} article={article} />
              ))}
            </List>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Box display="flex" justifyContent="center" mt={4}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(event, value) => setPage(value)}
                color="primary"
                size="large"
              />
            </Box>
          )}
        </>
      )}

      {/* AI Analysis Features */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          AI-Powered Analysis
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Box textAlign="center">
              <AutoAwesomeIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Sentiment Analysis</Typography>
              <Typography variant="body2" color="text.secondary">
                Automatic sentiment classification for each article
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign="center">
              <TimelineIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Entity Extraction</Typography>
              <Typography variant="body2" color="text.secondary">
                Identify key people, places, and organizations
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign="center">
              <TrendingUpIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Quality Scoring</Typography>
              <Typography variant="body2" color="text.secondary">
                AI-powered quality assessment and ranking
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default EnhancedArticles;