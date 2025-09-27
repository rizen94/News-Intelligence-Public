/**
 * News Intelligence System v3.3.0 - System Analytics Component
 * Provides advanced analytics using structured data and schemas from Phase 1
 *
 * TODO: Phase 2 (Week 7) - Advanced Analytics Dashboard
 * - Display duplicate patterns and trends
 * - Show cluster analysis and insights
 * - Add performance metrics visualization
 * - Implement data export functionality
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  LinearProgress,
  Button,
  Alert,
  CircularProgress,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Speed as SpeedIcon,
  Assessment as AssessmentIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Analytics as AnalyticsIcon,
  DataUsage as DataUsageIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';

import { enhancedApiService } from '../../services/enhancedApiService';
import Logger from '../../utils/logger';

interface AnalyticsData {
  system_health: {
    overall_score: number;
    error_rate: number;
    performance_score: number;
    reliability_score: number;
  };
  content_metrics: {
    total_articles: number;
    articles_processed: number;
    quality_distribution: { score_range: string; count: number }[];
    source_diversity: { source: string; count: number }[];
  };
  processing_metrics: {
    ml_processing_rate: number;
    deduplication_efficiency: number;
    average_processing_time: number;
    error_rate: number;
  };
  trends: {
    daily_articles: { date: string; count: number }[];
    error_trends: { date: string; errors: number }[];
    quality_trends: { date: string; avg_quality: number }[];
  };
}

const SystemAnalytics: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  // Data states
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [logStats, setLogStats] = useState<any>(null);
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  const [databaseMetrics, setDatabaseMetrics] = useState<any>(null);
  const [deduplicationStats, setDeduplicationStats] = useState<any>(null);

  // Pagination states
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const loadAnalyticsData = useCallback(async() => {
    try {
      setRefreshing(true);
      setError(null);

      Logger.info('Loading system analytics data');

      // Load analytics data in parallel
      const [
        logStatsData,
        metricsData,
        dbMetricsData,
        dedupStatsData,
      ] = await Promise.allSettled([
        enhancedApiService.getLogStatistics(30), // Last 30 days
        enhancedApiService.getSystemMetrics(),
        enhancedApiService.getDatabaseMetrics(),
        enhancedApiService.getDeduplicationStats(),
      ]);

      // Process results
      if (logStatsData.status === 'fulfilled') {
        setLogStats(logStatsData.value);
      }
      if (metricsData.status === 'fulfilled') {
        setSystemMetrics(metricsData.value);
      }
      if (dbMetricsData.status === 'fulfilled') {
        setDatabaseMetrics(dbMetricsData.value);
      }
      if (dedupStatsData.status === 'fulfilled') {
        setDeduplicationStats(dedupStatsData.value);
      }

      // Generate analytics data from collected metrics
      const analytics = generateAnalyticsData({
        logStats: logStatsData.status === 'fulfilled' ? logStatsData.value : null,
        systemMetrics: metricsData.status === 'fulfilled' ? metricsData.value : null,
        databaseMetrics: dbMetricsData.status === 'fulfilled' ? dbMetricsData.value : null,
        deduplicationStats: dedupStatsData.status === 'fulfilled' ? dedupStatsData.value : null,
      });

      setAnalyticsData(analytics);
      Logger.info('System analytics data loaded successfully');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      Logger.error('Failed to load system analytics data', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const generateAnalyticsData = (data: any): AnalyticsData => {
    const { logStats, systemMetrics, databaseMetrics, deduplicationStats } = data;

    // Calculate system health score
    const errorRate = logStats ? (logStats.error_count / logStats.total_entries) * 100 : 0;
    const performanceScore = systemMetrics ?
      Math.max(0, 100 - (systemMetrics.cpu_percent + systemMetrics.memory_percent) / 2) : 0;
    const reliabilityScore = Math.max(0, 100 - errorRate * 10);
    const overallScore = (performanceScore + reliabilityScore) / 2;

    // Generate quality distribution (mock data for now)
    const qualityDistribution = [
      { score_range: '0.0-0.2', count: Math.floor(Math.random() * 50) },
      { score_range: '0.2-0.4', count: Math.floor(Math.random() * 100) },
      { score_range: '0.4-0.6', count: Math.floor(Math.random() * 200) },
      { score_range: '0.6-0.8', count: Math.floor(Math.random() * 300) },
      { score_range: '0.8-1.0', count: Math.floor(Math.random() * 150) },
    ];

    // Generate source diversity (mock data for now)
    const sourceDiversity = [
      { source: 'CNN', count: Math.floor(Math.random() * 100) },
      { source: 'BBC', count: Math.floor(Math.random() * 80) },
      { source: 'Reuters', count: Math.floor(Math.random() * 60) },
      { source: 'Fox News', count: Math.floor(Math.random() * 90) },
      { source: 'MSNBC', count: Math.floor(Math.random() * 70) },
    ];

    // Generate trends (mock data for now)
    const dailyArticles = Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      count: Math.floor(Math.random() * 50) + 10,
    }));

    const errorTrends = Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      errors: Math.floor(Math.random() * 20),
    }));

    const qualityTrends = Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      avg_quality: Math.random() * 0.4 + 0.6, // 0.6 to 1.0
    }));

    return {
      system_health: {
        overall_score: overallScore,
        error_rate: errorRate,
        performance_score: performanceScore,
        reliability_score: reliabilityScore,
      },
      content_metrics: {
        total_articles: databaseMetrics?.total_articles || 0,
        articles_processed: databaseMetrics?.total_articles || 0,
        quality_distribution: qualityDistribution,
        source_diversity: sourceDiversity,
      },
      processing_metrics: {
        ml_processing_rate: 85.5, // Mock data
        deduplication_efficiency: deduplicationStats ?
          (deduplicationStats.total_duplicate_pairs / deduplicationStats.total_articles) * 100 : 0,
        average_processing_time: 2.3, // Mock data
        error_rate: errorRate,
      },
      trends: {
        daily_articles: dailyArticles,
        error_trends: errorTrends,
        quality_trends: qualityTrends,
      },
    };
  };

  useEffect(() => {
    loadAnalyticsData();
  }, [loadAnalyticsData]);

  // Auto-refresh setup
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(loadAnalyticsData, 60000); // 1 minute for analytics
      setRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, loadAnalyticsData]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleRefresh = () => {
    loadAnalyticsData();
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const getHealthColor = (score: number) => {
    if (score >= 90) return 'success';
    if (score >= 70) return 'warning';
    return 'error';
  };

  const getTrendIcon = (current: number, previous: number) => {
    if (current > previous) return <TrendingUpIcon color="success" />;
    if (current < previous) return <TrendingDownIcon color="error" />;
    return <TimelineIcon color="info" />;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading System Analytics...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          System Analytics
        </Typography>
        <Box display="flex" gap={2} alignItems="center">
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
            }
            label="Auto Refresh (1m)"
          />
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant="scrollable">
          <Tab icon={<AssessmentIcon />} label="Overview" />
          <Tab icon={<DataUsageIcon />} label="Content Metrics" />
          <Tab icon={<SpeedIcon />} label="Processing" />
          <Tab icon={<TrendingUpIcon />} label="Trends" />
          <Tab icon={<AnalyticsIcon />} label="Advanced" />
        </Tabs>
      </Paper>

      {/* Overview Tab */}
      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          {analyticsData && (
            <>
              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Overall Health Score
                    </Typography>
                    <Typography variant="h2" color={getHealthColor(analyticsData.system_health.overall_score)}>
                      {analyticsData.system_health.overall_score.toFixed(1)}
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={analyticsData.system_health.overall_score}
                      color={getHealthColor(analyticsData.system_health.overall_score)}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Error Rate
                    </Typography>
                    <Typography variant="h2" color={analyticsData.system_health.error_rate > 5 ? 'error' : 'success'}>
                      {analyticsData.system_health.error_rate.toFixed(2)}%
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Performance Score
                    </Typography>
                    <Typography variant="h2" color={getHealthColor(analyticsData.system_health.performance_score)}>
                      {analyticsData.system_health.performance_score.toFixed(1)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Reliability Score
                    </Typography>
                    <Typography variant="h2" color={getHealthColor(analyticsData.system_health.reliability_score)}>
                      {analyticsData.system_health.reliability_score.toFixed(1)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Content Metrics Tab */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={3}>
          {analyticsData && (
            <>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Quality Distribution
                    </Typography>
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Score Range</TableCell>
                            <TableCell align="right">Count</TableCell>
                            <TableCell align="right">Percentage</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {analyticsData.content_metrics.quality_distribution.map((item, index) => (
                            <TableRow key={index}>
                              <TableCell>{item.score_range}</TableCell>
                              <TableCell align="right">{item.count}</TableCell>
                              <TableCell align="right">
                                {((item.count / analyticsData.content_metrics.total_articles) * 100).toFixed(1)}%
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Source Diversity
                    </Typography>
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Source</TableCell>
                            <TableCell align="right">Articles</TableCell>
                            <TableCell align="right">Percentage</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {analyticsData.content_metrics.source_diversity.map((item, index) => (
                            <TableRow key={index}>
                              <TableCell>{item.source}</TableCell>
                              <TableCell align="right">{item.count}</TableCell>
                              <TableCell align="right">
                                {((item.count / analyticsData.content_metrics.total_articles) * 100).toFixed(1)}%
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Processing Tab */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={3}>
          {analyticsData && (
            <>
              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      ML Processing Rate
                    </Typography>
                    <Typography variant="h2" color="primary">
                      {analyticsData.processing_metrics.ml_processing_rate.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={analyticsData.processing_metrics.ml_processing_rate}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Deduplication Efficiency
                    </Typography>
                    <Typography variant="h2" color="primary">
                      {analyticsData.processing_metrics.deduplication_efficiency.toFixed(1)}%
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Avg Processing Time
                    </Typography>
                    <Typography variant="h2" color="primary">
                      {analyticsData.processing_metrics.average_processing_time.toFixed(1)}s
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Processing Error Rate
                    </Typography>
                    <Typography variant="h2" color={analyticsData.processing_metrics.error_rate > 5 ? 'error' : 'success'}>
                      {analyticsData.processing_metrics.error_rate.toFixed(2)}%
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Trends Tab */}
      <TabPanel value={tabValue} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Daily Article Processing Trends
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Advanced trend analysis and visualization will be implemented here using the structured data
                  from our comprehensive logging and monitoring systems.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Advanced Tab */}
      <TabPanel value={tabValue} index={4}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Advanced Analytics
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Machine learning-powered insights, predictive analytics, and advanced data mining
                  capabilities will be implemented here using the structured data and schemas from Phase 1.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};

// TabPanel component
interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`analytics-tabpanel-${index}`}
      aria-labelledby={`analytics-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default SystemAnalytics;
