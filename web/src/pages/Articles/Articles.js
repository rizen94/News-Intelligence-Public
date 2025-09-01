import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Pagination,
  Paper,
  InputAdornment,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Tooltip,
  Badge,
  Fab,
  SpeedDial,
  SpeedDialAction,
  SpeedDialIcon
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Sort as SortIcon,
  ViewList as ViewListIcon,
  ViewModule as ViewModuleIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  Share as ShareIcon,
  PriorityHigh as PriorityIcon,
  Tag as TagIcon,
  Timeline as TimelineIcon,
  OpenInNew as OpenInNewIcon,
  Refresh as RefreshIcon,
  Add as AddIcon
} from '@mui/icons-material';
import { useNewsSystem } from '../../contexts/NewsSystemContext';
import ArticleViewer from '../../components/ArticleViewer/ArticleViewer';

const Articles = () => {
  const { state, actions } = useNewsSystem();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [sortBy, setSortBy] = useState('published_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [itemsPerPage] = useState(12);
  const [priorityLevels, setPriorityLevels] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    fetchArticles();
    fetchPriorityLevels();
    fetchCategories();
  }, [currentPage, searchQuery, categoryFilter, priorityFilter, sortBy, sortOrder]);

  const fetchArticles = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage,
        per_page: itemsPerPage,
        search: searchQuery,
        category: categoryFilter,
        priority: priorityFilter,
        sort_by: sortBy,
        sort_order: sortOrder
      });

      const response = await fetch(`/api/articles?${params}`);
      const data = await response.json();
      
      if (data.success) {
        setArticles(data.articles || []);
        setTotalPages(Math.ceil((data.total || 0) / itemsPerPage));
      } else {
        setError(data.error || 'Failed to fetch articles');
      }
    } catch (err) {
      setError('Failed to fetch articles');
    } finally {
      setLoading(false);
    }
  };

  const fetchPriorityLevels = async () => {
    try {
      const response = await fetch('/api/prioritization/priority-levels');
      const data = await response.json();
      if (data.success) {
        setPriorityLevels(data.data);
      }
    } catch (err) {
      console.error('Failed to fetch priority levels:', err);
    }
  };

  const fetchCategories = async () => {
    try {
      // This would be a new API endpoint to get unique categories
      const response = await fetch('/api/articles/categories');
      const data = await response.json();
      if (data.success) {
        setCategories(data.categories || []);
      }
    } catch (err) {
      // Fallback to hardcoded categories for now
      setCategories(['Technology', 'Politics', 'Business', 'Science', 'Health', 'Sports', 'Entertainment']);
    }
  };

  const handleArticleClick = (article) => {
    setSelectedArticle(article);
  };

  const handleCloseViewer = () => {
    setSelectedArticle(null);
  };

  const handleArticleUpdate = () => {
    fetchArticles();
  };

  const handleSearch = (event) => {
    setSearchQuery(event.target.value);
    setCurrentPage(1);
  };

  const handleCategoryFilter = (event) => {
    setCategoryFilter(event.target.value);
    setCurrentPage(1);
  };

  const handlePriorityFilter = (event) => {
    setPriorityFilter(event.target.value);
    setCurrentPage(1);
  };

  const handleSortChange = (event) => {
    setSortBy(event.target.value);
    setCurrentPage(1);
  };

  const handleSortOrderToggle = () => {
    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    setCurrentPage(1);
  };

  const handlePageChange = (event, value) => {
    setCurrentPage(value);
    window.scrollTo(0, 0);
  };

  const getPriorityColor = (priority) => {
    const level = priorityLevels.find(p => p.name === priority);
    return level?.color_hex || '#666';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const truncateText = (text, maxLength = 150) => {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  const renderArticleCard = (article) => (
    <Card 
      key={article.id} 
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        cursor: 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: 4
        }
      }}
      onClick={() => handleArticleClick(article)}
    >
      <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Article Header */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6" gutterBottom sx={{ 
            lineHeight: 1.3,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden'
          }}>
            {article.title}
          </Typography>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            <Chip 
              label={article.source} 
              size="small" 
              variant="outlined" 
              color="primary"
            />
            {article.category && (
              <Chip 
                label={article.category} 
                size="small" 
                variant="outlined"
              />
            )}
            {article.priority_level && (
              <Chip 
                label={article.priority_level} 
                size="small" 
                style={{ backgroundColor: getPriorityColor(article.priority_level), color: 'white' }}
              />
            )}
          </Box>
        </Box>

        {/* Article Content Preview */}
        <Typography 
          variant="body2" 
          color="text.secondary" 
          sx={{ 
            flex: 1,
            display: '-webkit-box',
            WebkitLineClamp: 4,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            lineHeight: 1.5
          }}
        >
          {truncateText(article.content || article.summary || 'No content available')}
        </Typography>

        {/* Article Footer */}
        <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              {formatDate(article.published_date)}
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title="Quick Priority">
                <IconButton size="small" onClick={(e) => {
                  e.stopPropagation();
                  // Quick priority action
                }}>
                  <PriorityIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Add Tags">
                <IconButton size="small" onClick={(e) => {
                  e.stopPropagation();
                  // Quick tag action
                }}>
                  <TagIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Open Original">
                <IconButton 
                  size="small" 
                  onClick={(e) => {
                    e.stopPropagation();
                    window.open(article.url, '_blank');
                  }}
                >
                  <OpenInNewIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  const renderArticleList = (article) => (
    <Card 
      key={article.id} 
      sx={{ 
        mb: 2,
        cursor: 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          backgroundColor: 'action.hover'
        }
      }}
      onClick={() => handleArticleClick(article)}
    >
      <CardContent>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="h6" gutterBottom>
              {article.title}
            </Typography>
            <Typography 
              variant="body2" 
              color="text.secondary" 
              sx={{ 
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                mb: 1
              }}
            >
              {truncateText(article.content || article.summary || 'No content available', 200)}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip 
                label={article.source} 
                size="small" 
                variant="outlined" 
                color="primary"
              />
              {article.category && (
                <Chip 
                  label={article.category} 
                  size="small" 
                  variant="outlined"
                />
              )}
              {article.priority_level && (
                <Chip 
                  label={article.priority_level} 
                  size="small" 
                  style={{ backgroundColor: getPriorityColor(article.priority_level), color: 'white' }}
                />
              )}
            </Box>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                {formatDate(article.published_date)}
              </Typography>
              
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5, mt: 1 }}>
                <Tooltip title="Quick Priority">
                  <IconButton size="small" onClick={(e) => {
                    e.stopPropagation();
                    // Quick priority action
                  }}>
                    <PriorityIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Add Tags">
                  <IconButton size="small" onClick={(e) => {
                    e.stopPropagation();
                    // Quick tag action
                  }}>
                    <TagIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Open Original">
                  <IconButton 
                    size="small" 
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(article.url, '_blank');
                    }}
                  >
                    <OpenInNewIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );

  if (selectedArticle) {
    return (
      <ArticleViewer
        article={selectedArticle}
        onClose={handleCloseViewer}
        onUpdate={handleArticleUpdate}
      />
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Articles ({articles.length})
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Read, analyze, and manage your collected news articles
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Controls */}
      <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          {/* Search */}
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

          {/* Category Filter */}
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={categoryFilter}
                label="Category"
                onChange={handleCategoryFilter}
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

          {/* Priority Filter */}
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={priorityFilter}
                label="Priority"
                onChange={handlePriorityFilter}
              >
                <MenuItem value="">All Priorities</MenuItem>
                {priorityLevels.map((level) => (
                  <MenuItem key={level.name} value={level.name}>
                    {level.name.charAt(0).toUpperCase() + level.name.slice(1)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Sort */}
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={handleSortChange}
              >
                <MenuItem value="published_date">Date</MenuItem>
                <MenuItem value="title">Title</MenuItem>
                <MenuItem value="source">Source</MenuItem>
                <MenuItem value="priority">Priority</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {/* Sort Order */}
          <Grid item xs={12} md={1}>
            <Tooltip title={`Sort ${sortOrder === 'asc' ? 'Descending' : 'Ascending'}`}>
              <IconButton onClick={handleSortOrderToggle}>
                <SortIcon sx={{ 
                  transform: sortOrder === 'asc' ? 'rotate(180deg)' : 'none',
                  transition: 'transform 0.2s'
                }} />
              </IconButton>
            </Tooltip>
          </Grid>

          {/* View Mode */}
          <Grid item xs={12} md={1}>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title="Grid View">
                <IconButton 
                  onClick={() => setViewMode('grid')}
                  color={viewMode === 'grid' ? 'primary' : 'default'}
                >
                  <ViewModuleIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="List View">
                <IconButton 
                  onClick={() => setViewMode('list')}
                  color={viewMode === 'list' ? 'primary' : 'default'}
                >
                  <ViewListIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Content Tabs */}
      <Paper elevation={1} sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="All Articles" />
          <Tab label="High Priority" />
          <Tab label="Recent" />
          <Tab label="Bookmarked" />
        </Tabs>
      </Paper>

      {/* Articles Grid/List */}
      {loading ? (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      ) : articles.length === 0 ? (
        <Paper elevation={1} sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No articles found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your search criteria or filters
          </Typography>
        </Paper>
      ) : (
        <Box>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {articles.map((article) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={article.id}>
                  {renderArticleCard(article)}
                </Grid>
              ))}
            </Grid>
          ) : (
            <Box>
              {articles.map((article) => renderArticleList(article))}
            </Box>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Pagination
                count={totalPages}
                page={currentPage}
                onChange={handlePageChange}
                color="primary"
                size="large"
              />
            </Box>
          )}
        </Box>
      )}

      {/* Floating Action Button */}
      <Fab
        color="primary"
        aria-label="refresh"
        sx={{ position: 'fixed', bottom: 16, right: 16 }}
        onClick={fetchArticles}
      >
        <RefreshIcon />
      </Fab>
    </Box>
  );
};

export default Articles;
