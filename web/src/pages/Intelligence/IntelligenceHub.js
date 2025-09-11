import React, { useState } from 'react';
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
  Badge
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
  BookmarkBorder as BookmarkBorderIcon
} from '@mui/icons-material';
import { apiService } from '../../services/apiService';

const IntelligenceHub = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [bookmarkedItems, setBookmarkedItems] = useState(new Set());

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
          <IconButton onClick={() => setLoading(true)} disabled={loading}>
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
              <List>
                <ListItem>
                  <ListItemIcon>
                    <ArticleIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Top Story"
                    secondary="Breaking news and major developments from overnight"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <TrendingUpIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Trending Topics"
                    secondary="Most discussed topics and emerging stories"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <TimelineIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Storyline Updates"
                    secondary="Latest developments in ongoing storylines"
                  />
                </ListItem>
              </List>
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
              <Button variant="outlined" startIcon={<AutoAwesomeIcon />}>
                Generate Briefing
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  // Discover Tab
  const DiscoverTab = () => (
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
            </Select>
          </FormControl>
        </Box>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recommended Articles
            </Typography>
            <List>
              {[1, 2, 3].map((item) => (
                <ListItem key={item} divider>
                  <ListItemText
                    primary={`Sample Article ${item}`}
                    secondary={truncateText("This is a sample article description that would be populated with real content from the news intelligence system.")}
                  />
                  <Box display="flex" gap={1}>
                    <IconButton size="small">
                      <BookmarkBorderIcon />
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
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Discovery Features
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Button variant="outlined" startIcon={<AutoAwesomeIcon />}>
                  AI-Powered Search
                </Button>
                <Button variant="outlined" startIcon={<TrendingUpIcon />}>
                  Trending Topics
                </Button>
                <Button variant="outlined" startIcon={<GroupIcon />}>
                  Topic Clusters
                </Button>
                <Button variant="outlined" startIcon={<TimelineIcon />}>
                  Related Stories
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  // Trends Tab
  const TrendsTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Trends Analysis
        </Typography>
        <Tooltip title="Refresh Trends">
          <IconButton onClick={() => setLoading(true)} disabled={loading}>
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
              <Box display="flex" flexWrap="wrap" gap={1} mb={2}>
                <Chip label="Technology" color="primary" />
                <Chip label="Politics" color="secondary" />
                <Chip label="Business" color="info" />
                <Chip label="Health" color="success" />
              </Box>
              <Typography variant="body2" color="text.secondary">
                Topics ranked by engagement and discussion volume over the past 24 hours.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Sentiment Trends
              </Typography>
              <Box display="flex" justifyContent="space-between" mb={2}>
                <Box textAlign="center">
                  <Typography variant="h4" color="success.main">65%</Typography>
                  <Typography variant="caption">Positive</Typography>
                </Box>
                <Box textAlign="center">
                  <Typography variant="h4" color="error.main">20%</Typography>
                  <Typography variant="caption">Negative</Typography>
                </Box>
                <Box textAlign="center">
                  <Typography variant="h4" color="info.main">15%</Typography>
                  <Typography variant="caption">Neutral</Typography>
                </Box>
              </Box>
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

  // Clusters Tab
  const ClustersTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          <GroupIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Topic Clusters
        </Typography>
        <Tooltip title="Refresh Clusters">
          <IconButton onClick={() => setLoading(true)} disabled={loading}>
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
              <List>
                <ListItem>
                  <ListItemIcon>
                    <ArticleIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Technology Innovation"
                    secondary="15 articles • 3 storylines"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <ArticleIcon color="secondary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Economic Policy"
                    secondary="12 articles • 2 storylines"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <ArticleIcon color="info" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Climate Change"
                    secondary="8 articles • 1 storyline"
                  />
                </ListItem>
              </List>
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
              <Box display="flex" flexDirection="column" gap={1}>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Cluster Quality</Typography>
                  <Typography variant="body2" color="primary">92%</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Topic Diversity</Typography>
                  <Typography variant="body2" color="primary">87%</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Story Coherence</Typography>
                  <Typography variant="body2" color="primary">94%</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  // AI Analysis Tab
  const AIAnalysisTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          AI Analysis
        </Typography>
        <Tooltip title="Refresh Analysis">
          <IconButton onClick={() => setLoading(true)} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <AutoAwesomeIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Multi-Perspective Analysis
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Analyze news from multiple viewpoints and sources to provide balanced insights.
              </Typography>
              <Button variant="outlined" fullWidth>
                Run Analysis
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
              <Button variant="outlined" fullWidth>
                Assess Impact
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <HistoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Historical Context
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Connect current events to historical patterns and precedents.
              </Typography>
              <Button variant="outlined" fullWidth>
                Add Context
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <PredictionIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Predictive Analysis
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Forecast future developments and trends based on current data patterns.
              </Typography>
              <Button variant="outlined" fullWidth>
                Generate Predictions
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
              <Button variant="outlined" fullWidth>
                Request Analysis
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
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
    </Box>
  );
};

export default IntelligenceHub;
