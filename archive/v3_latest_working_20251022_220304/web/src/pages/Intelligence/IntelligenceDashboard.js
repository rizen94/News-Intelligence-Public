import {
  Psychology as PsychologyIcon,
  TrendingUp as TrendingUpIcon,
  Notifications as NotificationsIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh,
  AutoAwesome as AutoAwesomeIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
  Insights as InsightsIcon,
  Analytics,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Search,
  FilterList,
  Download as DownloadIcon,
  Share as ShareIcon,
  Visibility,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
  Security as SecurityIcon,
  Public as PublicIcon,
  Business as BusinessIcon,
  Person as PersonIcon,
  LocationOn as LocationIcon,
  Schedule,
  Star as StarIcon,
  Flag as FlagIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Button,
  Tabs,
  Tab,
  Badge,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Avatar,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  InputAdornment,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import { newsSystemService } from '../../services/newsSystemService';

const IntelligenceDashboard = () => {
  const [insights, setInsights] = useState([]);
  const [trends, setTrends] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [filterCategory, setFilterCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [timeRange, setTimeRange] = useState('24h');

  useEffect(() => {
    fetchIntelligenceData();
    const interval = setInterval(fetchIntelligenceData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [timeRange]);

  const fetchIntelligenceData = async() => {
    try {
      setRefreshing(true);
      setError(null);

      const [insightsData, trendsData, alertsData] = await Promise.allSettled([
        newsSystemService.getIntelligenceInsights(filterCategory, 50),
        newsSystemService.getIntelligenceTrends(),
        newsSystemService.getIntelligenceAlerts(),
      ]);

      if (insightsData.status === 'fulfilled') {
        setInsights(insightsData.value.insights || []);
      }
      if (trendsData.status === 'fulfilled') {
        setTrends(trendsData.value.trends || []);
      }
      if (alertsData.status === 'fulfilled') {
        setAlerts(alertsData.value.alerts || []);
      }

      setLoading(false);
    } catch (err) {
      console.error('Error fetching intelligence data:', err);
      setError(err.message);
      setLoading(false);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    fetchIntelligenceData();
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const getInsightIcon = (category) => {
    switch (category?.toLowerCase()) {
    case 'security': return <SecurityIcon />;
    case 'business': return <BusinessIcon />;
    case 'politics': return <PublicIcon />;
    case 'technology': return <PsychologyIcon />;
    case 'trending': return <TrendingUpIcon />;
    default: return <InsightsIcon />;
    }
  };

  const getInsightColor = (confidence) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'error';
  };

  const getTrendIcon = (direction) => {
    switch (direction) {
    case 'up': return <TrendingUpIcon color="success" />;
    case 'down': return <TrendingDownIcon color="error" />;
    default: return <TrendingFlatIcon color="default" />;
    }
  };

  const getAlertSeverity = (severity) => {
    switch (severity?.toLowerCase()) {
    case 'critical': return { color: 'error', icon: <ErrorIcon /> };
    case 'high': return { color: 'warning', icon: <WarningIcon /> };
    case 'medium': return { color: 'info', icon: <NotificationsIcon /> };
    case 'low': return { color: 'success', icon: <CheckCircleIcon /> };
    default: return { color: 'default', icon: <NotificationsIcon /> };
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatConfidence = (confidence) => {
    return `${(confidence * 100).toFixed(1)}%`;
  };

  const filteredInsights = insights.filter(insight => {
    const matchesCategory = !filterCategory || insight.category === filterCategory;
    const matchesSearch = !searchQuery ||
      insight.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      insight.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const getCategoryStats = () => {
    const stats = {};
    insights.forEach(insight => {
      stats[insight.category] = (stats[insight.category] || 0) + 1;
    });
    return stats;
  };

  const categoryStats = getCategoryStats();

  if (loading && insights.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" ml={2}>
          Loading intelligence data...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" size="small" onClick={handleRefresh}>
          Retry
        </Button>
      }>
        Error loading intelligence data: {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Intelligence Dashboard
          </Typography>
          <Typography variant="subtitle1" color="textSecondary">
            AI-powered insights, trends, and alerts from news analysis
          </Typography>
        </Box>
        <Box display="flex" gap={2}>
          <Tooltip title="Refresh Intelligence Data">
            <IconButton onClick={handleRefresh} disabled={refreshing}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            size="small"
          >
            Export
          </Button>
          <Button
            variant="contained"
            startIcon={<ShareIcon />}
            size="small"
          >
            Share
          </Button>
        </Box>
      </Box>

      {/* Key Metrics */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Total Insights
                  </Typography>
                  <Typography variant="h4" component="h2" color="primary">
                    {insights.length}
                  </Typography>
                  <Typography color="textSecondary" variant="body2">
                    {insights.filter(i => i.confidence >= 0.8).length} high confidence
                  </Typography>
                </Box>
                <Box color="primary.main">
                  <InsightsIcon sx={{ fontSize: 40 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Active Trends
                  </Typography>
                  <Typography variant="h4" component="h2" color="secondary">
                    {trends.length}
                  </Typography>
                  <Typography color="textSecondary" variant="body2">
                    {trends.filter(t => t.direction === 'up').length} trending up
                  </Typography>
                </Box>
                <Box color="secondary.main">
                  <TrendingUpIcon sx={{ fontSize: 40 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Active Alerts
                  </Typography>
                  <Typography variant="h4" component="h2" color="error">
                    {alerts.length}
                  </Typography>
                  <Typography color="textSecondary" variant="body2">
                    {alerts.filter(a => a.severity === 'critical').length} critical
                  </Typography>
                </Box>
                <Box color="error.main">
                  <NotificationsIcon sx={{ fontSize: 40 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Categories
                  </Typography>
                  <Typography variant="h4" component="h2" color="info">
                    {Object.keys(categoryStats).length}
                  </Typography>
                  <Typography color="textSecondary" variant="body2">
                    {Object.keys(categoryStats).join(', ')}
                  </Typography>
                </Box>
                <Box color="info.main">
                  <AssessmentIcon sx={{ fontSize: 40 }} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Search insights"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />,
              }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={filterCategory}
                label="Category"
                onChange={(e) => setFilterCategory(e.target.value)}
              >
                <MenuItem value="">All Categories</MenuItem>
                {Object.keys(categoryStats).map(category => (
                  <MenuItem key={category} value={category}>
                    {category} ({categoryStats[category]})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Time Range</InputLabel>
              <Select
                value={timeRange}
                label="Time Range"
                onChange={(e) => setTimeRange(e.target.value)}
              >
                <MenuItem value="1h">Last Hour</MenuItem>
                <MenuItem value="24h">Last 24 Hours</MenuItem>
                <MenuItem value="7d">Last 7 Days</MenuItem>
                <MenuItem value="30d">Last 30 Days</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="contained"
              startIcon={<FilterList />}
              onClick={handleRefresh}
              disabled={refreshing}
            >
              Apply
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Insights" icon={<InsightsIcon />} />
          <Tab label="Trends" icon={<TrendingUpIcon />} />
          <Tab label="Alerts" icon={<NotificationsIcon />} />
          <Tab label="Analytics" icon={<Analytics />} />
        </Tabs>
      </Box>

      {/* Insights Tab */}
      {activeTab === 0 && (
        <Box>
          <Grid container spacing={3}>
            {filteredInsights.map((insight, index) => (
              <Grid item xs={12} md={6} lg={4} key={index}>
                <Card sx={{ height: '100%' }}>
                  <CardHeader
                    avatar={
                      <Avatar sx={{ bgcolor: getInsightColor(insight.confidence) + '.main' }}>
                        {getInsightIcon(insight.category)}
                      </Avatar>
                    }
                    title={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="h6" noWrap>
                          {insight.title}
                        </Typography>
                        <Chip
                          label={formatConfidence(insight.confidence)}
                          color={getInsightColor(insight.confidence)}
                          size="small"
                        />
                      </Box>
                    }
                    subheader={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Chip label={insight.category} size="small" variant="outlined" />
                        <Typography variant="caption" color="textSecondary">
                          {formatDate(insight.created_at)}
                        </Typography>
                      </Box>
                    }
                    action={
                      <IconButton size="small">
                        <Visibility />
                      </IconButton>
                    }
                  />
                  <CardContent>
                    <Typography variant="body2" color="textSecondary" paragraph>
                      {insight.description}
                    </Typography>
                    {insight.data && Object.keys(insight.data).length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" gutterBottom>
                          Key Data:
                        </Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap">
                          {Object.entries(insight.data).slice(0, 3).map(([key, value]) => (
                            <Chip
                              key={key}
                              label={`${key}: ${value}`}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                        </Stack>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
          {filteredInsights.length === 0 && (
            <Box textAlign="center" py={4}>
              <InsightsIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="textSecondary">
                No insights found
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Try adjusting your filters or search criteria
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Trends Tab */}
      {activeTab === 1 && (
        <Box>
          <Grid container spacing={3}>
            {trends.map((trend, index) => (
              <Grid item xs={12} md={6} key={index}>
                <Card>
                  <CardContent>
                    <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                      <Typography variant="h6">{trend.name}</Typography>
                      {getTrendIcon(trend.direction)}
                    </Box>
                    <Typography variant="body2" color="textSecondary" paragraph>
                      {trend.description}
                    </Typography>
                    <Box display="flex" alignItems="center" gap={2}>
                      <Chip
                        label={`${trend.change}%`}
                        color={trend.direction === 'up' ? 'success' : trend.direction === 'down' ? 'error' : 'default'}
                        size="small"
                      />
                      <Typography variant="caption" color="textSecondary">
                        {formatDate(trend.updated_at)}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
          {trends.length === 0 && (
            <Box textAlign="center" py={4}>
              <TrendingUpIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="textSecondary">
                No trends available
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Trends will appear as patterns are detected in the news data
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Alerts Tab */}
      {activeTab === 2 && (
        <Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Severity</TableCell>
                  <TableCell>Alert</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {alerts.map((alert, index) => {
                  const severity = getAlertSeverity(alert.severity);
                  return (
                    <TableRow key={index}>
                      <TableCell>
                        <Chip
                          icon={severity.icon}
                          label={alert.severity}
                          color={severity.color}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {alert.title}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {alert.description}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={alert.category} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{alert.source}</TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {formatDate(alert.timestamp)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <IconButton size="small">
                          <Visibility />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
          {alerts.length === 0 && (
            <Box textAlign="center" py={4}>
              <CheckCircleIcon sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
              <Typography variant="h6" color="textSecondary">
                No active alerts
              </Typography>
              <Typography variant="body2" color="textSecondary">
                All systems are operating normally
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Analytics Tab */}
      {activeTab === 3 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Insights by Category" />
                <CardContent>
                  <List>
                    {Object.entries(categoryStats).map(([category, count]) => (
                      <ListItem key={category}>
                        <ListItemIcon>
                          {getInsightIcon(category)}
                        </ListItemIcon>
                        <ListItemText
                          primary={category}
                          secondary={`${count} insights`}
                        />
                        <LinearProgress
                          variant="determinate"
                          value={(count / Math.max(...Object.values(categoryStats))) * 100}
                          sx={{ width: 100 }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Confidence Distribution" />
                <CardContent>
                  <Box display="flex" flexDirection="column" gap={2}>
                    <Box>
                      <Box display="flex" justifyContent="space-between" mb={1}>
                        <Typography variant="body2">High (80%+)</Typography>
                        <Typography variant="body2">
                          {insights.filter(i => i.confidence >= 0.8).length}
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={(insights.filter(i => i.confidence >= 0.8).length / insights.length) * 100}
                        color="success"
                      />
                    </Box>
                    <Box>
                      <Box display="flex" justifyContent="space-between" mb={1}>
                        <Typography variant="body2">Medium (60-80%)</Typography>
                        <Typography variant="body2">
                          {insights.filter(i => i.confidence >= 0.6 && i.confidence < 0.8).length}
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={(insights.filter(i => i.confidence >= 0.6 && i.confidence < 0.8).length / insights.length) * 100}
                        color="warning"
                      />
                    </Box>
                    <Box>
                      <Box display="flex" justifyContent="space-between" mb={1}>
                        <Typography variant="body2">Low (&lt;60%)</Typography>
                        <Typography variant="body2">
                          {insights.filter(i => i.confidence < 0.6).length}
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={(insights.filter(i => i.confidence < 0.6).length / insights.length) * 100}
                        color="error"
                      />
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default IntelligenceDashboard;
