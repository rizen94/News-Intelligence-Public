import {
  Psychology as PsychologyIcon,
  TrendingUp as TrendingUpIcon,
  Assessment as AssessmentIcon,
  Timeline as TimelineIcon,
  AutoAwesome as AutoAwesomeIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Analytics,
  Insights as InsightsIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Refresh,
  FilterList,
  Search,
  Download as DownloadIcon,
  Share as ShareIcon,
  Bookmark,
  Star as StarIcon,
  Flag as FlagIcon,
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
  Tabs,
  Tab,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../../services/apiService.ts';

const Intelligence = () => {
  const [intelligenceData, setIntelligenceData] = useState({
    insights: [],
    trends: [],
    patterns: [],
    anomalies: [],
    recommendations: [],
    biasAnalysis: { left: 0, center: 0, right: 0, total: 0 },
    sentimentAnalysis: { positive: 0, neutral: 0, negative: 0, total: 0 },
    topicClusters: [],
    entityAnalysis: [],
    timelineEvents: [],
  });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [timeRange, setTimeRange] = useState('7d');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [selectedInsight, setSelectedInsight] = useState(null);
  const [insightDialogOpen, setInsightDialogOpen] = useState(false);

  const fetchIntelligenceData = useCallback(async() => {
    try {
      setLoading(true);

      // Fetch intelligence data from multiple sources
      const [articlesRes, storylinesRes, feedsRes] = await Promise.all([
        apiService.articles.getArticles({ limit: 100 }),
        apiService.storylines.getStorylines({ limit: 50 }),
        apiService.rssFeeds.getFeeds(),
      ]);

      // Generate insights from the data
      const articles = articlesRes.data?.articles || [];
      const storylines = storylinesRes.data?.storylines || [];
      const feeds = feedsRes.data?.feeds || [];

      // Bias analysis
      const biasAnalysis = {
        left: articles.filter(a => a.bias_score < -0.3).length,
        center: articles.filter(a => Math.abs(a.bias_score) <= 0.3).length,
        right: articles.filter(a => a.bias_score > 0.3).length,
        total: articles.length,
      };

      // Sentiment analysis (simulated)
      const sentimentAnalysis = {
        positive: Math.floor(articles.length * 0.4),
        neutral: Math.floor(articles.length * 0.3),
        negative: Math.floor(articles.length * 0.3),
        total: articles.length,
      };

      // Generate insights
      const insights = [
        {
          id: 1,
          title: 'Political Bias Shift Detected',
          description:
            'Recent articles show a 15% increase in left-leaning content',
          type: 'trend',
          severity: 'medium',
          confidence: 0.85,
          timestamp: new Date(),
          sources: articles.slice(0, 5).map(a => a.source),
          recommendations: ['Monitor source diversity', 'Adjust feed weights'],
        },
        {
          id: 2,
          title: 'Breaking News Cluster',
          description: 'High volume of articles on a single topic detected',
          type: 'pattern',
          severity: 'high',
          confidence: 0.92,
          timestamp: new Date(),
          sources: articles.slice(0, 3).map(a => a.source),
          recommendations: ['Create storyline', 'Set up alerts'],
        },
        {
          id: 3,
          title: 'Source Reliability Alert',
          description: 'Multiple sources reporting conflicting information',
          type: 'anomaly',
          severity: 'high',
          confidence: 0.78,
          timestamp: new Date(),
          sources: articles.slice(0, 4).map(a => a.source),
          recommendations: ['Verify sources', 'Cross-reference data'],
        },
      ];

      // Generate trends
      const trends = [
        {
          name: 'Political Coverage',
          change: 12.5,
          direction: 'up',
          articles: 45,
        },
        {
          name: 'Technology News',
          change: -8.2,
          direction: 'down',
          articles: 32,
        },
        {
          name: 'Economic Analysis',
          change: 5.7,
          direction: 'up',
          articles: 28,
        },
        {
          name: 'International Affairs',
          change: 15.3,
          direction: 'up',
          articles: 38,
        },
      ];

      // Generate patterns
      const patterns = [
        {
          pattern: 'Peak Activity',
          time: '09:00-11:00',
          frequency: 'Daily',
          confidence: 0.89,
        },
        {
          pattern: 'Source Correlation',
          sources: ['CNN', 'BBC'],
          correlation: 0.76,
        },
        {
          pattern: 'Topic Clustering',
          topics: ['Politics', 'Economy'],
          frequency: 'Weekly',
        },
      ];

      // Generate anomalies
      const anomalies = [
        {
          type: 'Volume Spike',
          description: 'Article volume increased 300%',
          severity: 'high',
          timestamp: new Date(),
        },
        {
          type: 'Source Error',
          description: 'RSS feed returning errors',
          severity: 'medium',
          timestamp: new Date(),
        },
        {
          type: 'Bias Shift',
          description: 'Unusual bias pattern detected',
          severity: 'low',
          timestamp: new Date(),
        },
      ];

      // Generate recommendations
      const recommendations = [
        {
          action: 'Add new RSS feeds',
          priority: 'high',
          impact: 'Increase source diversity',
        },
        {
          action: 'Adjust ML model parameters',
          priority: 'medium',
          impact: 'Improve accuracy',
        },
        {
          action: 'Update bias detection algorithm',
          priority: 'low',
          impact: 'Better bias analysis',
        },
      ];

      // Generate topic clusters
      const topicClusters = [
        {
          name: 'Political Coverage',
          size: 45,
          keywords: ['election', 'policy', 'government'],
          sentiment: 'neutral',
        },
        {
          name: 'Technology',
          size: 32,
          keywords: ['AI', 'tech', 'innovation'],
          sentiment: 'positive',
        },
        {
          name: 'Economy',
          size: 28,
          keywords: ['market', 'economy', 'finance'],
          sentiment: 'negative',
        },
        {
          name: 'International',
          size: 38,
          keywords: ['global', 'international', 'world'],
          sentiment: 'neutral',
        },
      ];

      // Generate entity analysis
      const entityAnalysis = [
        { entity: 'Joe Biden', mentions: 25, sentiment: 'neutral', sources: 8 },
        {
          entity: 'Donald Trump',
          mentions: 18,
          sentiment: 'negative',
          sources: 6,
        },
        {
          entity: 'Federal Reserve',
          mentions: 12,
          sentiment: 'negative',
          sources: 4,
        },
        { entity: 'Tesla', mentions: 15, sentiment: 'positive', sources: 5 },
      ];

      // Generate timeline events
      const timelineEvents = [
        { time: '2024-01-01', event: 'System initialized', type: 'system' },
        {
          time: '2024-01-02',
          event: 'First articles processed',
          type: 'milestone',
        },
        { time: '2024-01-03', event: 'ML model trained', type: 'ml' },
        { time: '2024-01-04', event: 'Bias analysis enabled', type: 'feature' },
      ];

      setIntelligenceData({
        insights,
        trends,
        patterns,
        anomalies,
        recommendations,
        biasAnalysis,
        sentimentAnalysis,
        topicClusters,
        entityAnalysis,
        timelineEvents,
      });
    } catch (error) {
      console.error('Error fetching intelligence data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIntelligenceData();
  }, [fetchIntelligenceData]);

  const getSeverityColor = severity => {
    switch (severity) {
    case 'high':
      return 'error';
    case 'medium':
      return 'warning';
    case 'low':
      return 'info';
    default:
      return 'default';
    }
  };

  const getSeverityIcon = severity => {
    switch (severity) {
    case 'high':
      return <ErrorIcon />;
    case 'medium':
      return <WarningIcon />;
    case 'low':
      return <InfoIcon />;
    default:
      return <CheckCircleIcon />;
    }
  };

  const getTrendIcon = direction => {
    return direction === 'up' ? <TrendingUpIcon /> : <TrendingUpIcon />;
  };

  const getTrendColor = direction => {
    return direction === 'up' ? 'success' : 'error';
  };

  const handleViewInsight = insight => {
    setSelectedInsight(insight);
    setInsightDialogOpen(true);
  };

  const TabPanel = ({ children, value, index, ...other }) => (
    <div
      role='tabpanel'
      hidden={value !== index}
      id={`intelligence-tabpanel-${index}`}
      aria-labelledby={`intelligence-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
          🧠 Intelligence Hub
        </Typography>
        <Box display='flex' gap={1}>
          <FormControl size='small' sx={{ minWidth: 120 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={timeRange}
              onChange={e => setTimeRange(e.target.value)}
              label='Time Range'
            >
              <MenuItem value='1d'>Last 24h</MenuItem>
              <MenuItem value='7d'>Last 7 days</MenuItem>
              <MenuItem value='30d'>Last 30 days</MenuItem>
              <MenuItem value='90d'>Last 90 days</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant='outlined'
            startIcon={<Refresh />}
            onClick={fetchIntelligenceData}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {/* Overview Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='primary'>
                {intelligenceData.insights.length}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Active Insights
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='warning'>
                {intelligenceData.anomalies.length}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Anomalies Detected
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='info'>
                {intelligenceData.recommendations.length}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Recommendations
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='success'>
                {intelligenceData.topicClusters.length}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Topic Clusters
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Main Content Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={activeTab}
            onChange={(e, newValue) => setActiveTab(newValue)}
          >
            <Tab label='Insights' icon={<InsightsIcon />} />
            <Tab label='Trends' icon={<TrendingUpIcon />} />
            <Tab label='Patterns' icon={<AssessmentIcon />} />
            <Tab label='Anomalies' icon={<WarningIcon />} />
            <Tab label='Recommendations' icon={<AutoAwesomeIcon />} />
            <Tab label='Analysis' icon={<Analytics />} />
          </Tabs>
        </Box>

        {/* Insights Tab */}
        <TabPanel value={activeTab} index={0}>
          <Typography variant='h6' sx={{ mb: 2 }}>
            🔍 Key Insights
          </Typography>
          <Grid container spacing={2}>
            {intelligenceData.insights.map(insight => (
              <Grid item xs={12} md={6} key={insight.id}>
                <Card>
                  <CardContent>
                    <Box
                      display='flex'
                      justifyContent='space-between'
                      alignItems='flex-start'
                      mb={2}
                    >
                      <Typography variant='h6'>{insight.title}</Typography>
                      <Chip
                        icon={getSeverityIcon(insight.severity)}
                        label={insight.severity}
                        color={getSeverityColor(insight.severity)}
                        size='small'
                      />
                    </Box>
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mb: 2 }}
                    >
                      {insight.description}
                    </Typography>
                    <Box display='flex' alignItems='center' gap={1} mb={2}>
                      <Typography variant='caption'>Confidence:</Typography>
                      <LinearProgress
                        variant='determinate'
                        value={insight.confidence * 100}
                        sx={{ flex: 1 }}
                      />
                      <Typography variant='caption'>
                        {(insight.confidence * 100).toFixed(0)}%
                      </Typography>
                    </Box>
                    <Button
                      size='small'
                      onClick={() => handleViewInsight(insight)}
                    >
                      View Details
                    </Button>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </TabPanel>

        {/* Trends Tab */}
        <TabPanel value={activeTab} index={1}>
          <Typography variant='h6' sx={{ mb: 2 }}>
            📈 Content Trends
          </Typography>
          <Grid container spacing={2}>
            {intelligenceData.trends.map((trend, index) => (
              <Grid item xs={12} md={6} key={index}>
                <Card>
                  <CardContent>
                    <Box
                      display='flex'
                      justifyContent='space-between'
                      alignItems='center'
                      mb={1}
                    >
                      <Typography variant='h6'>{trend.name}</Typography>
                      <Box display='flex' alignItems='center' gap={1}>
                        {getTrendIcon(trend.direction)}
                        <Typography
                          variant='h6'
                          color={getTrendColor(trend.direction)}
                        >
                          {trend.change > 0 ? '+' : ''}
                          {trend.change}%
                        </Typography>
                      </Box>
                    </Box>
                    <Typography variant='body2' color='text.secondary'>
                      {trend.articles} articles
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </TabPanel>

        {/* Patterns Tab */}
        <TabPanel value={activeTab} index={2}>
          <Typography variant='h6' sx={{ mb: 2 }}>
            🔍 Detected Patterns
          </Typography>
          <List>
            {intelligenceData.patterns.map((pattern, index) => (
              <ListItem key={index} divider>
                <ListItemIcon>
                  <AssessmentIcon />
                </ListItemIcon>
                <ListItemText
                  primary={pattern.pattern}
                  secondary={
                    <Box>
                      <Typography variant='body2'>
                        {pattern.time && `Time: ${pattern.time}`}
                        {pattern.frequency &&
                          ` | Frequency: ${pattern.frequency}`}
                        {pattern.sources &&
                          ` | Sources: ${pattern.sources.join(', ')}`}
                        {pattern.topics &&
                          ` | Topics: ${pattern.topics.join(', ')}`}
                      </Typography>
                      {pattern.confidence && (
                        <Box mt={1}>
                          <Typography variant='caption'>
                            Confidence: {pattern.confidence}
                          </Typography>
                          <LinearProgress
                            variant='determinate'
                            value={pattern.confidence * 100}
                            size='small'
                          />
                        </Box>
                      )}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* Anomalies Tab */}
        <TabPanel value={activeTab} index={3}>
          <Typography variant='h6' sx={{ mb: 2 }}>
            ⚠️ System Anomalies
          </Typography>
          <List>
            {intelligenceData.anomalies.map((anomaly, index) => (
              <ListItem key={index} divider>
                <ListItemIcon>
                  <WarningIcon color={getSeverityColor(anomaly.severity)} />
                </ListItemIcon>
                <ListItemText
                  primary={anomaly.type}
                  secondary={
                    <Box>
                      <Typography variant='body2'>
                        {anomaly.description}
                      </Typography>
                      <Typography variant='caption' color='text.secondary'>
                        {anomaly.timestamp.toLocaleString()}
                      </Typography>
                    </Box>
                  }
                />
                <Chip
                  label={anomaly.severity}
                  color={getSeverityColor(anomaly.severity)}
                  size='small'
                />
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* Recommendations Tab */}
        <TabPanel value={activeTab} index={4}>
          <Typography variant='h6' sx={{ mb: 2 }}>
            💡 AI Recommendations
          </Typography>
          <List>
            {intelligenceData.recommendations.map((rec, index) => (
              <ListItem key={index} divider>
                <ListItemIcon>
                  <AutoAwesomeIcon />
                </ListItemIcon>
                <ListItemText
                  primary={rec.action}
                  secondary={
                    <Box>
                      <Typography variant='body2'>{rec.impact}</Typography>
                      <Chip
                        label={rec.priority}
                        color={getSeverityColor(rec.priority)}
                        size='small'
                        sx={{ mt: 1 }}
                      />
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* Analysis Tab */}
        <TabPanel value={activeTab} index={5}>
          <Typography variant='h6' sx={{ mb: 2 }}>
            📊 Advanced Analysis
          </Typography>

          {/* Bias Analysis */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant='h6' sx={{ mb: 2 }}>
                Political Bias Distribution
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={4}>
                  <Typography variant='h4' color='error'>
                    {intelligenceData.biasAnalysis.left}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Left Bias
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant='h4' color='success'>
                    {intelligenceData.biasAnalysis.center}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Center
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant='h4' color='warning'>
                    {intelligenceData.biasAnalysis.right}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Right Bias
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          {/* Sentiment Analysis */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant='h6' sx={{ mb: 2 }}>
                Sentiment Analysis
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={4}>
                  <Typography variant='h4' color='success'>
                    {intelligenceData.sentimentAnalysis.positive}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Positive
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant='h4' color='info'>
                    {intelligenceData.sentimentAnalysis.neutral}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Neutral
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant='h4' color='error'>
                    {intelligenceData.sentimentAnalysis.negative}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Negative
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          {/* Topic Clusters */}
          <Card>
            <CardContent>
              <Typography variant='h6' sx={{ mb: 2 }}>
                Topic Clusters
              </Typography>
              <Grid container spacing={2}>
                {intelligenceData.topicClusters.map((cluster, index) => (
                  <Grid item xs={12} md={6} key={index}>
                    <Paper sx={{ p: 2 }}>
                      <Typography variant='h6'>{cluster.name}</Typography>
                      <Typography
                        variant='body2'
                        color='text.secondary'
                        sx={{ mb: 1 }}
                      >
                        {cluster.size} articles
                      </Typography>
                      <Box display='flex' gap={1} mb={1}>
                        {cluster.keywords.map((keyword, i) => (
                          <Chip key={i} label={keyword} size='small' />
                        ))}
                      </Box>
                      <Chip
                        label={cluster.sentiment}
                        color={
                          cluster.sentiment === 'positive'
                            ? 'success'
                            : cluster.sentiment === 'negative'
                              ? 'error'
                              : 'info'
                        }
                        size='small'
                      />
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </TabPanel>
      </Card>

      {/* Insight Detail Dialog */}
      <Dialog
        open={insightDialogOpen}
        onClose={() => setInsightDialogOpen(false)}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>{selectedInsight?.title}</DialogTitle>
        <DialogContent>
          {selectedInsight && (
            <Box>
              <Typography variant='body1' sx={{ mb: 2 }}>
                {selectedInsight.description}
              </Typography>
              <Typography variant='h6' sx={{ mb: 1 }}>
                Sources
              </Typography>
              <Box display='flex' gap={1} mb={2}>
                {selectedInsight.sources.map((source, index) => (
                  <Chip key={index} label={source} size='small' />
                ))}
              </Box>
              <Typography variant='h6' sx={{ mb: 1 }}>
                Recommendations
              </Typography>
              <List>
                {selectedInsight.recommendations.map((rec, index) => (
                  <ListItem key={index}>
                    <ListItemText primary={rec} />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInsightDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Intelligence;
