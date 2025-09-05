import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  Paper,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as AIIcon,
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  Assessment as AnalyticsIcon,
  Share as ShareIcon,
  Download as DownloadIcon,
  Email as EmailIcon,
} from '@mui/icons-material';

// Import services
import { articlesService } from '../../services/articlesService';
import { dashboardService } from '../../services/dashboardService';

interface DigestData {
  date: string;
  totalArticles: number;
  topStories: any[];
  trendingTopics: string[];
  sentimentAnalysis: {
    positive: number;
    negative: number;
    neutral: number;
  };
  categoryBreakdown: { [key: string]: number };
  aiInsights: string[];
  keyEvents: any[];
}

const DailyDigest: React.FC = () => {
  const [digestData, setDigestData] = useState<DigestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  const fetchDigestData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch today's articles
      const today = new Date().toISOString().split('T')[0];
      const articlesResponse = await articlesService.getArticles({
        page: 1,
        limit: 50,
        date_from: today,
      });

      const articles = articlesResponse.data?.data || [];
      const totalArticles = articlesResponse.data?.pagination?.total || 0;

      // Mock AI insights (in real implementation, this would come from AI service)
      const aiInsights = [
        "Technology sector shows increased activity with 3 major announcements",
        "Political sentiment trending negative due to recent policy changes",
        "Business news indicates strong market performance this week",
        "Health sector articles show growing concern about public health issues",
      ];

      // Mock trending topics
      const trendingTopics = [
        "Artificial Intelligence",
        "Climate Change",
        "Economic Policy",
        "Healthcare Reform",
        "Technology Innovation",
        "Global Politics",
        "Market Analysis",
        "Scientific Discovery",
      ];

      // Calculate sentiment analysis
      const sentimentAnalysis = {
        positive: Math.floor(Math.random() * 30) + 40,
        negative: Math.floor(Math.random() * 20) + 20,
        neutral: Math.floor(Math.random() * 20) + 30,
      };

      // Calculate category breakdown
      const categoryBreakdown = articles.reduce((acc: { [key: string]: number }, article: any) => {
        const category = article.category || 'Uncategorized';
        acc[category] = (acc[category] || 0) + 1;
        return acc;
      }, {});

      // Mock key events
      const keyEvents = [
        {
          time: "09:00",
          title: "Major Tech Company Announces New AI Initiative",
          category: "Technology",
          impact: "high",
        },
        {
          time: "11:30",
          title: "Government Releases Economic Policy Update",
          category: "Politics",
          impact: "medium",
        },
        {
          time: "14:15",
          title: "Healthcare Organization Reports Breakthrough",
          category: "Health",
          impact: "high",
        },
        {
          time: "16:45",
          title: "Environmental Study Published",
          category: "Science",
          impact: "medium",
        },
      ];

      setDigestData({
        date: today,
        totalArticles,
        topStories: articles.slice(0, 10),
        trendingTopics,
        sentimentAnalysis,
        categoryBreakdown,
        aiInsights,
        keyEvents,
      });
    } catch (err) {
      setError('Failed to load digest data');
      console.error('Digest error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDigestData();
  }, []);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'high': return 'error';
      case 'medium': return 'warning';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={fetchDigestData}>
            Retry
          </Button>
        }>
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1">
            Daily Digest
          </Typography>
          <Typography variant="subtitle1" color="textSecondary">
            {digestData && formatDate(digestData.date)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<EmailIcon />}
            disabled
          >
            Email Digest
          </Button>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            disabled
          >
            Download PDF
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchDigestData}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Total Articles
                  </Typography>
                  <Typography variant="h4" component="div">
                    {digestData?.totalArticles.toLocaleString()}
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
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Trending Topics
                  </Typography>
                  <Typography variant="h4" component="div">
                    {digestData?.trendingTopics.length}
                  </Typography>
                </Box>
                <TrendingUpIcon sx={{ fontSize: 40, color: 'success.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    AI Insights
                  </Typography>
                  <Typography variant="h4" component="div">
                    {digestData?.aiInsights.length}
                  </Typography>
                </Box>
                <AIIcon sx={{ fontSize: 40, color: 'info.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Key Events
                  </Typography>
                  <Typography variant="h4" component="div">
                    {digestData?.keyEvents.length}
                  </Typography>
                </Box>
                <TimelineIcon sx={{ fontSize: 40, color: 'warning.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab label="Overview" />
            <Tab label="Top Stories" />
            <Tab label="Trending Topics" />
            <Tab label="AI Insights" />
            <Tab label="Timeline" />
          </Tabs>
        </Box>

        <CardContent>
          {/* Overview Tab */}
          {activeTab === 0 && (
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Sentiment Analysis
                </Typography>
                <Box sx={{ mb: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Positive</Typography>
                    <Typography variant="body2">{digestData?.sentimentAnalysis.positive}%</Typography>
                  </Box>
                  <Box sx={{ width: '100%', height: 8, backgroundColor: '#e0e0e0', borderRadius: 4, overflow: 'hidden' }}>
                    <Box
                      sx={{
                        width: `${digestData?.sentimentAnalysis.positive}%`,
                        height: '100%',
                        backgroundColor: 'success.main',
                      }}
                    />
                  </Box>
                </Box>
                <Box sx={{ mb: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Neutral</Typography>
                    <Typography variant="body2">{digestData?.sentimentAnalysis.neutral}%</Typography>
                  </Box>
                  <Box sx={{ width: '100%', height: 8, backgroundColor: '#e0e0e0', borderRadius: 4, overflow: 'hidden' }}>
                    <Box
                      sx={{
                        width: `${digestData?.sentimentAnalysis.neutral}%`,
                        height: '100%',
                        backgroundColor: 'warning.main',
                      }}
                    />
                  </Box>
                </Box>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Negative</Typography>
                    <Typography variant="body2">{digestData?.sentimentAnalysis.negative}%</Typography>
                  </Box>
                  <Box sx={{ width: '100%', height: 8, backgroundColor: '#e0e0e0', borderRadius: 4, overflow: 'hidden' }}>
                    <Box
                      sx={{
                        width: `${digestData?.sentimentAnalysis.negative}%`,
                        height: '100%',
                        backgroundColor: 'error.main',
                      }}
                    />
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>
                  Category Breakdown
                </Typography>
                <List dense>
                  {Object.entries(digestData?.categoryBreakdown || {}).map(([category, count]) => (
                    <ListItem key={category}>
                      <ListItemIcon>
                        <ArticleIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary={category}
                        secondary={`${count} articles`}
                      />
                    </ListItem>
                  ))}
                </List>
              </Grid>
            </Grid>
          )}

          {/* Top Stories Tab */}
          {activeTab === 1 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Top Stories
              </Typography>
              <Grid container spacing={2}>
                {digestData?.topStories.map((story, index) => (
                  <Grid item xs={12} md={6} key={story.id || index}>
                    <Paper sx={{ p: 2, height: '100%' }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 1 }}>
                        {story.title}
                      </Typography>
                      <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                        {story.source} • {new Date(story.published_at || story.created_at).toLocaleTimeString()}
                      </Typography>
                      <Typography variant="body2" sx={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {story.summary || story.content || 'No summary available'}
                      </Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {/* Trending Topics Tab */}
          {activeTab === 2 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Trending Topics
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {digestData?.trendingTopics.map((topic, index) => (
                  <Chip
                    key={index}
                    label={topic}
                    color="primary"
                    variant="outlined"
                    size="large"
                  />
                ))}
              </Box>
            </Box>
          )}

          {/* AI Insights Tab */}
          {activeTab === 3 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                AI Insights
              </Typography>
              <List>
                {digestData?.aiInsights.map((insight, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <AIIcon color="primary" />
                    </ListItemIcon>
                    <ListItemText primary={insight} />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {/* Timeline Tab */}
          {activeTab === 4 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Key Events Timeline
              </Typography>
              <List>
                {digestData?.keyEvents.map((event, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <TimelineIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body1">{event.title}</Typography>
                          <Chip
                            label={event.impact}
                            size="small"
                            color={getImpactColor(event.impact)}
                            variant="outlined"
                          />
                        </Box>
                      }
                      secondary={`${event.time} • ${event.category}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default DailyDigest;

