import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Pagination,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip as MuiChip
} from '@mui/material';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Analytics as AnalyticsIcon
} from '@mui/icons-material';
import { apiService, Article, ArticleList } from '../../services/apiService';

interface ArticlesState {
  articles: Article[];
  loading: boolean;
  error: string | null;
  total: number;
  page: number;
  limit: number;
  sources: string[];
  categories: string[];
  searchQuery: string;
  selectedSource: string;
  selectedCategory: string;
}

const Articles: React.FC = () => {
  const [state, setState] = useState<ArticlesState>({
    articles: [],
    loading: true,
    error: null,
    total: 0,
    page: 0,
    limit: 20,
    sources: [],
    categories: [],
    searchQuery: '',
    selectedSource: '',
    selectedCategory: ''
  });

  useEffect(() => {
    loadArticles();
    loadSources();
    loadCategories();
  }, [state.page, state.limit, state.selectedSource, state.selectedCategory]);

  const loadArticles = async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      const response = await apiService.getArticles({
        page: state.page + 1,
        limit: state.limit,
        source: state.selectedSource || undefined,
        category: state.selectedCategory || undefined
      });

      setState(prev => ({
        ...prev,
        articles: response.data.items,
        total: response.data.total,
        loading: false
      }));
    } catch (error) {
      console.error('Error loading articles:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load articles'
      }));
    }
  };

  const loadSources = async () => {
    try {
      const response = await apiService.getArticleSources();
      setState(prev => ({ ...prev, sources: response.data }));
    } catch (error) {
      console.error('Error loading sources:', error);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await apiService.getArticleCategories();
      setState(prev => ({ ...prev, categories: response.data }));
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const handleSearch = async () => {
    if (!state.searchQuery.trim()) {
      loadArticles();
      return;
    }

    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      const response = await apiService.searchArticles({
        query: state.searchQuery,
        source: state.selectedSource || undefined,
        category: state.selectedCategory || undefined,
        page: state.page + 1,
        limit: state.limit
      });

      setState(prev => ({
        ...prev,
        articles: response.data.items,
        total: response.data.total,
        loading: false
      }));
    } catch (error) {
      console.error('Error searching articles:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to search articles'
      }));
    }
  };

  const handlePageChange = (event: unknown, newPage: number) => {
    setState(prev => ({ ...prev, page: newPage }));
  };

  const handleRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({
      ...prev,
      limit: parseInt(event.target.value, 10),
      page: 0
    }));
  };

  const handleAnalyzeArticle = async (articleId: string) => {
    try {
      await apiService.analyzeArticle(articleId);
      // Refresh articles to show updated analysis
      loadArticles();
    } catch (error) {
      console.error('Error analyzing article:', error);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getQualityColor = (score?: number) => {
    if (!score) return 'default';
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Articles
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={loadArticles}
          disabled={state.loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Search and Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Search Articles"
              value={state.searchQuery}
              onChange={(e) => setState(prev => ({ ...prev, searchQuery: e.target.value }))}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              InputProps={{
                endAdornment: (
                  <IconButton onClick={handleSearch} edge="end">
                    <SearchIcon />
                  </IconButton>
                )
              }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={state.selectedSource}
                onChange={(e) => setState(prev => ({ ...prev, selectedSource: e.target.value }))}
                label="Source"
              >
                <MenuItem value="">All Sources</MenuItem>
                {state.sources.map((source) => (
                  <MenuItem key={source} value={source}>
                    {source}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={state.selectedCategory}
                onChange={(e) => setState(prev => ({ ...prev, selectedCategory: e.target.value }))}
                label="Category"
              >
                <MenuItem value="">All Categories</MenuItem>
                {state.categories.map((category) => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="contained"
              onClick={handleSearch}
              disabled={state.loading}
            >
              Search
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Error Alert */}
      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {state.error}
        </Alert>
      )}

      {/* Loading Indicator */}
      {state.loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Articles Table */}
      {!state.loading && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Published</TableCell>
                <TableCell>Quality</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {state.articles.map((article) => (
                <TableRow key={article.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {article.title}
                    </Typography>
                    {article.summary && (
                      <Typography variant="caption" color="text.secondary">
                        {article.summary.substring(0, 100)}...
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip label={article.source || 'Unknown'} size="small" />
                  </TableCell>
                  <TableCell>
                    {article.category && (
                      <Chip label={article.category} size="small" color="primary" />
                    )}
                  </TableCell>
                  <TableCell>
                    {article.published_at && formatDate(article.published_at)}
                  </TableCell>
                  <TableCell>
                    {article.quality_score && (
                      <MuiChip
                        label={`${(article.quality_score * 100).toFixed(0)}%`}
                        size="small"
                        color={getQualityColor(article.quality_score)}
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={article.processing_status}
                      size="small"
                      color={article.processing_status === 'completed' ? 'success' : 'warning'}
                    />
                  </TableCell>
                  <TableCell>
                    <Tooltip title="View Details">
                      <IconButton size="small">
                        <ViewIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Analyze">
                      <IconButton
                        size="small"
                        onClick={() => handleAnalyzeArticle(article.id)}
                      >
                        <AnalyticsIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            rowsPerPageOptions={[10, 20, 50]}
            component="div"
            count={state.total}
            rowsPerPage={state.limit}
            page={state.page}
            onPageChange={handlePageChange}
            onRowsPerPageChange={handleRowsPerPageChange}
          />
        </TableContainer>
      )}

      {/* No Articles Message */}
      {!state.loading && state.articles.length === 0 && (
        <Box sx={{ textAlign: 'center', p: 4 }}>
          <Typography variant="h6" color="text.secondary">
            No articles found
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default Articles;
