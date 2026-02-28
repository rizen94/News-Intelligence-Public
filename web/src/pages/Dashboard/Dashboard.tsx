/**
 * News Intelligence System - Consolidated Dashboard
 * Combines features from EnhancedDashboard, Phase2Dashboard, UnifiedDashboard, and Dashboard
 *
 * Features:
 * - Tabbed interface (Overview, System Health, Logs & Monitoring, Analytics, API Status)
 * - Process controls (Pipeline, RSS, AI Analysis, Master Switch)
 * - System health monitoring
 * - Real-time metrics and statistics
 * - Bias analysis
 * - Performance metrics
 * - Master articles tracking
 * - Preprocessing statistics
 */

import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Alert,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  FormControlLabel,
  Switch,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Article,
  RssFeed as RssFeedIcon,
  Timeline as TimelineIcon,
  Refresh,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Schedule,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  Analytics,
  AutoAwesome as AutoAwesomeIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Queue as QueueIcon,
  BugReport as BugReportIcon,
  Assessment as AssessmentIcon,
  Code as CodeIcon,
  Monitor as MonitorIcon,
  Download as DownloadIcon,
  DeleteSweep as CleanupIcon,
  TrendingUp as TrendingUpIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

// Import with multiple patterns to handle webpack module resolution issues
import apiServiceDefault from '../../services/apiService';
import { getApiService } from '../../services/apiService';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { useNotification } from '../../hooks/useNotification';
import { getUserFriendlyError } from '../../utils/errorHandler';
import LoadingState from '../../components/shared/LoadingState';
import EmptyState from '../../components/shared/EmptyState';

// Robust apiService initialization - handle all webpack import patterns
let apiService: any = null;

// Try multiple import patterns to handle webpack module resolution
// Pattern 1: Default export
if (apiServiceDefault && typeof apiServiceDefault === 'object' && typeof (apiServiceDefault as any).getMonitoringDashboard === 'function') {
  apiService = apiServiceDefault;
  console.log('✅ Dashboard: apiService loaded via default export');
}

// Fallback to getter function
if (!apiService || typeof apiService.getMonitoringDashboard !== 'function') {
  try {
    const service = getApiService();
    if (service && typeof service.getMonitoringDashboard === 'function') {
      apiService = service;
      console.log('✅ Dashboard: apiService loaded via getApiService()');
    }
  } catch (e) {
    console.error('❌ Dashboard: Failed to get apiService:', e);
  }
}

