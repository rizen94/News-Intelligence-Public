import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  TextField,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  Tabs,
  Tab,
  Paper,
  Avatar,
  Tooltip,
  LinearProgress,
  Alert,
  CircularProgress,
  Divider,
  Badge
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Article as ArticleIcon,
  Psychology as PsychologyIcon,
  Timeline as TimelineIcon,
  Visibility as VisibilityIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  SentimentSatisfied as SentimentSatisfiedIcon,
  SentimentDissatisfied as SentimentDissatisfiedIcon,
  SentimentNeutral as SentimentNeutralIcon,
  AutoAwesome as AutoAwesomeIcon,
  Link as LinkIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { newsSystemService } from '../../services/newsSystemService';
import { useNotifications } from '../../components/Notifications/NotificationSystem';

const EnhancedArticles = () => {
  const { showSuccess, showError, showLoading, showInfo } = useNotifications();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    source: '',
    sentiment: '',
    dateFrom: '',
    dateTo: ''
  });
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [total, setTotal] = useState(0);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [stats, setStats] = useState(null);
  const [buttonLoading, setButtonLoading] = useState({});

  useEffect(() => {
    fetchArticles();
    fetchStats();
  }, [page, perPage, sortBy, sortOrder, filters, searchQuery]);

  const fetchArticles = async (isManualRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      if (isManualRefresh) {
        showInfo('Loading articles...', 'Articles Refresh');
      }

      const params = {
        page,
        per_page: perPage,
        sort_by: sortBy,
        sort_order: sortOrder,
        search: searchQuery || undefined,
        ...filters
      };

      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '' || params[key] === undefined) {
          delete params[key];
        }
      });

      const response = await newsSystemService.getArticles(params);
      setArticles(response.articles || []);
      setTotal(response.total || 0);

      if (isManualRefresh) {
        showSuccess(`Loaded ${response.articles?.length || 0} articles`, 'Articles Updated');
      }
    } catch (err) {
      console.error('Error fetching articles:', err);
      setError(err.message);
      
      if (isManualRefresh) {
        showError(`Failed to load articles: ${err.message}`, 'Load Error');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await newsSystemService.getArticleStats();
      setStats(response);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const handleSearch = async () => {
    setButtonLoading(prev => ({ ...prev, search: true }));
    try {
      setPage(1);
      await fetchArticles(true);
    } finally {
      setButtonLoading(prev => ({ ...prev, search: false }));
    }
  };

  const handleFilterChange = (filterName, value) => {
    setFilters(prev => ({
      ...prev,
      [filterName]: value
    }));
    setPage(1);
  };

  const handleSortChange = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleViewArticle = async (article) => {
    setButtonLoading(prev => ({ ...prev, [`view-${article.id}`]: true }));
    try {
      setSelectedArticle(article);
      setDetailDialogOpen(true);
    } finally {
      setButtonLoading(prev => ({ ...prev, [`view-${article.id}`]: false }));
    }
  };

  const handleAnalyzeArticle = async (articleId) => {
    try {
      setAnalyzing(true);
      setButtonLoading(prev => ({ ...prev, [`analyze-${articleId}`]: true }));
      
      showLoading('Analyzing article with AI...', 'AI Analysis');
      
      await newsSystemService.analyzeArticle(articleId);
      
      showSuccess('Article analyzed successfully!', 'Analysis Complete');
      
      // Refresh the article list to show updated analysis
      await fetchArticles();
    } catch (err) {
      console.error('Error analyzing article:', err);
      showError(`Failed to analyze article: ${err.message}`, 'Analysis Error');
    } finally {
      setAnalyzing(false);
      setButtonLoading(prev => ({ ...prev, [`analyze-${articleId}`]: false }));
    }
  };

  const getSentimentIcon = (sentiment) => {
    if (sentiment > 0.1) return <SentimentSatisfiedIcon color="success" />;
    if (sentiment < -0.1) return <SentimentDissatisfiedIcon color="error" />;
    return <SentimentNeutralIcon color="default" />;
  };

  const getSentimentColor = (sentiment) => {
    if (sentiment > 0.1) return 'success';
    if (sentiment < -0.1) return 'error';
    return 'default';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'processed': return 'success';
      case 'processing': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const truncateText = (text, maxLength = 150) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  if (loading && articles.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" ml={2}>
          Loading articles...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Articles Analysis
        </Typography>
        <Button
          variant="outlined"
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={() => fetchArticles(true)}
          disabled={loading}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </Button>
      </Box>

      {/* Stats Overview */}
      {stats && (
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Total Articles
                    </Typography>
                    <Typography variant="h4">
                      {stats.total_articles || 0}
                    </Typography>
                  </Box>
                  <ArticleIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Processed
                    </Typography>
                    <Typography variant="h4">
                      {stats.by_status?.processed || 0}
                    </Typography>
                  </Box>
                  <PsychologyIcon sx={{ fontSize: 40, color: 'success.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Processing
                    </Typography>
                    <Typography variant="h4">
                      {stats.by_status?.processing || 0}
                    </Typography>
                  </Box>
                  <TimelineIcon sx={{ fontSize: 40, color: 'warning.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Avg Sentiment
                    </Typography>
                    <Typography variant="h4">
                      {stats.avg_sentiment?.toFixed(2) || '0.00'}
                    </Typography>
                  </Box>
                  <AutoAwesomeIcon sx={{ fontSize: 40, color: 'info.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Search and Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Search articles"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              InputProps={{
                startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.status}
                label="Status"
                onChange={(e) => handleFilterChange('status', e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="processing">Processing</MenuItem>
                <MenuItem value="processed">Processed</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={filters.source}
                label="Source"
                onChange={(e) => handleFilterChange('source', e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                {stats?.top_sources && Object.keys(stats.top_sources).map(source => (
                  <MenuItem key={source} value={source}>{source}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sentiment</InputLabel>
              <Select
                value={filters.sentiment}
                label="Sentiment"
                onChange={(e) => handleFilterChange('sentiment', e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="positive">Positive</MenuItem>
                <MenuItem value="neutral">Neutral</MenuItem>
                <MenuItem value="negative">Negative</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="contained"
              startIcon={buttonLoading.search ? <CircularProgress size={16} /> : <SearchIcon />}
              onClick={handleSearch}
              disabled={loading || buttonLoading.search}
            >
              {buttonLoading.search ? 'Searching...' : 'Search'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Articles List */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading && (
        <LinearProgress sx={{ mb: 2 }} />
      )}

      <Grid container spacing={2}>
        {articles.map((article) => (
          <Grid item xs={12} key={article.id}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                  <Box flex={1}>
                    <Typography variant="h6" gutterBottom>
                      {article.title}
                    </Typography>
                    <Typography variant="body2" color="textSecondary" paragraph>
                      {truncateText(article.content)}
                    </Typography>
                    
                    <Box display="flex" alignItems="center" gap={2} mb={2}>
                      <Chip
                        label={article.source}
                        size="small"
                        variant="outlined"
                      />
                      <Chip
                        label={article.status}
                        size="small"
                        color={getStatusColor(article.status)}
                      />
                      {article.sentiment !== null && (
                        <Box display="flex" alignItems="center" gap={0.5}>
                          {getSentimentIcon(article.sentiment)}
                          <Typography variant="body2" color={`${getSentimentColor(article.sentiment)}.main`}>
                            {article.sentiment.toFixed(2)}
                          </Typography>
                        </Box>
                      )}
                      {article.relevance_score && (
                        <Chip
                          label={`Relevance: ${(article.relevance_score * 100).toFixed(0)}%`}
                          size="small"
                          color="info"
                          variant="outlined"
                        />
                      )}
                    </Box>

                    <Box display="flex" alignItems="center" gap={2}>
                      <Typography variant="caption" color="textSecondary">
                        <ScheduleIcon sx={{ fontSize: 14, mr: 0.5 }} />
                        {formatDate(article.created_at)}
                      </Typography>
                      {article.tags && article.tags.length > 0 && (
                        <Box display="flex" gap={0.5}>
                          {article.tags.slice(0, 3).map((tag, index) => (
                            <Chip key={index} label={tag} size="small" variant="outlined" />
                          ))}
                          {article.tags.length > 3 && (
                            <Chip label={`+${article.tags.length - 3}`} size="small" variant="outlined" />
                          )}
                        </Box>
                      )}
                    </Box>
                  </Box>

                  <Box display="flex" flexDirection="column" gap={1}>
                    <Tooltip title="View Details">
                      <IconButton 
                        onClick={() => handleViewArticle(article)}
                        disabled={buttonLoading[`view-${article.id}`]}
                      >
                        {buttonLoading[`view-${article.id}`] ? 
                          <CircularProgress size={20} /> : 
                          <VisibilityIcon />
                        }
                      </IconButton>
                    </Tooltip>
                    {article.status !== 'processed' && (
                      <Tooltip title={buttonLoading[`analyze-${article.id}`] ? "Analyzing..." : "Analyze with AI"}>
                        <IconButton 
                          onClick={() => handleAnalyzeArticle(article.id)}
                          disabled={analyzing || buttonLoading[`analyze-${article.id}`]}
                        >
                          {buttonLoading[`analyze-${article.id}`] ? 
                            <CircularProgress size={20} /> : 
                            <PsychologyIcon />
                          }
                        </IconButton>
                      </Tooltip>
                    )}
                    <Tooltip title="Open Original">
                      <IconButton 
                        component="a" 
                        href={article.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                      >
                        <LinkIcon />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Pagination */}
      {total > perPage && (
        <Box display="flex" justifyContent="center" mt={3}>
          <Pagination
            count={Math.ceil(total / perPage)}
            page={page}
            onChange={handlePageChange}
            color="primary"
            size="large"
          />
        </Box>
      )}

      {/* Article Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
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
                {selectedArticle.content}
              </Typography>
              
              {selectedArticle.summary && (
                <Box mb={2}>
                  <Typography variant="h6" gutterBottom>
                    AI Summary
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                    <Typography variant="body2">
                      {selectedArticle.summary}
                    </Typography>
                  </Paper>
                </Box>
              )}

              {selectedArticle.entities && selectedArticle.entities.length > 0 && (
                <Box mb={2}>
                  <Typography variant="h6" gutterBottom>
                    Key Entities
                  </Typography>
                  <Box display="flex" flexWrap="wrap" gap={1}>
                    {selectedArticle.entities.map((entity, index) => (
                      <Chip
                        key={index}
                        label={`${entity.name} (${entity.type})`}
                        size="small"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </Box>
              )}

              <Box display="flex" gap={2} flexWrap="wrap">
                <Chip label={`Source: ${selectedArticle.source}`} />
                <Chip label={`Status: ${selectedArticle.status}`} color={getStatusColor(selectedArticle.status)} />
                {selectedArticle.sentiment !== null && (
                  <Chip
                    label={`Sentiment: ${selectedArticle.sentiment.toFixed(2)}`}
                    color={getSentimentColor(selectedArticle.sentiment)}
                  />
                )}
                {selectedArticle.relevance_score && (
                  <Chip
                    label={`Relevance: ${(selectedArticle.relevance_score * 100).toFixed(0)}%`}
                    color="info"
                  />
                )}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>
            Close
          </Button>
          <Button
            component="a"
            href={selectedArticle?.url}
            target="_blank"
            rel="noopener noreferrer"
            variant="contained"
          >
            View Original
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnhancedArticles;
