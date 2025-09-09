import React, { useState, useEffect } from 'react';
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
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Search as SearchIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../../components/Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';

const Discover = () => {
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [timeFilter, setTimeFilter] = useState('today');
  const [activeTab, setActiveTab] = useState(0);
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [recentArticles, setRecentArticles] = useState([]);
  const [newStorylines, setNewStorylines] = useState([]);
  const navigate = useNavigate();
  const { showSuccess, showError, showLoading } = useNotifications();

  useEffect(() => {
    fetchDiscoverData();
  }, []);

  const fetchDiscoverData = async (isManualRefresh = false) => {
    try {
      setLoading(true);
      if (isManualRefresh) {
        showLoading('Refreshing discover content...');
      } else {
        showLoading('Loading discover content...');
      }

      // Fetch trending topics, recent articles, and new storylines
      const params = { 
        per_page: 20, 
        sort_by: 'created_at', 
        sort_order: 'desc' 
      };
      
      // Add cache-busting parameter for manual refresh
      if (isManualRefresh) {
        params._t = Date.now();
      }

      const [articlesResponse, storylinesResponse] = await Promise.all([
        newsSystemService.getArticles(params),
        newsSystemService.getActiveStories()
      ]);

      if (articlesResponse.success) {
        setRecentArticles(articlesResponse.data.articles || []);
      }

      if (storylinesResponse.success) {
        setNewStorylines(storylinesResponse.data || []);
      }

      // Generate trending topics from articles
      const trending = generateTrendingTopics(recentArticles);
      setTrendingTopics(trending);

      if (isManualRefresh) {
        showSuccess('Discover content refreshed');
      } else {
        showSuccess('Discover content loaded');
      }
    } catch (error) {
      console.error('Error loading discover data:', error);
      showError('Failed to load discover content');
    } finally {
      setLoading(false);
    }
  };

  const generateTrendingTopics = (articles) => {
    // Simple trending topics generation based on article titles
    const topicCounts = {};
    articles.forEach(article => {
      const words = article.title.toLowerCase().split(/\s+/);
      words.forEach(word => {
        if (word.length > 3) {
          topicCounts[word] = (topicCounts[word] || 0) + 1;
        }
      });
    });

    return Object.entries(topicCounts)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 10)
      .map(([topic, count]) => ({ topic, count }));
  };

  const handleSearch = () => {
    if (searchTerm.trim()) {
      navigate(`/articles?search=${encodeURIComponent(searchTerm)}`);
    }
  };

  const handleArticleClick = (articleId) => {
    navigate(`/articles/${articleId}`);
  };

  const handleStorylineClick = (storylineId) => {
    navigate(`/storylines/${storylineId}`);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const TabPanel = ({ children, value, index, ...other }) => (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`discover-tabpanel-${index}`}
      aria-labelledby={`discover-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Discover
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" paragraph>
          Explore trending topics, recent articles, and emerging storylines
        </Typography>

        {/* Search Bar */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <TextField
            fullWidth
            placeholder="Search articles, topics, or storylines..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="contained"
            onClick={handleSearch}
            startIcon={<SearchIcon />}
            sx={{ minWidth: 120 }}
          >
            Search
          </Button>
        </Box>

        {/* Filters */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <FormControl sx={{ minWidth: 120 }}>
            <InputLabel>Category</InputLabel>
            <Select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              label="Category"
            >
              <MenuItem value="">All Categories</MenuItem>
              <MenuItem value="politics">Politics</MenuItem>
              <MenuItem value="business">Business</MenuItem>
              <MenuItem value="technology">Technology</MenuItem>
              <MenuItem value="world">World</MenuItem>
            </Select>
          </FormControl>
          <FormControl sx={{ minWidth: 120 }}>
            <InputLabel>Time</InputLabel>
            <Select
              value={timeFilter}
              onChange={(e) => setTimeFilter(e.target.value)}
              label="Time"
            >
              <MenuItem value="today">Today</MenuItem>
              <MenuItem value="week">This Week</MenuItem>
              <MenuItem value="month">This Month</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="outlined"
            startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
            onClick={() => fetchDiscoverData(true)}
            disabled={loading}
            sx={{ minWidth: 120 }}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Box>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Trending Topics" icon={<TrendingUpIcon />} />
          <Tab label="Recent Articles" icon={<ArticleIcon />} />
          <Tab label="New Storylines" icon={<TimelineIcon />} />
        </Tabs>
      </Box>

      {/* Trending Topics Tab */}
      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          {trendingTopics.length > 0 ? (
            trendingTopics.map((item, index) => (
              <Grid item xs={12} sm={6} md={4} key={index}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="h6" component="h3">
                        {item.topic}
                      </Typography>
                      <Chip 
                        label={`${item.count} articles`} 
                        size="small" 
                        color="primary" 
                        variant="outlined"
                      />
                    </Box>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => {
                        setSearchTerm(item.topic);
                        handleSearch();
                      }}
                      sx={{ mt: 1 }}
                    >
                      View Articles
                    </Button>
                  </CardContent>
                </Card>
              </Grid>
            ))
          ) : (
            <Grid item xs={12}>
              <Alert severity="info">
                No trending topics found. Try refreshing or check back later.
              </Alert>
            </Grid>
          )}
        </Grid>
      </TabPanel>

      {/* Recent Articles Tab */}
      <TabPanel value={activeTab} index={1}>
        {recentArticles.length > 0 ? (
          <List>
            {recentArticles.map((article, index) => (
              <React.Fragment key={article.id}>
                <ListItem
                  button
                  onClick={() => handleArticleClick(article.id)}
                  sx={{ 
                    borderRadius: 1,
                    '&:hover': { backgroundColor: 'action.hover' }
                  }}
                >
                  <ListItemAvatar>
                    <Avatar>
                      <ArticleIcon />
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={article.title}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary" paragraph>
                          {article.summary || article.content?.substring(0, 150) + '...'}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <Chip label={article.source} size="small" variant="outlined" />
                          <Typography variant="caption" color="text.secondary">
                            {formatDate(article.published_date)}
                          </Typography>
                        </Box>
                      </Box>
                    }
                  />
                </ListItem>
                {index < recentArticles.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        ) : (
          <Alert severity="info">
            No recent articles found. Try refreshing or check back later.
          </Alert>
        )}
      </TabPanel>

      {/* New Storylines Tab */}
      <TabPanel value={activeTab} index={2}>
        <Grid container spacing={3}>
          {newStorylines.length > 0 ? (
            newStorylines.map((storyline) => (
              <Grid item xs={12} md={6} key={storyline.story_id}>
                <Card 
                  sx={{ 
                    height: '100%',
                    cursor: 'pointer',
                    '&:hover': { 
                      boxShadow: 4,
                      transform: 'translateY(-2px)',
                      transition: 'all 0.2s ease-in-out'
                    }
                  }}
                  onClick={() => handleStorylineClick(storyline.story_id)}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                      <Typography variant="h6" component="h3">
                        {storyline.name}
                      </Typography>
                      <Chip 
                        label={`Priority ${storyline.priority_level}`} 
                        size="small" 
                        color={storyline.priority_level >= 8 ? 'error' : storyline.priority_level >= 5 ? 'warning' : 'success'}
                      />
                    </Box>
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {storyline.description}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                      {storyline.keywords?.slice(0, 3).map((keyword, index) => (
                        <Chip 
                          key={index}
                          label={keyword} 
                          size="small" 
                          variant="outlined"
                        />
                      ))}
                      {storyline.keywords?.length > 3 && (
                        <Chip 
                          label={`+${storyline.keywords.length - 3}`} 
                          size="small" 
                          variant="outlined"
                        />
                      )}
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      Created: {formatDate(storyline.created_at)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))
          ) : (
            <Grid item xs={12}>
              <Alert severity="info">
                No storylines found. Create your first storyline to get started.
              </Alert>
            </Grid>
          )}
        </Grid>
      </TabPanel>
    </Box>
  );
};

export default Discover;
