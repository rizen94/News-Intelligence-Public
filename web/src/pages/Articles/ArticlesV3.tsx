/**
 * Articles Page v3.0 for News Intelligence System
 * Refactored to use new architecture with centralized state management
 */

import React, { useState, useMemo } from 'react';
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
  Alert,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  Schedule as ScheduleIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../components/Notifications/NotificationSystem';
import { useArticles, useArticleSources, useArticleCategories } from '@/hooks';
import { ArticleSearchParams, SortField, SortOrder } from '../../types/articles';
import ErrorBoundary from '../components/ErrorBoundary/ErrorBoundary';

const ArticlesV3: React.FC = () => {
  const navigate = useNavigate();
  const { showSuccess, showError, showLoading } = useNotifications();
  
  // Search and filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortField>(SortField.CREATED_AT);
  const [sortOrder, setSortOrder] = useState<SortOrder>(SortOrder.DESC);

  // Build search parameters
  const searchParams: ArticleSearchParams = useMemo(() => ({
    page: 1,
    per_page: 12,
    search: searchTerm || undefined,
    category: categoryFilter || undefined,
    source: sourceFilter || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  }), [searchTerm, categoryFilter, sourceFilter, sortBy, sortOrder]);

  // Use custom hooks
  const { data: articles, loading, error, refetch, pagination } = useArticles(searchParams);
  const { data: sources, loading: loadingSources } = useArticleSources();
  const { data: categories, loading: loadingCategories } = useArticleCategories();

  // Handle search
  const handleSearch = () => {
    refetch();
  };

  // Handle filter changes
  const handleFilterChange = (filterType: string, value: string) => {
    switch (filterType) {
      case 'category':
        setCategoryFilter(value);
        break;
      case 'source':
        setSourceFilter(value);
        break;
      case 'sortBy':
        setSortBy(value as SortField);
        break;
      case 'sortOrder':
        setSortOrder(value as SortOrder);
        break;
    }
    refetch();
  };

  // Handle clear filters
  const handleClearFilters = () => {
    setSearchTerm('');
    setCategoryFilter('');
    setSourceFilter('');
    setSortBy(SortField.CREATED_AT);
    setSortOrder(SortOrder.DESC);
    refetch();
  };

  // Handle article click
  const handleArticleClick = (articleId: number) => {
    navigate(`/articles/${articleId}`);
  };

  // Handle refresh
  const handleRefresh = () => {
    showLoading('Refreshing articles...');
    refetch();
    showSuccess('Articles refreshed successfully');
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processed': return 'success';
      case 'processing': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="contained" onClick={handleRefresh}>
          Try Again
        </Button>
      </Box>
    );
  }

  return (
    <ErrorBoundary>
      <Box sx={{ p: 3 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h3" component="h1" gutterBottom>
              Articles
            </Typography>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {pagination.total} articles found
            </Typography>
          </Box>
          <Button
            variant="outlined"
            startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
            onClick={handleRefresh}
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
                  onChange={(e) => handleFilterChange('category', e.target.value)}
                  label="Category"
                  disabled={loadingCategories}
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
                  onChange={(e) => handleFilterChange('source', e.target.value)}
                  label="Source"
                  disabled={loadingSources}
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
                  onChange={(e) => handleFilterChange('sortBy', e.target.value)}
                  label="Sort By"
                >
                  <MenuItem value={SortField.CREATED_AT}>Date</MenuItem>
                  <MenuItem value={SortField.TITLE}>Title</MenuItem>
                  <MenuItem value={SortField.SOURCE}>Source</MenuItem>
                  <MenuItem value={SortField.SENTIMENT}>Sentiment</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={2}>
              <Button
                variant="contained"
                onClick={handleSearch}
                disabled={loading}
                startIcon={<SearchIcon />}
                fullWidth
              >
                Search
              </Button>
            </Grid>
          </Grid>
          
          <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button
              variant="outlined"
              size="small"
              onClick={handleClearFilters}
              startIcon={<FilterIcon />}
            >
              Clear Filters
            </Button>
          </Box>
        </Paper>

        {/* Articles Grid */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Grid container spacing={3}>
            {articles.map((article) => (
              <Grid item xs={12} sm={6} md={4} key={article.id}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    cursor: 'pointer',
                    '&:hover': {
                      boxShadow: 4,
                    },
                  }}
                  onClick={() => handleArticleClick(article.id)}
                >
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography variant="h6" component="h2" gutterBottom>
                      {article.title}
                    </Typography>
                    
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {article.content.substring(0, 150)}...
                    </Typography>
                    
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                      <Chip
                        icon={<SourceIcon />}
                        label={article.source}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                      <Chip
                        label={article.processing_status}
                        size="small"
                        color={getStatusColor(article.processing_status) as any}
                      />
                      {article.category && (
                        <Chip
                          label={article.category}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', color: 'text.secondary' }}>
                      <ScheduleIcon sx={{ mr: 0.5, fontSize: 16 }} />
                      <Typography variant="caption">
                        {formatDate(article.created_at.toString())}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}

        {/* Pagination */}
        {pagination.totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <Pagination
              count={pagination.totalPages}
              page={pagination.page}
              onChange={(_, page) => pagination.goToPage(page)}
              color="primary"
              size="large"
            />
          </Box>
        )}
      </Box>
    </ErrorBoundary>
  );
};

export default ArticlesV3;

