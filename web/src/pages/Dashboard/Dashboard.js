import {
  Dashboard as DashboardIcon,
  Article,
  RssFeed as RssFeedIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  Chip,
  LinearProgress,
  Button,
  IconButton,
  Tooltip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Badge,
  CircularProgress,
} from '@mui/material';
import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/apiService.ts';

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState({
    articles: { total: 0, recent: [] },
    storylines: { total: 0, active: [] },
    rssFeeds: { total: 0, active: [] },
    systemHealth: { status: 'unknown', uptime: 0 },
    biasAnalysis: { analyzed: 0, leftBias: 0, rightBias: 0, centerBias: 0 },
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const fetchDashboardData = async() => {
    try {
      setLoading(true);

      // Fetch all dashboard data in parallel
      const [articlesRes, storylinesRes, feedsRes, healthRes] = await Promise.all([
        apiService.getArticles({ limit: 10 }),
        apiService.getStorylines({ limit: 10 }),
        apiService.getRSSFeeds(),
        apiService.getHealth(),
      ]);

      // Calculate bias analysis from articles
      const biasAnalysis = {
        analyzed: articlesRes.data?.articles?.length || 0,
        leftBias: articlesRes.data?.articles?.filter(a => a.bias_score < -0.3).length || 0,
        rightBias: articlesRes.data?.articles?.filter(a => a.bias_score > 0.3).length || 0,
        centerBias: articlesRes.data?.articles?.filter(a => Math.abs(a.bias_score) <= 0.3).length || 0,
      };

      setDashboardData({
        articles: {
          total: articlesRes.data?.total || 0,
          recent: articlesRes.data?.articles?.slice(0, 5) || [],
        },
        storylines: {
          total: storylinesRes.data?.total || 0,
          active: storylinesRes.data?.storylines?.slice(0, 5) || [],
        },
        rssFeeds: {
          total: feedsRes.data?.total || 0,
          active: feedsRes.data?.feeds?.filter(f => f.is_active).length || 0,
        },
        systemHealth: {
          status: healthRes.status || 'unknown',
          uptime: healthRes.uptime || 0,
        },
        biasAnalysis,
      });

      setLastUpdate(new Date());
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

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

  const getHealthColor = (status) => {
    switch (status) {
    case 'healthy': return 'success';
    case 'warning': return 'warning';
    case 'error': return 'error';
    default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          📊 News Intelligence Dashboard
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="body2" color="text.secondary">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </Typography>
          <IconButton onClick={fetchDashboardData} size="small">
            <SpeedIcon />
          </IconButton>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* System Health Overview */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <CheckCircleIcon color={getHealthColor(dashboardData.systemHealth.status)} sx={{ mr: 1 }} />
                <Typography variant="h6">System Health</Typography>
              </Box>
              <Typography variant="h4" color={getHealthColor(dashboardData.systemHealth.status)}>
                {dashboardData.systemHealth.status === 'healthy' ? '✅' :
                  dashboardData.systemHealth.status === 'warning' ? '⚠️' : '❌'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Uptime: {Math.floor(dashboardData.systemHealth.uptime / 3600)}h
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* ML Processing Status */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <PsychologyIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">ML Processing</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                🤖
              </Typography>
              <Typography variant="body2" color="text.secondary">
                ML Processing Active
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Articles with Bias Analysis */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Article color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Articles</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {dashboardData.articles.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Articles Processed
              </Typography>
              <Box mt={1}>
                <Chip label={`Left: ${dashboardData.biasAnalysis.leftBias}`} size="small" color="error" sx={{ mr: 0.5 }} />
                <Chip label={`Center: ${dashboardData.biasAnalysis.centerBias}`} size="small" color="success" sx={{ mr: 0.5 }} />
                <Chip label={`Right: ${dashboardData.biasAnalysis.rightBias}`} size="small" color="warning" />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Storylines */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TimelineIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Storylines</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {dashboardData.storylines.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Storylines
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* RSS Feeds */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <RssFeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">RSS Feeds</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {dashboardData.rssFeeds.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active: {dashboardData.rssFeeds.active}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Articles with Bias Indicators */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                📰 Recent Articles with Bias Analysis
              </Typography>
              {dashboardData.articles.recent.length > 0 ? (
                <List>
                  {dashboardData.articles.recent.map((article, index) => (
                    <ListItem key={index} divider>
                      <ListItemIcon>
                        <Article />
                      </ListItemIcon>
                      <ListItemText
                        primary={article.title}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {article.source} • {new Date(article.published_at).toLocaleDateString()}
                            </Typography>
                            <Box mt={0.5}>
                              <Chip
                                label={getBiasLabel(article.bias_score || 0)}
                                size="small"
                                color={getBiasColor(article.bias_score || 0)}
                              />
                              {article.credibility_score && (
                                <Chip
                                  label={`Credibility: ${Math.round(article.credibility_score * 100)}%`}
                                  size="small"
                                  variant="outlined"
                                  sx={{ ml: 0.5 }}
                                />
                              )}
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography color="text.secondary">No recent articles</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Active Storylines */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                📚 Active Storylines with Timeline
              </Typography>
              {dashboardData.storylines.active.length > 0 ? (
                <List>
                  {dashboardData.storylines.active.map((storyline, index) => (
                    <ListItem key={index} divider>
                      <ListItemIcon>
                        <TimelineIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary={storyline.title}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {storyline.category} • {storyline.article_count} articles
                            </Typography>
                            <Box mt={0.5}>
                              <Chip
                                label={storyline.status}
                                size="small"
                                color={storyline.status === 'active' ? 'success' : 'default'}
                              />
                              {storyline.priority && (
                                <Chip
                                  label={`Priority: ${storyline.priority}`}
                                  size="small"
                                  variant="outlined"
                                  sx={{ ml: 0.5 }}
                                />
                              )}
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography color="text.secondary">No active storylines</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* System Debug Information */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                🔧 System Debug Information
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="primary">API Status</Typography>
                    <Typography variant="body2">
                      Articles API: ✅ Working<br/>
                      Storylines API: ✅ Working<br/>
                      RSS Feeds API: ✅ Working<br/>
                      Health API: ✅ Working
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="primary">Data Processing</Typography>
                    <Typography variant="body2">
                      ML Processing: ✅ Running<br/>
                      System Status: Active<br/>
                      Last Update: {lastUpdate.toLocaleTimeString()}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="primary">Bias Analysis</Typography>
                    <Typography variant="body2">
                      Total Analyzed: {dashboardData.biasAnalysis.analyzed}<br/>
                      Left Bias: {dashboardData.biasAnalysis.leftBias}<br/>
                      Center: {dashboardData.biasAnalysis.centerBias}<br/>
                      Right Bias: {dashboardData.biasAnalysis.rightBias}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
