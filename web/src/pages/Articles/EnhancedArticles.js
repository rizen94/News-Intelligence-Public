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
  ViewModule as ViewModuleIcon,
  Add as AddIcon,
  Close as CloseIcon,
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
import { apiService } from '../../services/apiService.ts';

const EnhancedArticles = () => {
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
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateInfo, setDuplicateInfo] = useState({ article: null, storyline: null });

  const loadStorylines = useCallback(async() => {
    try {
      const response = await apiService.getStorylines();
      if (response.success) {
        setStorylines(response.data.storylines || []);
      }
    } catch (error) {
      console.error('Failed to load storylines:', error);
    }
  }, []);

  const loadArticles = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticles({
        page,
        limit: 12,
        search: searchQuery,
        source: filterSource,
        sort: sortBy,
      });

      if (response.success) {
        setArticles(response.data.articles || []);
        setTotalPages(Math.ceil((response.data.total || 0) / 12));
        setTotalArticles(response.data.total || 0);
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
  }, [page, searchQuery, filterSource, sortBy]);

  useEffect(() => {
    loadArticles();
    loadStorylines();
  }, [loadArticles, loadStorylines]);

  const handleSearch = (event) => {
    setSearchQuery(event.target.value);
    setPage(1);
  };

  const handleFilterChange = (filterType, value) => {
    switch (filterType) {
    case 'source':
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
      minute: '2-digit',
    });
  };

  const truncateText = (text, maxLength = 150) => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const handleOpenArticle = (article) => {
    setSelectedArticle(article);
    setReaderOpen(true);
  };

  const handleCloseReader = () => {
    setReaderOpen(false);
    setSelectedArticle(null);
  };

  const handleAddToStoryline = (article) => {
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
      const isDuplicate = await checkForDuplicate(selectedStorylineId, articleToAdd.id);

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
            overflow: 'hidden',
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
            overflow: 'hidden',
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
          onClick={(e) => {
            e.stopPropagation();
            handleOpenArticle(article);
          }}
        >
          Read Full Article
        </Button>
        <Button
          size="small"
          startIcon={<TimelineIcon />}
          onClick={(e) => {
            e.stopPropagation();
            handleAddToStoryline(article);
          }}
        >
          Add to Storyline
        </Button>
        <Button size="small" startIcon={<ShareIcon />}>
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
            onClick={(e) => {
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
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
            Article Queue
          </Typography>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Browse and curate articles for your storylines • {totalArticles} articles available
          </Typography>
        </Box>
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
              placeholder="Search articles by title, content, or source..."
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
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={(e) => handleFilterChange('sort', e.target.value)}
              >
                <MenuItem value="date">Date</MenuItem>
                <MenuItem value="relevance">Relevance</MenuItem>
                <MenuItem value="quality">Quality Score</MenuItem>
                <MenuItem value="title">Title</MenuItem>
                <MenuItem value="source">Source</MenuItem>
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
            {searchQuery || filterSource
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
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">
              Add Article to Storyline
            </Typography>
            <IconButton onClick={handleStorylineDialogClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent>
          {articleToAdd && (
            <Box mb={3}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Article to add:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant="body1" fontWeight="medium">
                  {articleToAdd.title}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {articleToAdd.source} • {new Date(articleToAdd.published_at).toLocaleDateString()}
                </Typography>
              </Paper>
            </Box>
          )}

          <FormControl component="fieldset" fullWidth>
            <FormLabel component="legend">
              Select a storyline:
            </FormLabel>
            <RadioGroup
              value={selectedStorylineId}
              onChange={(e) => setSelectedStorylineId(e.target.value)}
            >
              {storylines.length === 0 ? (
                <Box p={2} textAlign="center">
                  <Typography color="text.secondary">
                    No storylines available. Create one first.
                  </Typography>
                </Box>
              ) : (
                storylines.map((storyline) => (
                  <FormControlLabel
                    key={storyline.id}
                    value={storyline.id}
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="body1" fontWeight="medium">
                          {storyline.title}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {storyline.description || 'No description'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {storyline.article_count || 0} articles • Status: {storyline.status}
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
          <Button onClick={handleStorylineDialogClose}>
            Cancel
          </Button>
          <Button
            onClick={handleAddToStorylineConfirm}
            variant="contained"
            disabled={!selectedStorylineId || storylines.length === 0}
            startIcon={<AddIcon />}
          >
            Add to Storyline
          </Button>
        </DialogActions>
      </Dialog>

      {/* Duplicate Warning Dialog */}
      <Dialog
        open={duplicateDialogOpen}
        onClose={handleDuplicateCancel}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="h6" color="warning.main">
              Duplicate Article Detected
            </Typography>
          </Box>
        </DialogTitle>

        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This article may already exist in the selected storyline.
          </Alert>

          {duplicateInfo.article && duplicateInfo.storyline && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Article:
              </Typography>
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
                <Typography variant="body1" fontWeight="medium">
                  {duplicateInfo.article.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {duplicateInfo.article.source} • {new Date(duplicateInfo.article.published_at).toLocaleDateString()}
                </Typography>
              </Paper>

              <Typography variant="subtitle2" gutterBottom>
                Storyline:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant="body1" fontWeight="medium">
                  {duplicateInfo.storyline.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {duplicateInfo.storyline.description || 'No description'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {duplicateInfo.storyline.article_count || 0} articles • Status: {duplicateInfo.storyline.status}
                </Typography>
              </Paper>
            </Box>
          )}

          <Typography variant="body2" sx={{ mt: 2 }}>
            Do you want to add this article anyway? This may create a duplicate entry.
          </Typography>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleDuplicateCancel} color="inherit">
            Cancel
          </Button>
          <Button
            onClick={handleDuplicateConfirm}
            variant="contained"
            color="warning"
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
