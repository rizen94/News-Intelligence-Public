import {
  Search,
  FilterList,
  Refresh,
  Article,
  TrendingUp as TrendingUpIcon,
  Source,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Timeline as TimelineIcon,
  Visibility,
  Share as ShareIcon,
  Bookmark,
  BookmarkBorder,
  ViewList,
  ViewModule,
  Add,
  Close as CloseIcon,
  Download as DownloadIcon,
  AccessTime,
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
  FormLabel,
  Snackbar,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';

import ArticleReader from '../../components/ArticleReader';
import { apiService } from '../../services/apiService';
import { calculateReadingTime, formatReadingTime, getArticleReadingTime } from '../../utils/articleUtils';
import { useDomain } from '../../contexts/DomainContext';

const EnhancedArticles = () => {
  const { domain } = useDomain();
  // Topic clustering state
  const [topics, setTopics] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [clustering, setClustering] = useState(false);
  const [topicFilter, setTopicFilter] = useState('');
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [readerOpen, setReaderOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [viewMode, setViewMode] = useState('grid');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalArticles, setTotalArticles] = useState(0);
  const [bookmarkedArticles, setBookmarkedArticles] = useState(new Set());

  // Storyline selection dialog state
  const [storylineDialogOpen, setStorylineDialogOpen] = useState(false);
  const [storylines, setStorylines] = useState([]);
  const [selectedStorylineId, setSelectedStorylineId] = useState('');
  const [articleToAdd, setArticleToAdd] = useState(null);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success',
  });
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateInfo, setDuplicateInfo] = useState({
    article: null,
    storyline: null,
  });
  const [quickFilters, setQuickFilters] = useState({
    readingTime: null, // 'short' (< 3 min), 'medium' (3-5 min), 'long' (> 5 min)
    quality: null, // 'high' (> 0.7), 'medium' (0.5-0.7), 'low' (< 0.5)
    sentiment: null, // 'positive', 'negative', 'neutral'
  });
  const [searchSuggestions, setSearchSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const loadStorylines = useCallback(async() => {
    try {
      const response = await apiService.getStorylines({}, domain);
      if (response.success) {
        setStorylines(response.data.storylines || []);
      }
    } catch (error) {
      console.error('Failed to load storylines:', error);
    }
  }, [domain]);

  const loadArticles = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticles({
        page,
        limit: 12,
        search: searchQuery,
        source_domain: filterSource,
        sort: sortBy,
      }, domain);

      if (response.success) {
        // Handle both response structures: {data: {articles, total}} or {articles, total}
        const articlesData = response.data?.articles || response.data?.data?.articles || response.articles || [];
        const totalData = response.data?.total || response.data?.data?.total || response.total || 0;
        setArticles(articlesData);
        setTotalPages(Math.ceil(totalData / 12));
        setTotalArticles(totalData);
      } else {
        setArticles([]);
        setTotalPages(1);
        setTotalArticles(0);
      }
    } catch (err) {
      console.error('Error loading articles:', err);
      setError('Failed to load articles');
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, filterSource, sortBy, domain]);

  useEffect(() => {
    loadArticles();
    loadStorylines();
  }, [loadArticles, loadStorylines]);

  const handleSearch = event => {
    const value = event.target.value;
    setSearchQuery(value);
    setPage(1);

    // Simple autocomplete - show suggestions based on article titles
    if (value.length > 2 && articles.length > 0) {
      const suggestions = articles
        .filter(a => a.title?.toLowerCase().includes(value.toLowerCase()))
        .slice(0, 5)
        .map(a => a.title);
      setSearchSuggestions(suggestions);
      setShowSuggestions(suggestions.length > 0);
    } else {
      setSearchSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setSearchQuery(suggestion);
    setShowSuggestions(false);
    setPage(1);
  };

  const handleFilterChange = (filterType, value) => {
    switch (filterType) {
    case 'source_domain':
      setFilterSource(value);
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

  const handleQuickFilter = (filterType, value) => {
    setQuickFilters(prev => ({
      ...prev,
      [filterType]: prev[filterType] === value ? null : value,
    }));
    setPage(1);
  };

  const handleExportCSV = () => {
    try {
      // Prepare CSV data
      const headers = ['Title', 'Source', 'Published Date', 'Reading Time', 'Quality Score', 'Sentiment', 'URL'];
      const rows = articles.map(article => [
        `"${(article.title || '').replace(/"/g, '""')}"`,
        article.source_domain || '',
        article.published_at || article.created_at || '',
        formatReadingTime(getArticleReadingTime(article)),
        article.quality_score ? (article.quality_score * 100).toFixed(1) + '%' : '',
        article.sentiment || '',
        article.url || '',
      ]);

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.join(',')),
      ].join('\n');

      // Create download link
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `articles_export_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setSnackbar({
        open: true,
        message: `Exported ${articles.length} articles to CSV`,
        severity: 'success',
      });
    } catch (err) {
      console.error('Export error:', err);
      setSnackbar({
        open: true,
        message: 'Failed to export articles',
        severity: 'error',
      });
    }
  };

  // Apply quick filters to articles
  const filteredArticles = articles.filter(article => {
    if (quickFilters.readingTime) {
      const readingTime = getArticleReadingTime(article);
      if (quickFilters.readingTime === 'short' && readingTime >= 3) return false;
      if (quickFilters.readingTime === 'medium' && (readingTime < 3 || readingTime > 5)) return false;
      if (quickFilters.readingTime === 'long' && readingTime <= 5) return false;
    }
    if (quickFilters.quality && article.quality_score !== undefined) {
      if (quickFilters.quality === 'high' && article.quality_score < 0.7) return false;
      if (quickFilters.quality === 'medium' && (article.quality_score < 0.5 || article.quality_score >= 0.7)) return false;
      if (quickFilters.quality === 'low' && article.quality_score >= 0.5) return false;
    }
    if (quickFilters.sentiment && article.sentiment) {
      if (article.sentiment.toLowerCase() !== quickFilters.sentiment.toLowerCase()) return false;
    }
    return true;
  });

  const handleRefresh = () => {
    loadArticles();
  };

  const toggleBookmark = articleId => {
    const newBookmarked = new Set(bookmarkedArticles);
    if (newBookmarked.has(articleId)) {
      newBookmarked.delete(articleId);
    } else {
      newBookmarked.add(articleId);
    }
    setBookmarkedArticles(newBookmarked);
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

  const truncateText = (text, maxLength = 150) => {
    if (!text) return '';
    return text.length > maxLength
      ? text.substring(0, maxLength) + '...'
      : text;
  };

  const handleOpenArticle = article => {
    setSelectedArticle(article);
    setReaderOpen(true);
  };

  const handleCloseReader = () => {
    setReaderOpen(false);
    setSelectedArticle(null);
  };

  const handleAddToStoryline = article => {
    if (!article || !article.id) {
      setSnackbar({
        open: true,
        message: 'Invalid article data',
        severity: 'error',
      });
      return;
    }

    setArticleToAdd(article);
    setSelectedStorylineId('');
    setStorylineDialogOpen(true);
  };

  const checkForDuplicate = async(storylineId, articleId) => {
    try {
      // Check if article exists in storyline
      // For now, we'll simulate a check based on storyline article count
      const storyline = storylines.find(s => s.id === storylineId);
      if (storyline && storyline.article_count > 0) {
        // Simulate checking if article is already in storyline
        // In a real implementation, you'd call an API endpoint
        return false; // Real duplicate detection would be implemented here
      }
      return false;
    } catch (error) {
      console.error('Error checking for duplicate:', error);
      return false;
    }
  };

  const handleAddToStorylineConfirm = async() => {
    if (!articleToAdd || !selectedStorylineId) {
      setSnackbar({
        open: true,
        message: 'Please select a storyline',
        severity: 'error',
      });
      return;
    }

    try {
      // Check for duplicate
      const isDuplicate = await checkForDuplicate(
        selectedStorylineId,
        articleToAdd.id,
      );

      if (isDuplicate) {
        const storyline = storylines.find(s => s.id === selectedStorylineId);
        setDuplicateInfo({ article: articleToAdd, storyline });
        setDuplicateDialogOpen(true);
        return;
      }

      // Add article to storyline
      const storyline = storylines.find(s => s.id === selectedStorylineId);
      setSnackbar({
        open: true,
        message: `Article "${articleToAdd.title}" added to storyline "${storyline.title}"`,
        severity: 'success',
      });

      // Add article to storyline
      // const response = await apiService.addArticleToStoryline(selectedStorylineId, articleToAdd.id);

      setStorylineDialogOpen(false);
      setArticleToAdd(null);
      setSelectedStorylineId('');
    } catch (error) {
      console.error('Failed to add article to storyline:', error);
      setSnackbar({
        open: true,
        message: 'Failed to add article to storyline',
        severity: 'error',
      });
    }
  };

  const handleDuplicateConfirm = async() => {
    // User confirmed they want to add the duplicate
    const storyline = duplicateInfo.storyline;
    const article = duplicateInfo.article;

    setSnackbar({
      open: true,
      message: `Article "${article.title}" added to storyline "${storyline.title}" (duplicate allowed)`,
      severity: 'warning',
    });

    // Add article to storyline
    // const response = await apiService.addArticleToStoryline(storyline.id, article.id);

    setDuplicateDialogOpen(false);
    setStorylineDialogOpen(false);
    setArticleToAdd(null);
    setSelectedStorylineId('');
    setDuplicateInfo({ article: null, storyline: null });
  };

  const handleDuplicateCancel = () => {
    setDuplicateDialogOpen(false);
    setDuplicateInfo({ article: null, storyline: null });
  };

  const handleStorylineDialogClose = () => {
    setStorylineDialogOpen(false);
    setArticleToAdd(null);
    setSelectedStorylineId('');
  };

  const ArticleCard = ({ article }) => (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: 'pointer',
        '&:hover': {
          boxShadow: 4,
          transform: 'translateY(-2px)',
          transition: 'all 0.2s ease-in-out',
        },
      }}
      onClick={() => handleOpenArticle(article)}
    >
      {article.image_url && (
        <CardMedia
          component='img'
          height='200'
          image={article.image_url}
          alt={article.title}
          sx={{ objectFit: 'cover' }}
        />
      )}
      <CardContent sx={{ flexGrow: 1 }}>
        <Box
          display='flex'
          justifyContent='space-between'
          alignItems='flex-start'
          mb={2}
        >
          <Typography
            variant='h6'
            component='h3'
            sx={{
              fontWeight: 'bold',
              lineHeight: 1.2,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {article.title || 'Untitled Article'}
          </Typography>
          <IconButton
            size='small'
            onClick={() => toggleBookmark(article.id)}
            sx={{ ml: 1 }}
          >
            {bookmarkedArticles.has(article.id) ? (
              <Bookmark color='primary' />
            ) : (
              <BookmarkBorder />
            )}
          </IconButton>
        </Box>

        <Typography
          variant='body2'
          color='text.secondary'
          sx={{
            mb: 2,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {truncateText(article.summary || article.content)}
        </Typography>

        <Box display='flex' flexWrap='wrap' gap={1} mb={2}>
          {article.sentiment && (
            <Chip
              label={article.sentiment}
              color={getSentimentColor(article.sentiment)}
              size='small'
            />
          )}
          {article.quality_score && (
            <Chip
              label={`Quality: ${Math.round(article.quality_score * 100)}%`}
              color='primary'
              size='small'
            />
          )}
          {article.category && (
            <Chip label={article.category} color='secondary' size='small' />
          )}
        </Box>

        <Box
          display='flex'
          alignItems='center'
          justifyContent='space-between'
          mb={1}
        >
          <Box display='flex' alignItems='center' gap={1}>
            <Source fontSize='small' color='action' />
            <Typography variant='caption' color='text.secondary'>
              {article.source_domain || 'Unknown Source'}
            </Typography>
          </Box>
          <Box display='flex' alignItems='center' gap={1.5}>
            {(() => {
              const readingTime = getArticleReadingTime(article);
              return readingTime > 0 ? (
                <Box display='flex' alignItems='center' gap={0.5}>
                  <AccessTime fontSize='inherit' sx={{ fontSize: '0.875rem' }} />
                  <Typography variant='caption' color='text.secondary'>
                    {formatReadingTime(readingTime)}
                  </Typography>
                </Box>
              ) : null;
            })()}
            <Typography variant='caption' color='text.secondary'>
              {formatDate(article.published_at || article.created_at)}
            </Typography>
          </Box>
        </Box>

        {article.entities && article.entities.length > 0 && (
          <Box mt={1}>
            <Typography
              variant='caption'
              color='text.secondary'
              display='block'
            >
              Key Entities: {article.entities.slice(0, 3).join(', ')}
              {article.entities.length > 3 &&
                ` +${article.entities.length - 3} more`}
            </Typography>
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button
          size='small'
          startIcon={<Visibility />}
          onClick={e => {
            e.stopPropagation();
            handleOpenArticle(article);
          }}
        >
          Read Full Article
        </Button>
        <Button
          size='small'
          startIcon={<TimelineIcon />}
          onClick={e => {
            e.stopPropagation();
            handleAddToStoryline(article);
          }}
        >
          Add to Storyline
        </Button>
        <Button size='small' startIcon={<ShareIcon />}>
          Share
        </Button>
      </CardActions>
    </Card>
  );

  const ArticleListItem = ({ article }) => (
    <ListItem
      onClick={() => handleOpenArticle(article)}
      sx={{
        border: 1,
        cursor: 'pointer',
        '&:hover': {
          backgroundColor: 'action.hover',
          boxShadow: 1,
        },
        borderColor: 'divider',
        borderRadius: 1,
        mb: 1,
        bgcolor: 'background.paper',
      }}
    >
      <ListItemText
        primary={
          <Box display='flex' alignItems='center' gap={1} mb={1}>
            <Typography variant='h6' sx={{ flexGrow: 1 }}>
              {article.title || 'Untitled Article'}
            </Typography>
            <Box display='flex' gap={1}>
              {article.sentiment && (
                <Chip
                  label={article.sentiment}
                  color={getSentimentColor(article.sentiment)}
                  size='small'
                />
              )}
              {article.quality_score && (
                <Chip
                  label={`${Math.round(article.quality_score * 100)}%`}
                  color='primary'
                  size='small'
                />
              )}
            </Box>
          </Box>
        }
        secondary={
          <Box>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
              {truncateText(article.summary || article.content, 200)}
            </Typography>
            <Box display='flex' alignItems='center' gap={2}>
              <Box display='flex' alignItems='center' gap={0.5}>
                <Source fontSize='small' />
                <Typography variant='caption'>
                  {article.source_domain || 'Unknown Source'}
                </Typography>
              </Box>
              {(() => {
                const readingTime = getArticleReadingTime(article);
                return readingTime > 0 ? (
                  <Box display='flex' alignItems='center' gap={0.5}>
                    <AccessTime fontSize='inherit' sx={{ fontSize: '0.75rem' }} />
                    <Typography variant='caption' color='text.secondary'>
                      {formatReadingTime(readingTime)}
                    </Typography>
                  </Box>
                ) : null;
              })()}
              <Typography variant='caption'>
                {formatDate(article.published_at || article.created_at)}
              </Typography>
              {article.entities && article.entities.length > 0 && (
                <Typography variant='caption' color='text.secondary'>
                  Entities: {article.entities.slice(0, 3).join(', ')}
                </Typography>
              )}
            </Box>
          </Box>
        }
      />
      <ListItemSecondaryAction>
        <Box display='flex' gap={1}>
          <IconButton size='small' onClick={() => toggleBookmark(article.id)}>
            {bookmarkedArticles.has(article.id) ? (
              <Bookmark color='primary' />
            ) : (
              <BookmarkBorder />
            )}
          </IconButton>
          <Button
            size='small'
            startIcon={<Visibility />}
            onClick={e => {
              e.stopPropagation();
              handleOpenArticle(article);
            }}
          >
            View
          </Button>
        </Box>
      </ListItemSecondaryAction>
    </ListItem>
  );

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Box>
          <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
            Article Queue
          </Typography>
          <Typography variant='h6' color='text.secondary' gutterBottom>
            Browse and curate articles for your storylines • {totalArticles}{' '}
            articles available
          </Typography>
        </Box>
        <Box display='flex' gap={2} alignItems='center'>
          <Tooltip title='Refresh Articles'>
            <IconButton onClick={handleRefresh} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button
            variant={viewMode === 'grid' ? 'contained' : 'outlined'}
            startIcon={<ViewModule />}
            onClick={() => setViewMode('grid')}
            size='small'
          >
            Grid
          </Button>
          <Button
            variant={viewMode === 'list' ? 'contained' : 'outlined'}
            startIcon={<ViewList />}
            onClick={() => setViewMode('list')}
            size='small'
          >
            List
          </Button>
        </Box>
      </Box>

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems='center'>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder='Search articles by title, content, or source_domain...'
              value={searchQuery}
              onChange={handleSearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position='start'>
                    <Search />
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
                label='Source'
                onChange={e =>
                  handleFilterChange('source_domain', e.target.value)
                }
              >
                <MenuItem value=''>All Sources</MenuItem>
                <MenuItem value='bbc'>BBC</MenuItem>
                <MenuItem value='cnn'>CNN</MenuItem>
                <MenuItem value='reuters'>Reuters</MenuItem>
                <MenuItem value='ap'>Associated Press</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label='Sort By'
                onChange={e => handleFilterChange('sort', e.target.value)}
              >
                <MenuItem value='date'>Date</MenuItem>
                <MenuItem value='relevance'>Relevance</MenuItem>
                <MenuItem value='quality'>Quality Score</MenuItem>
                <MenuItem value='title'>Title</MenuItem>
                <MenuItem value='source_domain'>Source</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant='outlined'
              startIcon={<FilterList />}
              onClick={() => {
                setSearchQuery('');
                setFilterSource('');
                setSortBy('date');
                setQuickFilters({ readingTime: null, quality: null, sentiment: null });
                setPage(1);
              }}
            >
              Clear Filters
            </Button>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant='contained'
              startIcon={<DownloadIcon />}
              onClick={handleExportCSV}
              disabled={articles.length === 0}
            >
              Export CSV
            </Button>
          </Grid>
        </Grid>

        {/* Quick Filter Chips */}
        <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <Typography variant='body2' sx={{ mr: 1, alignSelf: 'center' }}>
            Quick Filters:
          </Typography>

          {/* Reading Time Filters */}
          <Chip
            label='Short Read (< 3 min)'
            onClick={() => handleQuickFilter('readingTime', 'short')}
            color={quickFilters.readingTime === 'short' ? 'primary' : 'default'}
            variant={quickFilters.readingTime === 'short' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Medium Read (3-5 min)'
            onClick={() => handleQuickFilter('readingTime', 'medium')}
            color={quickFilters.readingTime === 'medium' ? 'primary' : 'default'}
            variant={quickFilters.readingTime === 'medium' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Long Read (> 5 min)'
            onClick={() => handleQuickFilter('readingTime', 'long')}
            color={quickFilters.readingTime === 'long' ? 'primary' : 'default'}
            variant={quickFilters.readingTime === 'long' ? 'filled' : 'outlined'}
            size='small'
          />

          {/* Quality Filters */}
          <Chip
            label='High Quality (> 70%)'
            onClick={() => handleQuickFilter('quality', 'high')}
            color={quickFilters.quality === 'high' ? 'primary' : 'default'}
            variant={quickFilters.quality === 'high' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Medium Quality (50-70%)'
            onClick={() => handleQuickFilter('quality', 'medium')}
            color={quickFilters.quality === 'medium' ? 'primary' : 'default'}
            variant={quickFilters.quality === 'medium' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Low Quality (< 50%)'
            onClick={() => handleQuickFilter('quality', 'low')}
            color={quickFilters.quality === 'low' ? 'primary' : 'default'}
            variant={quickFilters.quality === 'low' ? 'filled' : 'outlined'}
            size='small'
          />

          {/* Sentiment Filters */}
          <Chip
            label='Positive'
            onClick={() => handleQuickFilter('sentiment', 'positive')}
            color={quickFilters.sentiment === 'positive' ? 'success' : 'default'}
            variant={quickFilters.sentiment === 'positive' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Neutral'
            onClick={() => handleQuickFilter('sentiment', 'neutral')}
            color={quickFilters.sentiment === 'neutral' ? 'default' : 'default'}
            variant={quickFilters.sentiment === 'neutral' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Negative'
            onClick={() => handleQuickFilter('sentiment', 'negative')}
            color={quickFilters.sentiment === 'negative' ? 'error' : 'default'}
            variant={quickFilters.sentiment === 'negative' ? 'filled' : 'outlined'}
            size='small'
          />
        </Box>
      </Paper>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Articles Display */}
      {articles.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Article sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant='h6' color='text.secondary' gutterBottom>
            No articles found
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            {searchQuery || filterSource
              ? 'Try adjusting your search criteria or filters'
              : 'Articles will appear here once the system starts collecting data'}
          </Typography>
        </Paper>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {filteredArticles.map(article => (
                <Grid item xs={12} sm={6} md={4} key={article.id}>
                  <ArticleCard article={article} />
                </Grid>
              ))}
            </Grid>
          ) : (
            <List>
              {filteredArticles.map(article => (
                <ArticleListItem key={article.id} article={article} />
              ))}
            </List>
          )}

          {filteredArticles.length === 0 && articles.length > 0 && (
            <Alert severity='info' sx={{ mt: 2 }}>
              No articles match the selected quick filters. Try adjusting your filters.
            </Alert>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Box display='flex' justifyContent='center' mt={4}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(event, value) => setPage(value)}
                color='primary'
                size='large'
              />
            </Box>
          )}
        </>
      )}

      {/* AI Analysis Features */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant='h6' gutterBottom>
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          AI-Powered Analysis
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <AutoAwesomeIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Sentiment Analysis</Typography>
              <Typography variant='body2' color='text.secondary'>
                Automatic sentiment classification for each article
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <TimelineIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Entity Extraction</Typography>
              <Typography variant='body2' color='text.secondary'>
                Identify key people, places, and organizations
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <TrendingUpIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Quality Scoring</Typography>
              <Typography variant='body2' color='text.secondary'>
                AI-powered quality assessment and ranking
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Article Reader Dialog */}
      <ArticleReader
        article={selectedArticle}
        open={readerOpen}
        onClose={handleCloseReader}
        onAddToStoryline={handleAddToStoryline}
      />

      {/* Storyline Selection Dialog */}
      <Dialog
        open={storylineDialogOpen}
        onClose={handleStorylineDialogClose}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>
          <Box
            display='flex'
            alignItems='center'
            justifyContent='space-between'
          >
            <Typography variant='h6'>Add Article to Storyline</Typography>
            <IconButton onClick={handleStorylineDialogClose} size='small'>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent>
          {articleToAdd && (
            <Box mb={3}>
              <Typography
                variant='subtitle2'
                color='text.secondary'
                gutterBottom
              >
                Article to add:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant='body1' fontWeight='medium'>
                  {articleToAdd.title}
                </Typography>
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 1 }}
                >
                  {articleToAdd.source_domain} •{' '}
                  {new Date(articleToAdd.published_at).toLocaleDateString()}
                </Typography>
              </Paper>
            </Box>
          )}

          <FormControl component='fieldset' fullWidth>
            <FormLabel component='legend'>Select a storyline:</FormLabel>
            <RadioGroup
              value={selectedStorylineId}
              onChange={e => setSelectedStorylineId(e.target.value)}
            >
              {storylines.length === 0 ? (
                <Box p={2} textAlign='center'>
                  <Typography color='text.secondary'>
                    No storylines available. Create one first.
                  </Typography>
                </Box>
              ) : (
                storylines.map(storyline => (
                  <FormControlLabel
                    key={storyline.id}
                    value={storyline.id}
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant='body1' fontWeight='medium'>
                          {storyline.title}
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          {storyline.description || 'No description'}
                        </Typography>
                        <Typography variant='caption' color='text.secondary'>
                          {storyline.article_count || 0} articles • Status:{' '}
                          {storyline.status}
                        </Typography>
                      </Box>
                    }
                  />
                ))
              )}
            </RadioGroup>
          </FormControl>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleStorylineDialogClose}>Cancel</Button>
          <Button
            onClick={handleAddToStorylineConfirm}
            variant='contained'
            disabled={!selectedStorylineId || storylines.length === 0}
            startIcon={<Add />}
          >
            Add to Storyline
          </Button>
        </DialogActions>
      </Dialog>

      {/* Duplicate Warning Dialog */}
      <Dialog
        open={duplicateDialogOpen}
        onClose={handleDuplicateCancel}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>
          <Box display='flex' alignItems='center' gap={1}>
            <Typography variant='h6' color='warning.main'>
              Duplicate Article Detected
            </Typography>
          </Box>
        </DialogTitle>

        <DialogContent>
          <Alert severity='warning' sx={{ mb: 2 }}>
            This article may already exist in the selected storyline.
          </Alert>

          {duplicateInfo.article && duplicateInfo.storyline && (
            <Box>
              <Typography variant='subtitle2' gutterBottom>
                Article:
              </Typography>
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
                <Typography variant='body1' fontWeight='medium'>
                  {duplicateInfo.article.title}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  {duplicateInfo.article.source_domain} •{' '}
                  {new Date(
                    duplicateInfo.article.published_at,
                  ).toLocaleDateString()}
                </Typography>
              </Paper>

              <Typography variant='subtitle2' gutterBottom>
                Storyline:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant='body1' fontWeight='medium'>
                  {duplicateInfo.storyline.title}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  {duplicateInfo.storyline.description || 'No description'}
                </Typography>
                <Typography variant='caption' color='text.secondary'>
                  {duplicateInfo.storyline.article_count || 0} articles •
                  Status: {duplicateInfo.storyline.status}
                </Typography>
              </Paper>
            </Box>
          )}

          <Typography variant='body2' sx={{ mt: 2 }}>
            Do you want to add this article anyway? This may create a duplicate
            entry.
          </Typography>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleDuplicateCancel} color='inherit'>
            Cancel
          </Button>
          <Button
            onClick={handleDuplicateConfirm}
            variant='contained'
            color='warning'
          >
            Add Anyway
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EnhancedArticles;
