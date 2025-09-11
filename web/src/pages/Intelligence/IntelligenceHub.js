import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Paper,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  IconButton,
  Tooltip,
  Alert,
  LinearProgress,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Badge,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormLabel,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  Schedule as ScheduleIcon,
  Search as SearchIcon,
  TrendingUp as TrendingUpIcon,
  Group as GroupIcon,
  Psychology as PsychologyIcon,
  Refresh as RefreshIcon,
  FilterList as FilterIcon,
  AutoAwesome as AutoAwesomeIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
  History as HistoryIcon,
  AutoAwesome as PredictionIcon,
  Article as ArticleIcon,
  RssFeed as RssFeedIcon,
  Analytics as AnalyticsIcon,
  Visibility as VisibilityIcon,
  Share as ShareIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  ExpandMore as ExpandMoreIcon,
  PlayArrow as PlayArrowIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import { apiService } from '../../services/apiService';

const IntelligenceHub = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [bookmarkedItems, setBookmarkedItems] = useState(new Set());
  
  // Content data
  const [articles, setArticles] = useState([]);
  const [storylines, setStorylines] = useState([]);
  const [selectedContent, setSelectedContent] = useState(null);
  const [contentType, setContentType] = useState('storyline'); // 'article' or 'storyline'
  
  // Analysis states
  const [analysisDialogOpen, setAnalysisDialogOpen] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [analysisResults, setAnalysisResults] = useState({});
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleSearch = (event) => {
    setSearchQuery(event.target.value);
  };

  const toggleBookmark = (itemId) => {
    const newBookmarked = new Set(bookmarkedItems);
    if (newBookmarked.has(itemId)) {
      newBookmarked.delete(itemId);
    } else {
      newBookmarked.add(itemId);
    }
    setBookmarkedItems(newBookmarked);
  };

  // Load content data
  const loadContent = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [articlesResponse, storylinesResponse] = await Promise.all([
        apiService.getArticles({ limit: 50 }),
        apiService.getStorylines({ limit: 50 })
      ]);

      if (articlesResponse.success) {
        setArticles(articlesResponse.data?.articles || []);
      }
      
      if (storylinesResponse.success) {
        setStorylines(storylinesResponse.data?.storylines || []);
      }
    } catch (err) {
      console.error('Error loading content:', err);
      setError('Failed to load content');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load morning briefing data
  const [morningBriefing, setMorningBriefing] = useState(null);
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [topicClusters, setTopicClusters] = useState([]);
  const [discoveryResults, setDiscoveryResults] = useState([]);
  
  // Error states for individual data loading
  const [morningBriefingError, setMorningBriefingError] = useState(null);
  const [trendingTopicsError, setTrendingTopicsError] = useState(null);
  const [topicClustersError, setTopicClustersError] = useState(null);
  const [discoveryError, setDiscoveryError] = useState(null);
  
  // Loading states for individual data loading
  const [morningBriefingLoading, setMorningBriefingLoading] = useState(false);
  const [trendingTopicsLoading, setTrendingTopicsLoading] = useState(false);
  const [topicClustersLoading, setTopicClustersLoading] = useState(false);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);

  const loadMorningBriefing = useCallback(async () => {
    try {
      setMorningBriefingLoading(true);
      setMorningBriefingError(null);
      
      const response = await apiService.get('/api/intelligence/morning-briefing');
      if (response.success) {
        setMorningBriefing(response.data);
      } else {
        setMorningBriefingError('Failed to load morning briefing data');
      }
    } catch (err) {
      console.error('Error loading morning briefing:', err);
      setMorningBriefingError(err.message || 'Failed to load morning briefing');
    } finally {
      setMorningBriefingLoading(false);
    }
  }, []);

  const loadTrendingTopics = useCallback(async () => {
    try {
      setTrendingTopicsLoading(true);
      setTrendingTopicsError(null);
      
      const response = await apiService.get('/intelligence/trending-topics?time_period=24h&limit=10');
      if (response.success) {
        setTrendingTopics(response.data.trending_topics || []);
      } else {
        setTrendingTopicsError('Failed to load trending topics');
      }
    } catch (err) {
      console.error('Error loading trending topics:', err);
      setTrendingTopicsError(err.message || 'Failed to load trending topics');
    } finally {
      setTrendingTopicsLoading(false);
    }
  }, []);

  const loadTopicClusters = useCallback(async () => {
    try {
      setTopicClustersLoading(true);
      setTopicClustersError(null);
      
      const response = await apiService.get('/intelligence/topic-clusters?time_period=7d&min_articles=3');
      if (response.success) {
        setTopicClusters(response.data.clusters || []);
      } else {
        setTopicClustersError('Failed to load topic clusters');
      }
    } catch (err) {
      console.error('Error loading topic clusters:', err);
      setTopicClustersError(err.message || 'Failed to load topic clusters');
    } finally {
      setTopicClustersLoading(false);
    }
  }, []);

  const loadDiscoveryResults = useCallback(async (searchQuery = '', category = '') => {
    try {
      setDiscoveryLoading(true);
      setDiscoveryError(null);
      
      const params = new URLSearchParams();
      if (searchQuery) params.append('search_query', searchQuery);
      if (category) params.append('category', category);
      params.append('limit', '20');
      
      const response = await apiService.get(`/intelligence/discovery?${params.toString()}`);
      if (response.success) {
        setDiscoveryResults(response.data.articles || []);
      } else {
        setDiscoveryError('Failed to load discovery results');
      }
    } catch (err) {
      console.error('Error loading discovery results:', err);
      setDiscoveryError(err.message || 'Failed to load discovery results');
    } finally {
      setDiscoveryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContent();
    loadMorningBriefing();
    loadTrendingTopics();
    loadTopicClusters();
  }, [loadContent, loadMorningBriefing, loadTrendingTopics, loadTopicClusters]);

  // Analysis functions
  const runAnalysis = async (analysisType, contentId) => {
    try {
      setAnalysisLoading(true);
      setAnalysisError(null);
      
      let response;
      const endpoint = `/api/enhanced-analysis/${analysisType}/${contentId}`;
      
      switch (analysisType) {
        case 'multi-perspective':
          response = await apiService.post(endpoint, {});
          break;
        case 'impact-assessment':
          response = await apiService.post(endpoint, {});
          break;
        case 'predictive-analysis':
          response = await apiService.post(endpoint, {});
          break;
        case 'expert-analysis':
          response = await apiService.post(endpoint, {});
          break;
        default:
          throw new Error('Unknown analysis type');
      }

      if (response.success) {
        setAnalysisResults(prev => ({
          ...prev,
          [contentId]: {
            ...prev[contentId],
            [analysisType]: response.data
          }
        }));
      } else {
        throw new Error(response.message || 'Analysis failed');
      }
    } catch (err) {
      console.error(`Error running ${analysisType} analysis:`, err);
      setAnalysisError(`Failed to run ${analysisType} analysis: ${err.message}`);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleAnalysisClick = (analysisType) => {
    if (!selectedContent) {
      setError('Please select an article or storyline first');
      return;
    }
    
    setSelectedAnalysis(analysisType);
    setAnalysisDialogOpen(true);
  };

  const confirmAnalysis = () => {
    if (selectedContent && selectedAnalysis) {
      runAnalysis(selectedAnalysis, selectedContent.id);
      setAnalysisDialogOpen(false);
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

  // Morning Briefing Tab
  const MorningBriefingTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          <ScheduleIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Morning Briefing
        </Typography>
        <Tooltip title="Refresh Briefing">
          <IconButton onClick={() => {
            loadMorningBriefing();
            loadTrendingTopics();
          }} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Today's Highlights
              </Typography>
              {morningBriefingLoading ? (
                <Box display="flex" alignItems="center" justifyContent="center" py={4}>
                  <CircularProgress size={24} sx={{ mr: 2 }} />
                  <Typography variant="body2" color="text.secondary">
                    Loading morning briefing...
                  </Typography>
                </Box>
              ) : morningBriefingError ? (
                <Alert 
                  severity="error" 
                  action={
                    <Button size="small" onClick={loadMorningBriefing}>
                      Retry
                    </Button>
                  }
                >
                  {morningBriefingError}
                </Alert>
              ) : morningBriefing ? (
                <Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Generated: {new Date(morningBriefing.generated_at).toLocaleString()}
                  </Typography>
                  {morningBriefing.sections?.system_overview && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        System Overview
                      </Typography>
                      <Typography variant="body2">
                        Articles processed: {morningBriefing.sections.system_overview.articles_processed || 0}
                      </Typography>
                      <Typography variant="body2">
                        New articles: {morningBriefing.sections.system_overview.new_articles || 0}
                      </Typography>
                    </Box>
                  )}
                  {trendingTopics.length > 0 && (
                    <Box>
                      <Typography variant="subtitle2" gutterBottom>
                        Trending Topics
                      </Typography>
                      <Box display="flex" flexWrap="wrap" gap={1}>
                        {trendingTopics.slice(0, 5).map((topic) => (
                          <Chip 
                            key={topic.id} 
                            label={topic.name} 
                            size="small" 
                            color="primary"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </Box>
                  )}
                </Box>
              ) : (
                <Alert severity="info">
                  <Typography variant="body2">
                    No morning briefing data available. Click "Generate Briefing" to create one.
                  </Typography>
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                AI-Generated Summary
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Your personalized news summary based on your interests and reading patterns.
              </Typography>
              <Box display="flex" gap={1} mb={2}>
                <Chip label="Multi-Perspective" color="primary" size="small" />
                <Chip label="Impact Assessment" color="secondary" size="small" />
                <Chip label="Predictive Analysis" color="info" size="small" />
              </Box>
              <Button 
                variant="outlined" 
                startIcon={<AutoAwesomeIcon />}
                onClick={loadMorningBriefing}
                disabled={loading}
              >
                {loading ? 'Generating...' : 'Generate Briefing'}
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  // Discover Tab
  const DiscoverTab = () => {
    const handleSearchSubmit = () => {
      loadDiscoveryResults(searchQuery, filterCategory);
    };

    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h5" component="h2">
            <SearchIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Discover Articles
          </Typography>
          <Box display="flex" gap={2}>
            <TextField
              placeholder="Search articles..."
              value={searchQuery}
              onChange={handleSearch}
              onKeyPress={(e) => e.key === 'Enter' && handleSearchSubmit()}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
              sx={{ minWidth: 300 }}
            />
            <FormControl sx={{ minWidth: 120 }}>
              <InputLabel>Category</InputLabel>
              <Select
                value={filterCategory}
                label="Category"
                onChange={(e) => setFilterCategory(e.target.value)}
              >
                <MenuItem value="">All Categories</MenuItem>
                <MenuItem value="politics">Politics</MenuItem>
                <MenuItem value="business">Business</MenuItem>
                <MenuItem value="technology">Technology</MenuItem>
                <MenuItem value="health">Health</MenuItem>
                <MenuItem value="science">Science</MenuItem>
                <MenuItem value="sports">Sports</MenuItem>
              </Select>
            </FormControl>
            <Button 
              variant="contained" 
              onClick={handleSearchSubmit}
              disabled={loading}
            >
              Search
            </Button>
          </Box>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                {discoveryResults.length > 0 ? 'Search Results' : 'Recommended Articles'}
              </Typography>
              {discoveryLoading ? (
                <Box display="flex" alignItems="center" justifyContent="center" py={4}>
                  <CircularProgress size={24} sx={{ mr: 2 }} />
                  <Typography variant="body2" color="text.secondary">
                    Searching articles...
                  </Typography>
                </Box>
              ) : discoveryError ? (
                <Alert 
                  severity="error" 
                  action={
                    <Button size="small" onClick={() => loadDiscoveryResults(searchQuery, filterCategory)}>
                      Retry
                    </Button>
                  }
                >
                  {discoveryError}
                </Alert>
              ) : discoveryResults.length > 0 ? (
                <List>
                  {discoveryResults.map((article) => (
                    <ListItem key={article.id} divider>
                      <ListItemText
                        primary={article.title}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              {truncateText(article.summary || article.content, 150)}
                            </Typography>
                            <Box display="flex" gap={1} alignItems="center">
                              <Chip label={article.category} size="small" color="primary" variant="outlined" />
                              <Chip label={article.source} size="small" />
                              <Typography variant="caption" color="text.secondary">
                                Quality: {(article.quality_score * 100).toFixed(0)}%
                              </Typography>
                            </Box>
                          </Box>
                        }
                      />
                      <Box display="flex" gap={1}>
                        <IconButton 
                          size="small"
                          onClick={() => toggleBookmark(article.id)}
                        >
                          {bookmarkedItems.has(article.id) ? <BookmarkIcon /> : <BookmarkBorderIcon />}
                        </IconButton>
                        <IconButton size="small">
                          <VisibilityIcon />
                        </IconButton>
                        <IconButton size="small">
                          <ShareIcon />
                        </IconButton>
                      </Box>
                    </ListItem>
                  ))}
                </List>
              ) : (
                <List>
                  {articles.slice(0, 5).map((article) => (
                    <ListItem key={article.id} divider>
                      <ListItemText
                        primary={article.title}
                        secondary={truncateText(article.summary || article.content, 150)}
                      />
                      <Box display="flex" gap={1}>
                        <IconButton 
                          size="small"
                          onClick={() => toggleBookmark(article.id)}
                        >
                          {bookmarkedItems.has(article.id) ? <BookmarkIcon /> : <BookmarkBorderIcon />}
                        </IconButton>
                        <IconButton size="small">
                          <VisibilityIcon />
                        </IconButton>
                        <IconButton size="small">
                          <ShareIcon />
                        </IconButton>
                      </Box>
                    </ListItem>
                  ))}
                </List>
              )}
            </Paper>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Discovery Features
                </Typography>
                <Box display="flex" flexDirection="column" gap={2}>
                  <Button 
                    variant="outlined" 
                    startIcon={<AutoAwesomeIcon />}
                    onClick={() => loadDiscoveryResults('', '')}
                  >
                    AI-Powered Search
                  </Button>
                  <Button 
                    variant="outlined" 
                    startIcon={<TrendingUpIcon />}
                    onClick={loadTrendingTopics}
                  >
                    Trending Topics
                  </Button>
                  <Button 
                    variant="outlined" 
                    startIcon={<GroupIcon />}
                    onClick={loadTopicClusters}
                  >
                    Topic Clusters
                  </Button>
                  <Button 
                    variant="outlined" 
                    startIcon={<TimelineIcon />}
                    onClick={() => loadDiscoveryResults('', '')}
                  >
                    Related Stories
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    );
  };

  // Trends Tab
  const TrendsTab = () => {
    // Calculate sentiment distribution from trending topics
    const sentimentDistribution = trendingTopics.reduce((acc, topic) => {
      const sentiment = topic.avg_sentiment;
      if (sentiment > 0.1) acc.positive += 1;
      else if (sentiment < -0.1) acc.negative += 1;
      else acc.neutral += 1;
      return acc;
    }, { positive: 0, negative: 0, neutral: 0 });

    const total = sentimentDistribution.positive + sentimentDistribution.negative + sentimentDistribution.neutral;
    const positivePercent = total > 0 ? Math.round((sentimentDistribution.positive / total) * 100) : 0;
    const negativePercent = total > 0 ? Math.round((sentimentDistribution.negative / total) * 100) : 0;
    const neutralPercent = total > 0 ? Math.round((sentimentDistribution.neutral / total) * 100) : 0;

    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h5" component="h2">
            <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Trends Analysis
          </Typography>
          <Tooltip title="Refresh Trends">
            <IconButton onClick={loadTrendingTopics} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Trending Topics
                </Typography>
                {trendingTopicsLoading ? (
                  <Box display="flex" alignItems="center" justifyContent="center" py={2}>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    <Typography variant="body2" color="text.secondary">
                      Loading trending topics...
                    </Typography>
                  </Box>
                ) : trendingTopicsError ? (
                  <Alert 
                    severity="error" 
                    action={
                      <Button size="small" onClick={loadTrendingTopics}>
                        Retry
                      </Button>
                    }
                  >
                    {trendingTopicsError}
                  </Alert>
                ) : trendingTopics.length > 0 ? (
                  <Box>
                    <Box display="flex" flexWrap="wrap" gap={1} mb={2}>
                      {trendingTopics.slice(0, 8).map((topic) => (
                        <Chip 
                          key={topic.id}
                          label={`${topic.name} (${topic.article_count})`}
                          color="primary"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      Topics ranked by engagement and discussion volume over the past 24 hours.
                    </Typography>
                  </Box>
                ) : (
                  <Alert severity="info">
                    <Typography variant="body2">
                      No trending topics available. Click "Refresh Trends" to load data.
                    </Typography>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Sentiment Trends
                </Typography>
                {trendingTopicsLoading ? (
                  <Box display="flex" alignItems="center" justifyContent="center" py={2}>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    <Typography variant="body2" color="text.secondary">
                      Loading sentiment data...
                    </Typography>
                  </Box>
                ) : trendingTopicsError ? (
                  <Alert severity="error">
                    Unable to load sentiment trends
                  </Alert>
                ) : trendingTopics.length > 0 ? (
                  <Box display="flex" justifyContent="space-between" mb={2}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="success.main">{positivePercent}%</Typography>
                      <Typography variant="caption">Positive</Typography>
                    </Box>
                    <Box textAlign="center">
                      <Typography variant="h4" color="error.main">{negativePercent}%</Typography>
                      <Typography variant="caption">Negative</Typography>
                    </Box>
                    <Box textAlign="center">
                      <Typography variant="h4" color="info.main">{neutralPercent}%</Typography>
                      <Typography variant="caption">Neutral</Typography>
                    </Box>
                  </Box>
                ) : (
                  <Alert severity="info">
                    <Typography variant="body2">
                      No sentiment data available
                    </Typography>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  AI Analysis Features
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <Box textAlign="center">
                      <AutoAwesomeIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                      <Typography variant="h6">Multi-Perspective</Typography>
                      <Typography variant="body2" color="text.secondary">
                        Analyze trends from multiple viewpoints
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Box textAlign="center">
                      <AssessmentIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                      <Typography variant="h6">Impact Assessment</Typography>
                      <Typography variant="body2" color="text.secondary">
                        Evaluate potential impacts of trending topics
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Box textAlign="center">
                      <PredictionIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                      <Typography variant="h6">Predictive Analysis</Typography>
                      <Typography variant="body2" color="text.secondary">
                        Forecast future trend developments
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    );
  };

  // Clusters Tab
  const ClustersTab = () => {
    // Calculate cluster metrics
    const totalClusters = topicClusters.length;
    const avgQuality = topicClusters.length > 0 
      ? topicClusters.reduce((sum, cluster) => sum + cluster.avg_quality, 0) / topicClusters.length 
      : 0;
    const totalArticles = topicClusters.reduce((sum, cluster) => sum + cluster.article_count, 0);
    const sourceDiversity = topicClusters.reduce((sum, cluster) => sum + cluster.sources.length, 0);

    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h5" component="h2">
            <GroupIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Topic Clusters
          </Typography>
          <Tooltip title="Refresh Clusters">
            <IconButton onClick={loadTopicClusters} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Active Clusters
                </Typography>
                {topicClustersLoading ? (
                  <Box display="flex" alignItems="center" justifyContent="center" py={2}>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    <Typography variant="body2" color="text.secondary">
                      Loading clusters...
                    </Typography>
                  </Box>
                ) : topicClustersError ? (
                  <Alert 
                    severity="error" 
                    action={
                      <Button size="small" onClick={loadTopicClusters}>
                        Retry
                      </Button>
                    }
                  >
                    {topicClustersError}
                  </Alert>
                ) : topicClusters.length > 0 ? (
                  <List>
                    {topicClusters.slice(0, 5).map((cluster) => (
                      <ListItem key={cluster.id}>
                        <ListItemIcon>
                          <ArticleIcon color="primary" />
                        </ListItemIcon>
                        <ListItemText
                          primary={cluster.name}
                          secondary={`${cluster.article_count} articles • ${cluster.sources.length} sources`}
                        />
                        <Box display="flex" alignItems="center" gap={1}>
                          <Chip 
                            label={`${(cluster.avg_quality * 100).toFixed(0)}%`}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                        </Box>
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Alert severity="info">
                    <Typography variant="body2">
                      No topic clusters available. Click "Refresh Clusters" to load data.
                    </Typography>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Cluster Analysis
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  AI-powered topic clustering helps identify related articles and emerging story patterns.
                </Typography>
                {topicClustersLoading ? (
                  <Box display="flex" alignItems="center" justifyContent="center" py={2}>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    <Typography variant="body2" color="text.secondary">
                      Loading cluster analysis...
                    </Typography>
                  </Box>
                ) : topicClustersError ? (
                  <Alert severity="error">
                    Unable to load cluster analysis
                  </Alert>
                ) : topicClusters.length > 0 ? (
                  <Box display="flex" flexDirection="column" gap={1}>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2">Total Clusters</Typography>
                      <Typography variant="body2" color="primary">{totalClusters}</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2">Avg Quality</Typography>
                      <Typography variant="body2" color="primary">{(avgQuality * 100).toFixed(0)}%</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2">Total Articles</Typography>
                      <Typography variant="body2" color="primary">{totalArticles}</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2">Source Diversity</Typography>
                      <Typography variant="body2" color="primary">{sourceDiversity}</Typography>
                    </Box>
                  </Box>
                ) : (
                  <Alert severity="info">
                    <Typography variant="body2">
                      No cluster analysis data available
                    </Typography>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    );
  };

  // AI Analysis Tab
  const AIAnalysisTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          AI Analysis
        </Typography>
        <Tooltip title="Refresh Content">
          <IconButton onClick={loadContent} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Content Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Select Content for Analysis
          </Typography>
          <FormControl component="fieldset" sx={{ mb: 2 }}>
            <FormLabel component="legend">Content Type</FormLabel>
            <RadioGroup
              row
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
            >
              <FormControlLabel value="storyline" control={<Radio />} label="Storylines" />
              <FormControlLabel value="article" control={<Radio />} label="Articles" />
            </RadioGroup>
          </FormControl>
          
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Select {contentType === 'storyline' ? 'Storyline' : 'Article'}</InputLabel>
            <Select
              value={selectedContent?.id || ''}
              label={`Select ${contentType === 'storyline' ? 'Storyline' : 'Article'}`}
              onChange={(e) => {
                const content = contentType === 'storyline' 
                  ? storylines.find(s => s.id === e.target.value)
                  : articles.find(a => a.id === e.target.value);
                setSelectedContent(content);
              }}
            >
              {(contentType === 'storyline' ? storylines : articles).map((item) => (
                <MenuItem key={item.id} value={item.id}>
                  {item.title || item.headline}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {selectedContent && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Selected: <strong>{selectedContent.title || selectedContent.headline}</strong>
              {selectedContent.description && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  {truncateText(selectedContent.description, 200)}
                </Typography>
              )}
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Analysis Options */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <AutoAwesomeIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Multi-Perspective Analysis
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Analyze from multiple viewpoints and sources to provide balanced insights.
              </Typography>
              <Button 
                variant="outlined" 
                fullWidth
                onClick={() => handleAnalysisClick('multi-perspective')}
                disabled={!selectedContent || analysisLoading}
                startIcon={analysisLoading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {analysisLoading ? 'Running...' : 'Run Analysis'}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <AssessmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Impact Assessment
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Evaluate potential impacts across different dimensions and stakeholders.
              </Typography>
              <Button 
                variant="outlined" 
                fullWidth
                onClick={() => handleAnalysisClick('impact-assessment')}
                disabled={!selectedContent || analysisLoading}
                startIcon={analysisLoading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {analysisLoading ? 'Running...' : 'Assess Impact'}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <PredictionIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Predictive Analysis
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Forecast future developments and trends based on current data patterns.
              </Typography>
              <Button 
                variant="outlined" 
                fullWidth
                onClick={() => handleAnalysisClick('predictive-analysis')}
                disabled={!selectedContent || analysisLoading}
                startIcon={analysisLoading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {analysisLoading ? 'Running...' : 'Generate Predictions'}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <AnalyticsIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Expert Analysis
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Integrate expert opinions and authoritative sources for comprehensive analysis.
              </Typography>
              <Button 
                variant="outlined" 
                fullWidth
                onClick={() => handleAnalysisClick('expert-analysis')}
                disabled={!selectedContent || analysisLoading}
                startIcon={analysisLoading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {analysisLoading ? 'Running...' : 'Request Analysis'}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <AutoAwesomeIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Run All Analyses
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Execute all available analysis types for comprehensive insights.
              </Typography>
              <Button 
                variant="contained" 
                fullWidth
                onClick={() => {
                  if (selectedContent) {
                    ['multi-perspective', 'impact-assessment', 'predictive-analysis', 'expert-analysis'].forEach(analysisType => {
                      runAnalysis(analysisType, selectedContent.id);
                    });
                  }
                }}
                disabled={!selectedContent || analysisLoading}
                startIcon={analysisLoading ? <CircularProgress size={20} /> : <AutoAwesomeIcon />}
              >
                {analysisLoading ? 'Running All...' : 'Run All Analyses'}
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Analysis Results */}
      {selectedContent && analysisResults[selectedContent.id] && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Analysis Results for: {selectedContent.title || selectedContent.headline}
            </Typography>
            {Object.entries(analysisResults[selectedContent.id]).map(([analysisType, result]) => (
              <Accordion key={analysisType} sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1" sx={{ textTransform: 'capitalize' }}>
                    {analysisType.replace('-', ' ')} Analysis
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(result, null, 2)}
                  </Typography>
                </AccordionDetails>
              </Accordion>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Analysis Error */}
      {analysisError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {analysisError}
        </Alert>
      )}
    </Box>
  );

  const tabContent = [
    { label: 'Morning Briefing', content: <MorningBriefingTab /> },
    { label: 'Discover', content: <DiscoverTab /> },
    { label: 'Trends', content: <TrendsTab /> },
    { label: 'Clusters', content: <ClustersTab /> },
    { label: 'AI Analysis', content: <AIAnalysisTab /> }
  ];

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 3 }}>
        Intelligence Hub
      </Typography>

      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          {tabContent.map((tab, index) => (
            <Tab key={index} label={tab.label} />
          ))}
        </Tabs>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {tabContent[activeTab].content}

      {/* Analysis Confirmation Dialog */}
      <Dialog open={analysisDialogOpen} onClose={() => setAnalysisDialogOpen(false)}>
        <DialogTitle>Confirm Analysis</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Run <strong>{selectedAnalysis?.replace('-', ' ')}</strong> analysis on:
          </Typography>
          {selectedContent && (
            <Alert severity="info">
              <strong>{selectedContent.title || selectedContent.headline}</strong>
              {selectedContent.description && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  {truncateText(selectedContent.description, 150)}
                </Typography>
              )}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAnalysisDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmAnalysis} variant="contained">
            Run Analysis
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default IntelligenceHub;
