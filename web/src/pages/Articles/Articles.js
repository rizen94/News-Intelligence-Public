import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  Schedule as ScheduleIcon,
  Refresh as RefreshIcon,
  ReadMore as ReadMoreIcon,
  Psychology as PsychologyIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
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
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Tooltip,
  Badge,
  LinearProgress,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiService } from '../../services/apiService.ts';

const Articles = () => {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [biasFilter, setBiasFilter] = useState('');
  const [sortBy, setSortBy] = useState('published_at');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalArticles, setTotalArticles] = useState(0);
  const [sources, setSources] = useState([]);
  const [categories, setCategories] = useState([]);
  const [biasStats, setBiasStats] = useState({
    total: 0,
    leftBias: 0,
    centerBias: 0,
    rightBias: 0,
    analyzed: 0,
  });
  const navigate = useNavigate();

  const fetchArticles = useCallback(async(isManualRefresh = false) => {
    try {
      setLoading(true);

      const params = {
        page,
        limit: 20,
        search: searchTerm || undefined,
        category: categoryFilter || undefined,
        source: sourceFilter || undefined,
        sort_by: sortBy,
        bias_filter: biasFilter || undefined,
      };

      const response = await apiService.articles.getArticles(params);

      if (response.success) {
        setArticles(response.data.articles || []);
        setTotalPages(response.data.total_pages || 1);
        setTotalArticles(response.data.total_count || 0);

        // Calculate bias statistics
        const articles = response.data.articles || [];
        const biasStats = {
          total: articles.length,
          leftBias: articles.filter(a => a.bias_score < -0.3).length,
          centerBias: articles.filter(a => Math.abs(a.bias_score) <= 0.3).length,
          rightBias: articles.filter(a => a.bias_score > 0.3).length,
          analyzed: articles.filter(a => a.bias_score !== null && a.bias_score !== undefined).length,
        };
        setBiasStats(biasStats);
      }
    } catch (error) {
      console.error('Error fetching articles:', error);
    } finally {
      setLoading(false);
    }
  }, [page, searchTerm, categoryFilter, sourceFilter, sortBy, biasFilter]);

  const fetchSourcesAndCategories = useCallback(async() => {
    try {
      const [sourcesRes, categoriesRes] = await Promise.all([
        apiService.articles.getSources(),
        apiService.articles.getCategories(),
      ]);

      if (sourcesRes.success) {
        setSources(sourcesRes.data.sources || []);
      }
      if (categoriesRes.success) {
        setCategories(categoriesRes.data.categories || []);
      }
    } catch (error) {
      console.error('Error fetching sources and categories:', error);
    }
  }, []);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  useEffect(() => {
    fetchSourcesAndCategories();
  }, [fetchSourcesAndCategories]);

  const getBiasColor = (biasScore) => {
    if (biasScore < -0.3) return 'error';
    if (biasScore > 0.3) return 'warning';
    return 'success';
  };

  const getBiasLabel = (biasScore) => {
    if (biasScore < -0.3) return 'Left Bias';
    if (biasScore > 0.3) return 'Right Bias';
    return 'Center';
  };

  const getBiasIcon = (biasScore) => {
    if (biasScore < -0.3) return <WarningIcon />;
    if (biasScore > 0.3) return <TrendingUpIcon />;
    return <CheckCircleIcon />;
  };

  const getCredibilityColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          📰 Articles with Bias Analysis
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => fetchArticles(true)}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Bias Statistics Overview */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="primary">
                {biasStats.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Articles
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="error">
                {biasStats.leftBias}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Left Bias
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="success">
                {biasStats.centerBias}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Center
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="warning">
                {biasStats.rightBias}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Right Bias
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="info">
                {biasStats.analyzed}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Analyzed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="primary">
                {biasStats.total > 0 ? Math.round((biasStats.analyzed / biasStats.total) * 100) : 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Analysis Rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
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
              <InputLabel>Bias</InputLabel>
              <Select
                value={biasFilter}
                onChange={(e) => setBiasFilter(e.target.value)}
                label="Bias"
              >
                <MenuItem value="">All Bias</MenuItem>
                <MenuItem value="left">Left Bias</MenuItem>
                <MenuItem value="center">Center</MenuItem>
                <MenuItem value="right">Right Bias</MenuItem>
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
                <MenuItem value="published_at">Published Date</MenuItem>
                <MenuItem value="title">Title</MenuItem>
                <MenuItem value="bias_score">Bias Score</MenuItem>
                <MenuItem value="credibility_score">Credibility</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={1}>
            <Button
              variant="contained"
              startIcon={<FilterIcon />}
              onClick={() => fetchArticles(true)}
              disabled={loading}
              fullWidth
            >
              Filter
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Articles List */}
      {loading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={2}>
          {articles.map((article) => (
            <Grid item xs={12} key={article.id}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Box flex={1}>
                      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
                        {article.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {article.summary || 'No summary available'}
                      </Typography>
                      <Box display="flex" alignItems="center" gap={1} mb={1}>
                        <Chip
                          icon={<SourceIcon />}
                          label={article.source}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          icon={<ScheduleIcon />}
                          label={formatDate(article.published_at)}
                          size="small"
                          variant="outlined"
                        />
                        {article.category && (
                          <Chip
                            label={article.category}
                            size="small"
                            color="primary"
                          />
                        )}
                      </Box>
                    </Box>
                    <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
                      {/* Bias Analysis */}
                      {article.bias_score !== null && article.bias_score !== undefined && (
                        <Tooltip title={`Bias Score: ${article.bias_score.toFixed(2)}`}>
                          <Chip
                            icon={getBiasIcon(article.bias_score)}
                            label={getBiasLabel(article.bias_score)}
                            color={getBiasColor(article.bias_score)}
                            size="small"
                          />
                        </Tooltip>
                      )}

                      {/* Credibility Score */}
                      {article.credibility_score && (
                        <Tooltip title={`Credibility Score: ${article.credibility_score.toFixed(2)}`}>
                          <Chip
                            icon={<CheckCircleIcon />}
                            label={`${Math.round(article.credibility_score * 100)}%`}
                            color={getCredibilityColor(article.credibility_score)}
                            size="small"
                            variant="outlined"
                          />
                        </Tooltip>
                      )}

                      {/* Read More Button */}
                      <Button
                        size="small"
                        startIcon={<ReadMoreIcon />}
                        onClick={() => navigate(`/articles/${article.id}`)}
                      >
                        Read More
                      </Button>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <Box display="flex" justifyContent="center" mt={3}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(event, value) => setPage(value)}
            color="primary"
          />
        </Box>
      )}

      {/* Results Summary */}
      <Box mt={2}>
        <Typography variant="body2" color="text.secondary">
          Showing {articles.length} of {totalArticles} articles
        </Typography>
      </Box>
    </Box>
  );
};

export default Articles;