// Final safety check - create a proxy that logs errors
if (!apiService || typeof apiService.getMonitoringDashboard !== 'function') {
  console.error('❌ Dashboard: apiService is still undefined or invalid:', {
    apiServiceDefault,
    apiService,
    hasGetApiService: typeof getApiService === 'function',
  });

  // Create a minimal fallback that at least prevents crashes
  apiService = {
    getMonitoringDashboard: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getHealth: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getArticles: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getStorylines: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getRSSFeeds: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getPipelineStatus: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getSystemMetrics: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getDatabaseMetrics: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getLogStatistics: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getRealtimeLogs: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getDeduplicationStats: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getAPIStatus: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    triggerPipeline: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    updateRSSFeeds: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    runAIAnalysis: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
  } as any;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role='tabpanel'
      hidden={value !== index}
      id={`dashboard-tabpanel-${index}`}
      aria-labelledby={`dashboard-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

interface SystemStatus {
  overall: string;
  health?: any;
  articleStats?: {
    data: {
      total_articles: number;
      articles_today: number;
      articles_this_week: number;
      top_sources: any[];
    };
  };
  rssStats?: {
    data: {
      total_feeds: number;
      active_feeds: number;
      feeds_with_errors: number;
    };
  };
  storylineStats?: {
    data: {
      total_storylines: number;
      active_storylines: number;
    };
  };
  pipelineStatus?: {
    data: {
      status: string;
      success_rate: number;
      total_traces: number;
      active_traces: number;
    };
  };
  recentArticles?: any[];
  analytics?: any;
  systemMetrics?: any;
}

const StoryActivityWidgets: React.FC<{ domain: string; navigate: any }> = ({ domain, navigate }) => {
  const [activityFeed, setActivityFeed] = useState<any[]>([]);
  const [dormant, setDormant] = useState<any[]>([]);
  const [gaps, setGaps] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [af, ds, cg] = await Promise.allSettled([
          apiService.getActivityFeed?.(10) || Promise.resolve({ data: [] }),
          apiService.getDormantAlerts?.(30) || Promise.resolve({ data: [] }),
          apiService.getCoverageGaps?.(7) || Promise.resolve({ data: [] }),
        ]);
        setActivityFeed((af.status === 'fulfilled' ? af.value?.data : null) || []);
        setDormant((ds.status === 'fulfilled' ? ds.value?.data : null) || []);
        setGaps((cg.status === 'fulfilled' ? cg.value?.data : null) || []);
      } catch { /* non-critical */ }
      setLoaded(true);
    };
    load();
  }, []);

  if (!loaded) return null;
  const hasData = activityFeed.length > 0 || dormant.length > 0 || gaps.length > 0;
  if (!hasData) return null;

  return (
    <>
      {activityFeed.length > 0 && (
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <TimelineIcon color='primary' sx={{ mr: 1 }} />
                <Typography variant='h6'>Recent Event Activity</Typography>
              </Box>
              <List dense>
                {activityFeed.slice(0, 6).map((item: any, i: number) => (
                  <ListItem key={i} divider sx={{ cursor: 'pointer' }}
                    onClick={() => item.storyline_id && navigate(`/${domain}/storylines/${item.storyline_id}/timeline`)}>
                    <ListItemText
                      primary={item.event_title}
                      secondary={`${(item.event_type || '').replace(/_/g, ' ')} · ${item.storyline_title || 'unlinked'} · ${item.event_date || ''}`}
                    />
                    {item.source_count > 1 && (
                      <Chip label={`${item.source_count} sources`} size='small' color='info' variant='outlined' />
                    )}
                  </ListItem>
                ))}
              </List>
              <Button size='small' onClick={() => navigate(`/${domain}/intelligence/events`)}>
                View all events
              </Button>
            </CardContent>
          </Card>
        </Grid>
      )}

      {dormant.length > 0 && (
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <WarningIcon color='warning' sx={{ mr: 1 }} />
                <Typography variant='h6'>Dormant Stories</Typography>
              </Box>
              <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
                Watched stories silent for 30+ days
              </Typography>
              <List dense>
                {dormant.slice(0, 4).map((d: any, i: number) => (
                  <ListItem key={i} sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/${domain}/storylines/${d.storyline_id}`)}>
                    <ListItemText
                      primary={d.title}
                      secondary={`Since ${d.dormant_since ? new Date(d.dormant_since).toLocaleDateString() : '?'}`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      )}

      {gaps.length > 0 && (
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' mb={2}>
                <ErrorIcon color='error' sx={{ mr: 1 }} />
                <Typography variant='h6'>Coverage Gaps</Typography>
              </Box>
              <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
                Active stories with no new sources in 7+ days
              </Typography>
              <List dense>
                {gaps.slice(0, 4).map((g: any, i: number) => (
                  <ListItem key={i} sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/${domain}/storylines/${g.storyline_id}`)}>
                    <ListItemText
                      primary={g.title}
                      secondary={`Last: ${g.last_event_at ? new Date(g.last_event_at).toLocaleDateString() : 'never'}`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      )}
    </>
  );
};

const Dashboard: React.FC = () => {
  const { domain } = useDomainRoute();
  const navigate = useNavigate();
  const { showSuccess, showError, NotificationComponent } = useNotification();

  // Tab state
  const [tabValue, setTabValue] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Loading and error states
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // System data states
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [monitoringData, setMonitoringData] = useState<any>(null);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  const [databaseMetrics, setDatabaseMetrics] = useState<any>(null);
  const [logStats, setLogStats] = useState<any>(null);
  const [realtimeLogs, setRealtimeLogs] = useState<any[]>([]);
  const [deduplicationStats, setDeduplicationStats] = useState<any>(null);
  const [apiStatus, setApiStatus] = useState<any>(null);

  // Process status states
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [rssRunning, setRssRunning] = useState(false);
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [masterRunning, setMasterRunning] = useState(false);

  // ETA states
  const [displayPipelineETA, setDisplayPipelineETA] = useState<string | null>(null);
  const [displayRssETA, setDisplayRssETA] = useState<string | null>(null);
  const [displayAnalysisETA, setDisplayAnalysisETA] = useState<string | null>(null);

  // Dialog states
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);

  // Bias analysis state
  const [biasAnalysis, setBiasAnalysis] = useState({
    analyzed: 0,
    leftBias: 0,
    rightBias: 0,
    centerBias: 0,
  });

  const loadSystemData = useCallback(async() => {
    try {
      setRefreshing(true);
      setError(null);

      // Log that we're starting to load data
      console.log('🔄 Starting to load system data...');

      // Load all dashboard data in parallel
      const [
        monitoringData,
        healthData,
        articlesData,
        storylinesData,
        rssData,
        pipelineStatusData,
        metricsData,
        dbMetricsData,
        logStatsData,
        realtimeLogsData,
        dedupStatsData,
        apiStatusData,
      ] = await Promise.allSettled([
        apiService.getMonitoringDashboard().catch(err => {
          console.error('❌ Monitoring dashboard error:', err);
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            const errorMsg = getUserFriendlyError(err);
            setError(errorMsg);
            showError(errorMsg);
          }
          return null;
        }),
        apiService.getHealth().catch(err => {
          console.error('❌ Health check error:', err);
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            const errorMsg = getUserFriendlyError(err);
            setError(errorMsg);
            showError(errorMsg);
          }
          return { success: false, status: 'unknown', error: 'Connection failed' };
        }),
        apiService.getArticles({ limit: 100 }, domain).catch(err => {
          console.error('❌ Articles fetch error:', err);
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            return { data: { articles: [], total: 0 } };
          }
          return { data: { articles: [], total: 0 } };
        }),
        apiService.getStorylines({ limit: 100 }, domain).catch(err => {
          console.error('❌ Storylines fetch error:', err);
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            return { data: { storylines: [], total: 0 } };
          }
          return { data: { storylines: [], total: 0 } };
        }),
        apiService.getRSSFeeds({ limit: 100 }, domain).catch(err => {
          console.error('❌ RSS feeds fetch error:', err);
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            return { data: { feeds: [], total: 0 } };
          }
          return { data: { feeds: [], total: 0 } };
        }),
        apiService.getPipelineStatus().catch(err => {
          console.error('❌ Pipeline status error:', err);
          if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || !err.response) {
            return { success: false, data: { pipeline_status: 'idle', success_rate: 0, total_traces: 0, active_traces: 0 } };
          }
          return { success: false, data: { pipeline_status: 'idle', success_rate: 0, total_traces: 0, active_traces: 0 } };
        }),
        apiService.getSystemMetrics().catch(() => null),
        apiService.getDatabaseMetrics().catch(() => null),
        apiService.getLogStatistics(7).catch(() => null),
        apiService.getRealtimeLogs(50).catch(() => null),
        apiService.getDeduplicationStats().catch(() => null),
        apiService.getAPIStatus().catch(() => null),
      ]);

      // Extract values from Promise.allSettled results
      const monitoringResult = monitoringData.status === 'fulfilled' ? monitoringData.value : null;

      // Log for debugging
      if (!monitoringResult) {
        console.warn('⚠️ Monitoring dashboard data not available');
      } else {
        console.log('✅ Monitoring dashboard data loaded:', {
          success: monitoringResult.success,
          hasData: !!monitoringResult.data,
          overallStatus: monitoringResult.data?.overall_status,
          database: monitoringResult.data?.database,
        });
      }
      const healthResult = healthData.status === 'fulfilled' ? healthData.value : { success: false, status: 'unknown' };
      const articlesResult = articlesData.status === 'fulfilled' ? articlesData.value : { data: { articles: [], total: 0 } };
      const storylinesResult = storylinesData.status === 'fulfilled' ? storylinesData.value : { data: { storylines: [], total: 0 } };
      const rssResult = rssData.status === 'fulfilled' ? rssData.value : { data: { feeds: [], total: 0 } };
      const pipelineResult = pipelineStatusData.status === 'fulfilled' ? pipelineStatusData.value : { success: false, data: { pipeline_status: 'idle', success_rate: 0, total_traces: 0, active_traces: 0 } };
      const metricsResult = metricsData.status === 'fulfilled' ? metricsData.value : null;
      const dbMetricsResult = dbMetricsData.status === 'fulfilled' ? dbMetricsData.value : null;
      const logStatsResult = logStatsData.status === 'fulfilled' && logStatsData.value?.success ? logStatsData.value : null;
      const realtimeLogsResult = realtimeLogsData.status === 'fulfilled' && realtimeLogsData.value?.success ? realtimeLogsData.value : null;
      const dedupStatsResult = dedupStatsData.status === 'fulfilled' && dedupStatsData.value?.success ? dedupStatsData.value : null;
      const apiStatusResult = apiStatusData.status === 'fulfilled' && apiStatusData.value?.success ? apiStatusData.value : null;

      // Extract articles from response
      const articlesList = articlesResult.data?.articles ||
                          articlesResult.data?.data?.articles ||
                          articlesResult.articles ||
                          [];
      const totalArticlesCount = articlesResult.data?.total ||
                                 articlesResult.data?.data?.total ||
                                 articlesResult.total ||
                                 articlesList.length;

      // Extract storylines from response
      const storylinesList = Array.isArray(storylinesResult.data)
        ? storylinesResult.data
        : storylinesResult.data?.storylines ||
        storylinesResult.data?.data?.storylines ||
        storylinesResult.storylines ||
        [];
      const totalStorylinesCount = storylinesResult.pagination?.total ||
                                   storylinesResult.data?.total ||
                                   storylinesResult.data?.data?.total ||
                                   storylinesResult.total ||
                                   storylinesList.length;

      // Calculate today's articles
      const today = new Date().toISOString().split('T')[0];
      const todayArticles = articlesList.filter(
        article =>
          article.published_at && article.published_at.startsWith(today),
      );

      // Calculate this week's articles
      const weekAgo = new Date();
      weekAgo.setDate(weekAgo.getDate() - 7);
      const weekArticles = articlesList.filter(
        article =>
          article.published_at && new Date(article.published_at) >= weekAgo,
      );

      // Calculate bias analysis
      const biasAnalysisData = {
        analyzed: articlesList.length,
        leftBias: articlesList.filter(a => (a.bias_score || 0) < -0.3).length,
        rightBias: articlesList.filter(a => (a.bias_score || 0) > 0.3).length,
        centerBias: articlesList.filter(a => Math.abs(a.bias_score || 0) <= 0.3).length,
      };

      // Calculate top sources from articles (replace static empty array)
      const sourceCounts = new Map<string, number>();
      articlesList.forEach((article: any) => {
        const source = article.source_domain || article.source || 'Unknown';
        sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
      });
      const topSources = Array.from(sourceCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([source, count]) => ({ source, count }));

      // Calculate RSS feeds with errors (replace static 0)
      const feedsWithErrors = rssResult.data?.feeds?.filter((feed: any) =>
        feed.error_count > 0 || feed.last_error || feed.status === 'error',
      ).length || 0;

      // Determine overall health status
      const healthStatus = healthResult?.status ||
        healthResult?.data?.status ||
        (monitoringResult?.data?.database?.status === 'healthy' &&
        monitoringResult?.data?.redis?.status === 'healthy' ? 'healthy' : 'unknown');

      // Use monitoring data for accurate counts (from domain schemas)
      // Note: apiService returns response.data, so monitoringResult is already the unwrapped response
      const monitoringDbData = monitoringResult?.data?.database || {};
      const dbMetricsDataExtracted = dbMetricsResult?.data || {};

      // Log data extraction for debugging
      console.log('📊 Data extraction:', {
        monitoringDbData,
        dbMetricsDataExtracted,
        totalArticlesCount,
        todayArticlesLength: todayArticles.length,
        weekArticlesLength: weekArticles.length,
      });

      // Combine the data into system status
      // IMPORTANT: Use domain-specific data from getArticles/getRSSFeeds/getStorylines calls,
      // NOT aggregated monitoring data which combines all domains
      const status: SystemStatus = {
        overall: monitoringResult?.data?.overall_status || healthStatus,
        health: healthResult,
        articleStats: {
          data: {
            // Use domain-specific article counts (from getArticles call with domain parameter)
            total_articles: totalArticlesCount || 0,
            articles_today: todayArticles.length || 0,
            articles_this_week: weekArticles.length || 0,
            top_sources: topSources,
          },
        },
        rssStats: {
          data: {
            // Use domain-specific RSS feed counts (from getRSSFeeds call with domain parameter)
            total_feeds: rssResult.data?.total || rssResult.data?.feeds?.length || 0,
            active_feeds: rssResult.data?.feeds?.filter((feed: any) => feed.is_active)?.length || 0,
            feeds_with_errors: feedsWithErrors,
          },
        },
        storylineStats: {
          data: {
            // Use domain-specific storyline counts (from getStorylines call with domain parameter)
            total_storylines: totalStorylinesCount || 0,
            active_storylines:
              storylinesList.filter(
                (s: any) => s.status === 'active',
              )?.length || 0,
          },
        },
        pipelineStatus: {
          data: {
            status: pipelineResult?.data?.pipeline_status === 'running' ? 'running' : (pipelineResult?.data?.pipeline_status || 'idle'),
            success_rate: pipelineResult?.data?.success_rate || 0,
            total_traces: pipelineResult?.data?.total_traces || 0,
            active_traces: pipelineResult?.data?.active_traces || 0,
          },
        },
        recentArticles: articlesResult.data?.articles?.slice(0, 5) || [],
        analytics: {},
        systemMetrics: monitoringResult?.data?.system || {},
      };

      setSystemStatus(status);
      setMonitoringData(monitoringResult);

      // FIXED: Transform healthResult to match frontend expectations
      // API now returns {success, status, services: {database, redis, system}, system_metrics}
      // Frontend expects {status, services: {database, redis, system}}
      const transformedHealth = healthResult?.success ? {
        status: healthResult.status || 'unknown',
        services: healthResult.services || {
          database: monitoringResult?.data?.database?.status || 'unknown',
          redis: monitoringResult?.data?.redis?.status || 'unknown',
          system: monitoringResult?.data?.system?.status || 'unknown',
        },
        system_metrics: healthResult.system_metrics || {},
      } : { status: 'unknown', services: {} };
      setSystemHealth(transformedHealth);

      // FIXED: systemMetrics should come from monitoringResult.data.system (not metricsResult)
      // metricsResult is from /metrics endpoint which has different structure
      const transformedMetrics = monitoringResult?.data?.system || metricsResult?.data?.metrics?.[0] || healthResult?.system_metrics || null;
      setSystemMetrics(transformedMetrics);

      setDatabaseMetrics(dbMetricsResult);

      // FIXED: logStats now comes from proper endpoint with correct structure
      // Endpoint returns {data: {total_entries, error_count, warning_count, info_count}}
      const transformedLogStats = logStatsResult?.data ? {
        total_entries: logStatsResult.data.total_entries || 0,
        error_count: logStatsResult.data.error_count || 0,
        warning_count: logStatsResult.data.warning_count || 0,
        info_count: logStatsResult.data.info_count || 0,
      } : null;
      setLogStats(transformedLogStats);

      setRealtimeLogs(realtimeLogsResult?.data?.entries || []);
      setDeduplicationStats(dedupStatsResult);
      setApiStatus(apiStatusResult);
      setBiasAnalysis(biasAnalysisData);

      // Always update the last update time, even if some data failed to load
      setLastUpdate(new Date());

      // Clear any previous errors if we got here successfully
      if (error) {
        setError(null);
      }

      console.log('✅ System data loaded successfully');
    } catch (err: any) {
      console.error('❌ Error loading system data:', err);
      console.error('❌ Error details:', {
        message: err?.message,
        stack: err?.stack,
        code: err?.code,
        response: err?.response?.data,
        url: err?.config?.url,
        status: err?.response?.status,
      });

      // Provide more specific error messages
      let errorMessage = 'Failed to load system data';
      if (err?.code === 'ECONNREFUSED' || err?.message?.includes('Network Error') || err?.message?.includes('fetch')) {
        errorMessage = '⚠️ Cannot connect to API server. Please check if the API server is running on port 8000.';
      } else if (err?.response?.status === 404) {
        errorMessage = `⚠️ API endpoint not found: ${err?.config?.url}. Please check the API server configuration.`;
      } else if (err?.response?.status >= 500) {
        errorMessage = '⚠️ API server error. Please check the API server logs.';
      } else if (err?.message) {
        errorMessage = `⚠️ ${err.message}`;
      }

      const friendlyError = getUserFriendlyError(err);
      setError(friendlyError);
      showError(friendlyError);

      // Update last update time even on error (so user knows when last attempt was made)
      setLastUpdate(new Date());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [domain]);

  useEffect(() => {
    loadSystemData();
    if (autoRefresh) {
      const interval = setInterval(loadSystemData, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [loadSystemData, autoRefresh]);

  // Load process status from localStorage on mount
  useEffect(() => {
    const savedPipelineStatus = localStorage.getItem('pipelineStatus');
    const savedRssStatus = localStorage.getItem('rssStatus');
    const savedAnalysisStatus = localStorage.getItem('analysisStatus');
    const savedMasterStatus = localStorage.getItem('masterStatus');

    if (savedPipelineStatus) {
      const status = JSON.parse(savedPipelineStatus);
      setPipelineRunning(status.running);
      setDisplayPipelineETA(status.eta);
    }
    if (savedRssStatus) {
      const status = JSON.parse(savedRssStatus);
      setRssRunning(status.running);
      setDisplayRssETA(status.eta);
    }
    if (savedAnalysisStatus) {
      const status = JSON.parse(savedAnalysisStatus);
      setAnalysisRunning(status.running);
      setDisplayAnalysisETA(status.eta);
    }
    if (savedMasterStatus) {
      const status = JSON.parse(savedMasterStatus);
      setMasterRunning(status.running);
    }
  }, []);

  const handleRefresh = () => {
    loadSystemData();
  };

  // Process management functions
  const saveProcessStatus = (process: string, running: boolean, eta: string | null = null) => {
    const status = { running, eta, timestamp: new Date().toISOString() };
    localStorage.setItem(`${process}Status`, JSON.stringify(status));
  };

  const executeTriggerPipeline = async() => {
    try {
      setPipelineRunning(true);
      setDisplayPipelineETA('Processing...');
      saveProcessStatus('pipeline', true, 'Processing...');

      await apiService.triggerPipeline();

      setTimeout(() => {
        setPipelineRunning(false);
        setDisplayPipelineETA(null);
        saveProcessStatus('pipeline', false);
        loadSystemData();
      }, 30000);
    } catch (error) {
      console.error('Pipeline execution failed:', error);
      setPipelineRunning(false);
      setDisplayPipelineETA(null);
      saveProcessStatus('pipeline', false);
    }
  };

  const executeUpdateRSSFeeds = async() => {
    try {
      setRssRunning(true);
      setDisplayRssETA('Updating...');
      saveProcessStatus('rss', true, 'Updating...');

      const response = await apiService.updateRSSFeeds();

      if (response.success) {
        setDisplayRssETA(
          `Complete - ${response.articles_added || 0} articles added`,
        );
        setTimeout(() => {
          setDisplayRssETA(null);
        }, 2000);
      } else {
        setDisplayRssETA('Failed');
        setTimeout(() => {
          setDisplayRssETA(null);
        }, 2000);
      }

      setRssRunning(false);
      saveProcessStatus('rss', false);
      loadSystemData();
    } catch (error) {
      console.error('RSS update failed:', error);
      setRssRunning(false);
      setDisplayRssETA('Error');
      setTimeout(() => {
        setDisplayRssETA(null);
      }, 2000);
      saveProcessStatus('rss', false);
    }
  };

  const executeRunAIAnalysis = async() => {
    try {
      setAnalysisRunning(true);
      setDisplayAnalysisETA('Analyzing...');
      saveProcessStatus('analysis', true, 'Analyzing...');

      await apiService.runAIAnalysis();

      setTimeout(() => {
        setAnalysisRunning(false);
        setDisplayAnalysisETA(null);
        saveProcessStatus('analysis', false);
        loadSystemData();
      }, 20000);
    } catch (error) {
      console.error('AI analysis failed:', error);
      setAnalysisRunning(false);
      setDisplayAnalysisETA(null);
      saveProcessStatus('analysis', false);
    }
  };

  const executeMasterSwitch = async() => {
    try {
      setMasterRunning(true);
      setRssRunning(true);
      setPipelineRunning(true);
      setAnalysisRunning(true);
      saveProcessStatus('master', true);

      const response = await apiService.triggerPipeline();

      if (response.success) {
        setDisplayRssETA('Completed');
        setDisplayPipelineETA('Completed');
        setDisplayAnalysisETA('Completed');

        setTimeout(() => {
          setMasterRunning(false);
          setRssRunning(false);
          setPipelineRunning(false);
          setAnalysisRunning(false);
          setDisplayRssETA(null);
          setDisplayPipelineETA(null);
          setDisplayAnalysisETA(null);
          saveProcessStatus('master', false);
          loadSystemData();
        }, 3000);
      } else {
        throw new Error(response.error || 'Pipeline orchestration failed');
      }
    } catch (error) {
      console.error('Master switch execution failed:', error);
      setMasterRunning(false);
      setRssRunning(false);
      setPipelineRunning(false);
      setAnalysisRunning(false);
      setDisplayRssETA(null);
      setDisplayPipelineETA(null);
      setDisplayAnalysisETA(null);
      saveProcessStatus('master', false);
    }
  };

  const handleProcessAction = (action: string) => {
    setConfirmAction(action);
    setConfirmDialogOpen(true);
  };

  const confirmProcessAction = () => {
    setConfirmDialogOpen(false);

    switch (confirmAction) {
    case 'pipeline':
      executeTriggerPipeline();
      break;
    case 'rss':
      executeUpdateRSSFeeds();
      break;
    case 'analysis':
      executeRunAIAnalysis();
      break;
    case 'master':
      executeMasterSwitch();
      break;
    default:
      break;
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleExportLogs = async() => {
    try {
      // Log export functionality - can be implemented when needed
      // For now, logs can be accessed via the monitoring dashboard
      const logs = await apiService.getLogStatistics();
      const logData = JSON.stringify(logs, null, 2);
      const blob = new Blob([logData], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `system-logs-${new Date().toISOString()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export logs', err);
    }
  };

  const handleCleanupLogs = async() => {
    try {
      // Log cleanup - note: v4 API doesn't have explicit cleanup endpoint
      // Logs are managed automatically by the system
      console.info('Log cleanup is handled automatically by the system');
      loadSystemData();
    } catch (err) {
      console.error('Failed to cleanup logs', err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
    case 'healthy':
      return 'success';
    case 'degraded':
    case 'warning':
      return 'warning';
    case 'error':
      return 'error';
    default:
      return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
    case 'healthy':
      return <CheckCircleIcon />;
    case 'degraded':
    case 'warning':
      return <WarningIcon />;
    case 'error':
      return <WarningIcon />;
    default:
      return <WarningIcon />;
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level?.toUpperCase()) {
    case 'ERROR':
      return 'error';
    case 'WARNING':
      return 'warning';
    case 'INFO':
      return 'info';
    case 'DEBUG':
      return 'default';
    default:
      return 'default';
    }
  };

  const getBiasColor = (biasScore: number) => {
    if (biasScore < -0.3) return 'error';
    if (biasScore > 0.3) return 'warning';
    return 'success';
  };

  const getBiasLabel = (biasScore: number) => {
    if (biasScore < -0.3) return 'Left Bias';
    if (biasScore > 0.3) return 'Right Bias';
    return 'Center';
  };

  if (loading && !systemStatus) {
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
          News Intelligence Dashboard
        </Typography>
        <Box display='flex' alignItems='center' gap={2}>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
              />
            }
            label='Auto Refresh'
          />
          <Typography variant='body2' color='text.secondary'>
            Last updated:{' '}
            {lastUpdate ? (
              <>
                {lastUpdate.toLocaleTimeString()} ({Math.floor((Date.now() - lastUpdate.getTime()) / 1000)}s ago)
              </>
            ) : (
              'Never'
            )}
          </Typography>
          <Tooltip title='Refresh Data'>
            <span>
              <IconButton onClick={handleRefresh} disabled={refreshing}>
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {refreshing && <LinearProgress sx={{ mb: 3 }} />}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant='scrollable'>
          <Tab icon={<DashboardIcon />} label='Overview' />
          <Tab icon={<MonitorIcon />} label='System Health' />
          <Tab icon={<BugReportIcon />} label='Logs & Monitoring' />
          <Tab icon={<AssessmentIcon />} label='Analytics' />
          <Tab icon={<CodeIcon />} label='API Status' />
        </Tabs>
      </Paper>

      {/* Overview Tab */}
      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          {/* System Health Overview */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box display='flex' alignItems='center' mb={2}>
                  <DashboardIcon color='primary' sx={{ mr: 1 }} />
                  <Typography variant='h6'>System Health</Typography>
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={3}>
                    <Box textAlign='center'>
                      <Chip
                        icon={getStatusIcon(systemStatus?.overall || 'unknown')}
                        label={(systemStatus?.overall || 'UNKNOWN').toUpperCase()}
                        color={getStatusColor(systemStatus?.overall || 'unknown')}
                        size='medium'
                      />
                      <Typography
                        variant='body2'
                        color='text.secondary'
                        sx={{ mt: 1 }}
                      >
                        Overall Status
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Box textAlign='center'>
                      <Typography variant='h4' color='primary'>
                        {monitoringData?.data?.database?.status === 'healthy'
                          ? '✓'
                          : '✗'}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Database
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Box textAlign='center'>
                      <Typography variant='h4' color='primary'>
                        {monitoringData?.data?.redis?.status === 'healthy'
                          ? '✓'
                          : '✗'}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Redis Cache
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Box textAlign='center'>
                      <Typography variant='h4' color='primary'>
                        {monitoringData?.data?.system?.status === 'healthy'
                          ? '✓'
                          : '✗'}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        System
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Core Metrics */}
          <Grid item xs={12} md={3}>
            <Card
              sx={{ cursor: 'pointer', '&:hover': { boxShadow: 6 } }}
              onClick={() => navigate(`/${domain}/articles`)}
            >
              <CardContent>
                <Box display='flex' alignItems='center' mb={2}>
                  <Article color='primary' sx={{ mr: 1 }} />
                  <Typography variant='h6'>Articles</Typography>
                </Box>
                <Typography variant='h4' color='primary'>
                  {systemStatus?.articleStats?.data?.total_articles || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Total Articles
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant='body2' color='text.secondary'>
                  Today: {systemStatus?.articleStats?.data?.articles_today || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  This Week:{' '}
                  {systemStatus?.articleStats?.data?.articles_this_week || 0}
                </Typography>
                <Box mt={1}>
                  <Chip
                    label={`Left: ${biasAnalysis.leftBias}`}
                    size='small'
                    color='error'
                    sx={{ mr: 0.5 }}
                  />
                  <Chip
                    label={`Center: ${biasAnalysis.centerBias}`}
                    size='small'
                    color='success'
                    sx={{ mr: 0.5 }}
                  />
                  <Chip
                    label={`Right: ${biasAnalysis.rightBias}`}
                    size='small'
                    color='warning'
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card
              sx={{ cursor: 'pointer', '&:hover': { boxShadow: 6 } }}
              onClick={() => navigate(`/${domain}/rss-feeds`)}
            >
              <CardContent>
                <Box display='flex' alignItems='center' mb={2}>
                  <RssFeedIcon color='primary' sx={{ mr: 1 }} />
                  <Typography variant='h6'>RSS Feeds</Typography>
                </Box>
                <Typography variant='h4' color='primary'>
                  {systemStatus?.rssStats?.data?.active_feeds || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Active Feeds
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant='body2' color='text.secondary'>
                  Total: {systemStatus?.rssStats?.data?.total_feeds || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Errors: {systemStatus?.rssStats?.data?.feeds_with_errors || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card
              sx={{ cursor: 'pointer', '&:hover': { boxShadow: 6 } }}
              onClick={() => navigate(`/${domain}/storylines`)}
            >
              <CardContent>
                <Box display='flex' alignItems='center' mb={2}>
                  <TimelineIcon color='primary' sx={{ mr: 1 }} />
                  <Typography variant='h6'>Storylines</Typography>
                </Box>
                <Typography variant='h4' color='primary'>
                  {systemStatus?.storylineStats?.data?.active_storylines || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Active Storylines
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant='body2' color='text.secondary'>
                  Total:{' '}
                  {systemStatus?.storylineStats?.data?.total_storylines || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Box display='flex' alignItems='center' mb={2}>
                  <SpeedIcon color='primary' sx={{ mr: 1 }} />
                  <Typography variant='h6'>Pipeline Status</Typography>
                </Box>
                <Typography
                  variant='h4'
                  color={
                    systemStatus?.pipelineStatus?.data?.status === 'running'
                      ? 'warning'
                      : systemStatus?.pipelineStatus?.data?.status === 'healthy'
                        ? 'success'
                        : 'primary'
                  }
                >
                  {systemStatus?.pipelineStatus?.data?.status === 'running'
                    ? 'RUNNING'
                    : systemStatus?.pipelineStatus?.data?.status === 'healthy'
                      ? 'HEALTHY'
                      : 'IDLE'}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Processing Status
                </Typography>
                <Divider sx={{ my: 1 }} />
                <Typography variant='body2' color='text.secondary'>
                  Success Rate:{' '}
                  {systemStatus?.pipelineStatus?.data?.success_rate || 0}%
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Active Traces:{' '}
                  {systemStatus?.pipelineStatus?.data?.active_traces || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Total Traces:{' '}
                  {systemStatus?.pipelineStatus?.data?.total_traces || 0}
                </Typography>

                {/* Process Control Buttons with ETA */}
                <Divider sx={{ my: 2 }} />
                <Typography variant='subtitle2' gutterBottom>
                  Process Controls
                </Typography>

                <Box display='flex' flexDirection='column' gap={1}>
                  <Button
                    variant={pipelineRunning ? 'contained' : 'outlined'}
                    color={pipelineRunning ? 'warning' : 'primary'}
                    size='small'
                    startIcon={pipelineRunning ? <StopIcon /> : <PlayArrowIcon />}
                    onClick={() => handleProcessAction('pipeline')}
                    disabled={masterRunning || rssRunning || analysisRunning}
                    fullWidth
                  >
                    {pipelineRunning
                      ? `Pipeline Running ${
                        displayPipelineETA ? `(${displayPipelineETA})` : ''
                      }`
                      : 'Trigger Pipeline'}
                  </Button>

                  <Button
                    variant={rssRunning ? 'contained' : 'outlined'}
                    color={rssRunning ? 'warning' : 'primary'}
                    size='small'
                    startIcon={rssRunning ? <StopIcon /> : <RssFeedIcon />}
                    onClick={() => handleProcessAction('rss')}
                    disabled={masterRunning || pipelineRunning || analysisRunning}
                    fullWidth
                  >
                    {rssRunning
                      ? `RSS Updating ${
                        displayRssETA ? `(${displayRssETA})` : ''
                      }`
                      : 'Update RSS Feeds'}
                  </Button>

                  <Button
                    variant={analysisRunning ? 'contained' : 'outlined'}
                    color={analysisRunning ? 'warning' : 'primary'}
                    size='small'
                    startIcon={analysisRunning ? <StopIcon /> : <Analytics />}
                    onClick={() => handleProcessAction('analysis')}
                    disabled={masterRunning || pipelineRunning || rssRunning}
                    fullWidth
                  >
                    {analysisRunning
                      ? `Analysis Running ${
                        displayAnalysisETA ? `(${displayAnalysisETA})` : ''
                      }`
                      : 'Run AI Analysis'}
                  </Button>

                  <Button
                    variant={masterRunning ? 'contained' : 'outlined'}
                    color={masterRunning ? 'warning' : 'secondary'}
                    size='small'
                    startIcon={masterRunning ? <StopIcon /> : <QueueIcon />}
                    onClick={() => handleProcessAction('master')}
                    disabled={pipelineRunning || rssRunning || analysisRunning}
                    fullWidth
                  >
                    {masterRunning
                      ? 'Master Process Running'
                      : 'Complete All Processes'}
                  </Button>
                </Box>

                {/* Queue Status Indicators */}
                {masterRunning && (
                  <Box mt={2}>
                    <Typography
                      variant='caption'
                      color='primary'
                      display='block'
                      gutterBottom
                    >
                      Process Queue Status:
                    </Typography>
                    <Box display='flex' gap={0.5} flexWrap='wrap'>
                      <Chip
                        label={rssRunning ? 'RSS: Running' : 'RSS: Queued'}
                        color={rssRunning ? 'warning' : 'info'}
                        size='small'
                      />
                      <Chip
                        label={
                          pipelineRunning
                            ? 'Pipeline: Running'
                            : 'Pipeline: Queued'
                        }
                        color={pipelineRunning ? 'warning' : 'info'}
                        size='small'
                      />
                      <Chip
                        label={
                          analysisRunning
                            ? 'Analysis: Running'
                            : 'Analysis: Queued'
                        }
                        color={analysisRunning ? 'warning' : 'info'}
                        size='small'
                      />
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* AI & Analysis Features */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  AI Analysis Features
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <AutoAwesomeIcon
                        color='primary'
                        sx={{ fontSize: 40, mb: 1 }}
                      />
                      <Typography variant='h6'>
                        Multi-Perspective Analysis
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Analyze news from multiple viewpoints
                      </Typography>
                      <Chip
                        label='Available'
                        color='success'
                        size='small'
                        sx={{ mt: 1 }}
                      />
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Analytics color='primary' sx={{ fontSize: 40, mb: 1 }} />
                      <Typography variant='h6'>Impact Assessment</Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Evaluate potential impacts across dimensions
                      </Typography>
                      <Chip
                        label='Available'
                        color='success'
                        size='small'
                        sx={{ mt: 1 }}
                      />
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Schedule color='primary' sx={{ fontSize: 40, mb: 1 }} />
                      <Typography variant='h6'>Predictive Analysis</Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Forecast future developments
                      </Typography>
                      <Chip
                        label='Available'
                        color='success'
                        size='small'
                        sx={{ mt: 1 }}
                      />
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Recent Articles with Bias */}
          {systemStatus?.recentArticles && systemStatus.recentArticles.length > 0 && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' sx={{ mb: 2 }}>
                    Recent Articles
                  </Typography>
                  <List>
                    {systemStatus.recentArticles.map((article: any, index: number) => (
                      <ListItem key={index} divider>
                        <ListItemIcon>
                          <Article />
                        </ListItemIcon>
                        <ListItemText
                          primary={article.title}
                          secondary={
                            <span>
                              {article.source} •{' '}
                              {new Date(
                                article.published_at,
                              ).toLocaleDateString()}
                              {' '}
                              <Chip
                                label={getBiasLabel(article.bias_score || 0)}
                                size='small'
                                color={getBiasColor(article.bias_score || 0)}
                                component='span'
                                sx={{ ml: 0.5, display: 'inline-flex', verticalAlign: 'middle' }}
                              />
                            </span>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Database Metrics */}
          {databaseMetrics && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    Database Metrics
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {databaseMetrics.total_articles}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Total Articles
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {databaseMetrics.total_storylines}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Storylines
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {databaseMetrics.total_rss_feeds}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        RSS Feeds
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {databaseMetrics.recent_articles}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Recent (24h)
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Deduplication Stats */}
          {deduplicationStats && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    Deduplication System
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {deduplicationStats.total_articles}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Articles Processed
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {deduplicationStats.total_clusters}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Clusters
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {deduplicationStats.total_duplicate_pairs}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Duplicate Pairs
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Chip
                        label={deduplicationStats.system_status}
                        color={getStatusColor(deduplicationStats.system_status)}
                      />
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* v5.0 Story Intelligence Widgets */}
          <StoryActivityWidgets domain={domain} navigate={navigate} />
        </Grid>
      </TabPanel>

      {/* System Health Tab */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={3}>
          {systemHealth && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    System Health
                  </Typography>
                  <Chip
                    label={systemHealth.status}
                    color={getStatusColor(systemHealth.status)}
                    sx={{ mb: 2 }}
                  />
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color='success' />
                      </ListItemIcon>
                      <ListItemText
                        primary='Database'
                        secondary={systemHealth.services?.database}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color='success' />
                      </ListItemIcon>
                      <ListItemText
                        primary='Redis'
                        secondary={systemHealth.services?.redis}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color='success' />
                      </ListItemIcon>
                      <ListItemText
                        primary='System'
                        secondary={systemHealth.services?.system}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>
          )}

          {systemMetrics && (
            <>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      CPU Usage
                    </Typography>
                    <Typography variant='h4' color='primary'>
                      {systemMetrics.cpu_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemMetrics.cpu_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Memory Usage
                    </Typography>
                    <Typography variant='h4' color='primary'>
                      {systemMetrics.memory_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemMetrics.memory_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant='h6' gutterBottom>
                      Disk Usage
                    </Typography>
                    <Typography variant='h4' color='primary'>
                      {systemMetrics.disk_percent?.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={systemMetrics.disk_percent}
                      sx={{ mt: 2 }}
                    />
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      </TabPanel>

      {/* Logs & Monitoring Tab */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={3}>
          {/* Log Statistics */}
          {logStats ? (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    Log Statistics (7 days)
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='primary'>
                        {logStats.total_entries || 0}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Total Entries
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='error'>
                        {logStats.error_count || 0}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Errors
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='warning'>
                        {logStats.warning_count || 0}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Warnings
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant='h4' color='info'>
                        {logStats.info_count || 0}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Info
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          ) : (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    Log Statistics
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Log statistics endpoint is not yet implemented.
                    This will show log counts by level once the logging system is fully integrated.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Real-time Logs */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box
                  display='flex'
                  justifyContent='space-between'
                  alignItems='center'
                  mb={2}
                >
                  <Typography variant='h6'>Real-time Logs</Typography>
                  <Box>
                    <Button
                      variant='outlined'
                      startIcon={<DownloadIcon />}
                      onClick={handleExportLogs}
                      sx={{ mr: 1 }}
                    >
                      Export
                    </Button>
                    <Button
                      variant='outlined'
                      startIcon={<CleanupIcon />}
                      onClick={handleCleanupLogs}
                    >
                      Cleanup
                    </Button>
                  </Box>
                </Box>
                {realtimeLogs.length > 0 ? (
                  <List>
                    {realtimeLogs.map((log, index) => (
                      <ListItem key={index} divider>
                        <ListItemIcon>
                          <Chip
                            label={log.level || 'INFO'}
                            color={getLogLevelColor(log.level || 'INFO')}
                            size='small'
                          />
                        </ListItemIcon>
                        <ListItemText
                          primary={log.message || log.title || 'System event'}
                          secondary={`${log.logger || 'system'} - ${log.timestamp ? new Date(log.timestamp).toLocaleString() : 'Unknown time'}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant='body2' color='text.secondary' sx={{ p: 2, textAlign: 'center' }}>
                    No recent logs available. Logs will appear here as system events occur.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Analytics Tab */}
      <TabPanel value={tabValue} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  System Analytics
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Advanced analytics and insights will be implemented here using
                  the structured data from our comprehensive logging and
                  monitoring systems.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* API Status Tab */}
      <TabPanel value={tabValue} index={4}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  API Documentation Status
                </Typography>
                {apiStatus ? (
                  <Box>
                    <Typography variant='h5' gutterBottom>
                      {apiStatus.api?.name} v{apiStatus.api?.version}
                    </Typography>
                    <Chip
                      label={apiStatus.api?.status}
                      color={getStatusColor(apiStatus.api?.status)}
                      sx={{ mb: 2 }}
                    />
                    <Typography variant='body1' paragraph>
                      {apiStatus.api?.description}
                    </Typography>
                    <Typography variant='h6' gutterBottom>
                      Available Features:
                    </Typography>
                    <List>
                      {apiStatus.api?.features?.map(
                        (feature: string, index: number) => (
                          <ListItem key={index}>
                            <ListItemIcon>
                              <CheckCircleIcon color='success' />
                            </ListItemIcon>
                            <ListItemText primary={feature} />
                          </ListItem>
                        ),
                      )}
                    </List>
                  </Box>
                ) : (
                  <CircularProgress size={24} />
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialogOpen}
        onClose={() => setConfirmDialogOpen(false)}
      >
        <DialogTitle>Confirm Process Action</DialogTitle>
        <DialogContent>
          <Typography>
            {confirmAction === 'pipeline' &&
              'This will trigger the article processing pipeline. This may take several minutes and will process all pending articles. Continue?'}
            {confirmAction === 'rss' &&
              'This will update all RSS feeds and collect new articles. This may take a few minutes depending on the number of feeds. Continue?'}
            {confirmAction === 'analysis' &&
              'This will run AI analysis on recent articles including sentiment analysis, entity extraction, and content classification. Continue?'}
            {confirmAction === 'master' &&
              'This will execute all processes in sequence: RSS update, pipeline processing, and AI analysis. This may take several minutes. Continue?'}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={confirmProcessAction}
            variant='contained'
            color='primary'
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>

      {/* Standardized notification component */}
      <NotificationComponent />
    </Box>
  );
};

// Memoize Dashboard component to prevent unnecessary re-renders
export default memo(Dashboard);
