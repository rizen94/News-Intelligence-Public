import {
  Refresh,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Schedule,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  TrendingUp as TrendingUpIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
  History as HistoryIcon,
  AutoAwesome as PredictionIcon,
  RssFeed as RssFeedIcon,
  Analytics,
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
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import apiService from '../../services/apiService';

const Monitoring = () => {
  const [systemStatus, setSystemStatus] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [pipelinePerformance, setPipelinePerformance] = useState(null);
  const [pipelineTraces, setPipelineTraces] = useState([]);
  const [orchestratorDashboard, setOrchestratorDashboard] = useState(null);
  const [dbStats, setDbStats] = useState(null);
  const [devices, setDevices] = useState(null);
  const [healthFeeds, setHealthFeeds] = useState(null);
  const [degradedReasons, setDegradedReasons] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [actionLoading, setActionLoading] = useState({
    pipeline: false,
    rss: false,
    analysis: false,
  });
  const [actionMessage, setActionMessage] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({
    open: false,
    type: null,
    title: '',
    content: '',
  });

  // Debug logging for system status
  console.log('🔍 Current system status:', {
    overall: systemStatus?.overall,
    hasMonitoringData: !!systemStatus?.monitoringData,
    hasHealth: !!systemStatus?.health,
    loading,
    error,
  });

  // Pipeline status
  const [pipelineRunning, setPipelineRunning] = useState(() => {
    const saved = localStorage.getItem('pipelineStatus');
    if (saved) {
      const data = JSON.parse(saved);
      const now = new Date();
      const eta = new Date(data.eta);
      if (eta > now) return true;
      else {
        localStorage.removeItem('pipelineStatus');
        return false;
      }
    }
    return false;
  });
  const [pipelineETA, setPipelineETA] = useState(() => {
    const saved = localStorage.getItem('pipelineStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return new Date(data.eta);
    }
    return null;
  });
  const [pipelineProgress, setPipelineProgress] = useState(() => {
    const saved = localStorage.getItem('pipelineStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return data.progress || 0;
    }
    return 0;
  });

  // RSS Feeds status
  const [rssRunning, setRssRunning] = useState(() => {
    const saved = localStorage.getItem('rssStatus');
    if (saved) {
      const data = JSON.parse(saved);
      const now = new Date();
      const eta = new Date(data.eta);
      if (eta > now) return true;
      else {
        localStorage.removeItem('rssStatus');
        return false;
      }
    }
    return false;
  });
  const [rssETA, setRssETA] = useState(() => {
    const saved = localStorage.getItem('rssStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return new Date(data.eta);
    }
    return null;
  });
  const [rssProgress, setRssProgress] = useState(() => {
    const saved = localStorage.getItem('rssStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return data.progress || 0;
    }
    return 0;
  });

  // AI Analysis status
  const [analysisRunning, setAnalysisRunning] = useState(() => {
    const saved = localStorage.getItem('analysisStatus');
    if (saved) {
      const data = JSON.parse(saved);
      const now = new Date();
      const eta = new Date(data.eta);
      if (eta > now) return true;
      else {
        localStorage.removeItem('analysisStatus');
        return false;
      }
    }
    return false;
  });
  const [analysisETA, setAnalysisETA] = useState(() => {
    const saved = localStorage.getItem('analysisStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return new Date(data.eta);
    }
    return null;
  });
  const [analysisProgress, setAnalysisProgress] = useState(() => {
    const saved = localStorage.getItem('analysisStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return data.progress || 0;
    }
    return 0;
  });

  // Display ETAs for real-time updates
  const [displayPipelineETA, setDisplayPipelineETA] = useState(null);
  const [displayRssETA, setDisplayRssETA] = useState(null);
  const [displayAnalysisETA, setDisplayAnalysisETA] = useState(null);

  // Master switch status
  const [masterRunning, setMasterRunning] = useState(() => {
    const saved = localStorage.getItem('masterStatus');
    if (saved) {
      const data = JSON.parse(saved);
      const now = new Date();
      const eta = new Date(data.eta);
      if (eta > now) return true;
      else {
        localStorage.removeItem('masterStatus');
        return false;
      }
    }
    return false;
  });
  const [masterETA, setMasterETA] = useState(() => {
    const saved = localStorage.getItem('masterStatus');
    if (saved) {
      const data = JSON.parse(saved);
      return new Date(data.eta);
    }
    return null;
  });

  useEffect(() => {
    loadMonitoringData();
    const interval = setInterval(loadMonitoringData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Effect to check pipeline status and update progress
  useEffect(() => {
    if (!pipelineRunning) return;

    const checkPipelineCompletion = () => {
      const now = new Date();
      if (pipelineETA && pipelineETA <= now) {
        // Pipeline should be finished
        setPipelineRunning(false);
        setPipelineETA(null);
        setPipelineProgress(0);
        saveProcessStatus('pipeline', false, null, 0);

        // Show completion message
        setActionMessage({
          type: 'success',
          text: 'Pipeline completed successfully!',
        });

        // Refresh data to get latest results
        loadMonitoringData();
      } else if (pipelineETA) {
        // Update progress based on time elapsed
        const startedAt = new Date(pipelineETA.getTime() - 30 * 60 * 1000); // 30 minutes ago
        const elapsed = (now as Date).getTime() - startedAt.getTime();
        const total = 30 * 60 * 1000; // 30 minutes total
        const progress = Math.min((elapsed / total) * 100, 95); // Cap at 95% until actually done

        setPipelineProgress(progress);
        saveProcessStatus('pipeline', true, pipelineETA, progress);
      }
    };

    // Check immediately
    checkPipelineCompletion();

    // Then check every 10 seconds for ETA updates
    const interval = setInterval(checkPipelineCompletion, 10000);

    return () => clearInterval(interval);
  }, [pipelineRunning, pipelineETA]);

  // Effect to update display ETA every 10 seconds
  useEffect(() => {
    if (!pipelineRunning || !pipelineETA) {
      setDisplayPipelineETA(null);
      return;
    }

    // Set initial display ETA
    setDisplayPipelineETA(pipelineETA);

    // Update display ETA every 10 seconds
    const interval = setInterval(() => {
      const now = new Date();
      if (pipelineETA > now) {
        setDisplayPipelineETA(pipelineETA);
      } else {
        setDisplayPipelineETA(null);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [pipelineRunning, pipelineETA]);

  const loadMonitoringData = async() => {
    try {
      setLoading(true);
      setError(null);

      console.log('🔍 Starting to load monitoring data...');

      const [
        systemResponse,
        pipelineStatusResponse,
        healthResponse,
        orchestratorResponse,
        dbStatsResponse,
        devicesResponse,
        healthFeedsResponse,
      ] = await Promise.allSettled([
        apiService.getMonitoringDashboard().catch((err: any) => {
          console.warn('Monitoring dashboard error:', err);
          return { success: false, data: null };
        }),
        apiService.getPipelineStatus().catch((err: any) => {
          console.warn('Pipeline status error:', err);
          return { success: false, data: {} };
        }),
        apiService.getHealth().catch((err: any) => {
          console.warn('Health check error:', err);
          return { success: false, status: 'unknown' };
        }),
        apiService.getOrchestratorDashboard().catch((err: any) => {
          console.warn('Orchestrator dashboard error:', err);
          return { status: {}, error: (err && err.message) || 'Unavailable' };
        }),
        apiService.getDatabaseStats().catch((err: any) => ({ success: false, data: null })),
        apiService.getDevices().catch((err: any) => ({ success: false, data: null })),
        apiService.getHealthFeeds().catch((err: any) => ({ success: false, data: null })),
      ]);

      const monitoringResult = systemResponse.status === 'fulfilled' && systemResponse.value?.success
        ? systemResponse.value
        : null;
      const pipelineResult = pipelineStatusResponse.status === 'fulfilled' && pipelineStatusResponse.value?.success
        ? pipelineStatusResponse.value
        : null;
      const healthResult = healthResponse.status === 'fulfilled' && healthResponse.value?.success
        ? healthResponse.value
        : null;

      console.log('🔍 API Response received:', { monitoringResult, pipelineResult, healthResult });

      // Extract pipeline data from API response
      const pipelineResponse = pipelineResult?.data ? {
        system_status: pipelineResult.data.pipeline_status || 'idle',
        active_traces_count: pipelineResult.data.active_traces || 0,
        current_stage: pipelineResult.data.current_stage || null,
        overall_progress: pipelineResult.data.overall_progress || 0,
      } : {
        system_status: 'idle',
        active_traces_count: 0,
      };

      const performanceResponse = pipelineResult?.data ? {
        total_traces: pipelineResult.data.total_traces || 0,
        success_rate: pipelineResult.data.success_rate || 0,
        total_articles_processed: pipelineResult.data.articles_processed || 0,
        total_feeds_processed: 0, // Not available in pipeline status
        error_count: pipelineResult.data.errors || 0,
      } : {
        total_traces: 0,
        success_rate: 0,
        total_articles_processed: 0,
        total_feeds_processed: 0,
        error_count: 0,
      };

      const tracesResponse = {
        data: {
          traces: pipelineResult?.data?.recent_traces || [],
        },
      };

      console.log('🔍 Setting system status with data:', {
        overall: monitoringResult?.data?.overall_status || 'unknown',
        hasMonitoringData: !!monitoringResult,
        hasHealth: !!monitoringResult,
        pipelineData: pipelineResult,
      });

      // Calculate overall status from component statuses
      let overallStatus = 'unknown';
      if (monitoringResult?.data) {
        const systemStatus = monitoringResult.data.system?.status || 'unknown';
        const databaseStatus = monitoringResult.data.database?.status || 'unknown';
        const redisStatus = monitoringResult.data.redis?.status || 'unknown';
        const alertsStatus = monitoringResult.data.alerts?.status || 'unknown';

        // Redis is not used (removed from architecture); treat not_used as OK
        const redisOk = redisStatus === 'healthy' || redisStatus === 'not_used';
        if (systemStatus === 'healthy' && databaseStatus === 'healthy' &&
            redisOk && alertsStatus === 'healthy') {
          overallStatus = 'healthy';
        } else if (systemStatus === 'warning' || databaseStatus === 'warning' ||
                   (redisStatus !== 'not_used' && redisStatus !== 'healthy') || alertsStatus === 'warning') {
          overallStatus = 'warning';
        } else if (systemStatus === 'unhealthy' || databaseStatus === 'unhealthy' ||
                   (redisStatus !== 'not_used' && redisStatus !== 'healthy') || alertsStatus === 'unhealthy') {
          overallStatus = 'unhealthy';
        } else {
          // Use API's overall_status if available, otherwise use calculated
          overallStatus = monitoringResult.data.overall_status || 'unknown';
        }
      } else if (healthResult?.status) {
        // Fallback to health check status if monitoring dashboard fails
        overallStatus = healthResult.status;
      } else if (pipelineResult?.data?.pipeline_status) {
        // Fallback to pipeline status if available
        overallStatus = pipelineResult.data.pipeline_status === 'healthy' ? 'healthy' :
          pipelineResult.data.pipeline_status === 'error' ? 'unhealthy' : 'warning';
      }
      if (overallStatus === 'degraded' && Array.isArray(healthResult?.degraded_reasons)) {
        setDegradedReasons(healthResult.degraded_reasons);
      } else {
        setDegradedReasons(null);
      }

      setSystemStatus({
        overall: overallStatus,
        monitoringData: monitoringResult,
        health: monitoringResult,
      });
      setPipelineStatus(pipelineResponse);
      setPipelinePerformance(performanceResponse);
      setPipelineTraces(
        Array.isArray(tracesResponse?.data?.traces)
          ? tracesResponse.data.traces
          : [],
      );
      const orchData = orchestratorResponse.status === 'fulfilled' && orchestratorResponse.value && !orchestratorResponse.value.error
        ? orchestratorResponse.value
        : null;
      setOrchestratorDashboard(orchData);
      if (dbStatsResponse.status === 'fulfilled' && dbStatsResponse.value?.success && dbStatsResponse.value?.data) {
        setDbStats(dbStatsResponse.value.data);
      } else {
        setDbStats(null);
      }
      if (devicesResponse.status === 'fulfilled' && devicesResponse.value?.success && devicesResponse.value?.data) {
        setDevices(devicesResponse.value.data);
      } else {
        setDevices(null);
      }
      if (healthFeedsResponse.status === 'fulfilled' && healthFeedsResponse.value?.success && healthFeedsResponse.value?.data) {
        setHealthFeeds(healthFeedsResponse.value.data);
      } else {
        setHealthFeeds(null);
      }
      setLastUpdate(new Date());

      // Check if pipeline is running
      checkPipelineStatus(pipelineResponse);

      console.log('✅ Monitoring data loaded successfully');
    } catch (err) {
      console.error('❌ Error loading monitoring data:', err);
      setError('Failed to load monitoring data');
    } finally {
      setLoading(false);
    }
  };

  const saveProcessStatus = (processType, running, eta, progress) => {
    const key = `${processType}Status`;
    if (running && eta) {
      const status = {
        running: true,
        eta: eta.toISOString(),
        progress: progress || 0,
        startedAt: new Date().toISOString(),
      };
      localStorage.setItem(key, JSON.stringify(status));
    } else {
      localStorage.removeItem(key);
    }
  };

  const checkPipelineStatus = pipelineResponse => {
    // If we already have a running pipeline from localStorage, don't override it
    if (pipelineRunning) {
      // Check if the stored ETA has passed
      const now = new Date();
      if (pipelineETA && pipelineETA <= now) {
        // Pipeline should be finished
        setPipelineRunning(false);
        setPipelineETA(null);
        setPipelineProgress(0);
        saveProcessStatus('pipeline', false, null, 0);
      }
      return;
    }

    // Only check API response if we don't have a running pipeline
    if (
      pipelineResponse?.system_status === 'running' ||
      pipelineResponse?.active_traces_count > 0
    ) {
      setPipelineRunning(true);

      // Calculate ETA based on pipeline performance data
      const avgDuration = pipelineResponse?.average_duration_ms || 0;
      const totalItems = 1000; // Default total items
      const processedItems = pipelineResponse?.processed_items || 0;

      let eta, progress;

      if (avgDuration > 0 && processedItems > 0) {
        const remainingItems = totalItems - processedItems;
        const estimatedRemainingTime = (remainingItems * avgDuration) / 1000; // Transform to seconds
        eta = new Date(Date.now() + estimatedRemainingTime * 1000);
        progress = (processedItems / totalItems) * 100;
      } else {
        // Fallback ETA calculation
        eta = new Date(Date.now() + 30 * 60 * 1000); // 30 minutes from now
        progress = 0;
      }

      setPipelineETA(eta);
      setPipelineProgress(progress);
      saveProcessStatus('pipeline', true, eta, progress);
    }
  };

  const handleRefresh = () => {
    loadMonitoringData();
  };

  const handleMasterSwitch = () => {
    // Determine which processes are already running and what needs to be done
    const runningProcesses = [];
    const remainingProcesses = [];

    if (rssRunning) {
      runningProcesses.push('RSS Feed Update');
    } else {
      remainingProcesses.push('RSS Feed Update (5 min)');
    }

    if (pipelineRunning) {
      runningProcesses.push('Pipeline Processing');
    } else {
      remainingProcesses.push('Pipeline Processing (30 min)');
    }

    if (analysisRunning) {
      runningProcesses.push('AI Analysis');
    } else {
      remainingProcesses.push('AI Analysis (30 min)');
    }

    // Calculate remaining time
    const remainingTime = remainingProcesses.length * 30; // Rough estimate

    let content = 'This will complete the remaining processes in sequence:\n\n';

    if (runningProcesses.length > 0) {
      content += '**Currently Running:**\n';
      runningProcesses.forEach(process => {
        content += `• ${process} - Will continue and complete\n`;
      });
      content += '\n';
    }

    content += '**Will Execute Next:**\n';
    remainingProcesses.forEach(process => {
      content += `• ${process}\n`;
    });

    content += `\n• **Total estimated time:** ${remainingTime} minutes (remaining processes)
• **Why sequential?** Each process depends on the previous one's output
• **Resource usage:**
  - GPU: ~15-20GB VRAM during ML phases (Llama 3.1 70B model)
  - RAM: ~8-12GB for processing
  - CPU: Multi-core utilization during RSS phase
• **Benefits:** Complete system refresh with data integrity
• **Risks:** Long processing time, high resource usage during ML phases

• **System Status:**
  - Available GPU VRAM: ~31GB (98.4% free)
  - Available RAM: ~46GB (74% free)
  - Current GPU usage: 1.6%

Do you want to proceed with completing the remaining processes?`;

    setConfirmDialog({
      open: true,
      type: 'master',
      title: `Complete Remaining Processes (${remainingProcesses.length} remaining)`,
      content,
    });
  };

  const handleTriggerPipeline = () => {
    // Check if any process is already running
    if (pipelineRunning || rssRunning || analysisRunning || masterRunning) {
      setActionMessage({
        type: 'warning',
        text: `Pipeline is already running or another process is active. ETA: ${formatETA(
          displayPipelineETA || pipelineETA,
        )}`,
      });
      return;
    }

    setConfirmDialog({
      open: true,
      type: 'pipeline',
      title: 'Trigger Article Classification Pipeline',
      content: `This will start the Article Classification Pipeline, which:

• **What it does:**
  - Analyzes and categorizes articles by topic and relevance
  - Applies machine learning models to classify content
  - Processes up to 1,000 articles in the queue
  - Updates article metadata with classification results

• **Benefits:**
  - Improves article organization and discoverability
  - Enables better content filtering and search
  - Provides insights into content trends
  - Enhances the overall intelligence of the system

• **Risks:**
  - May take up to 30 minutes to complete
  - Uses system resources during processing
  - Will temporarily increase CPU usage
  - Cannot be stopped once started

• **Estimated time:** 30 minutes
• **Articles to process:** Up to 1,000

Do you want to proceed with triggering the pipeline?`,
    });
  };

  const handleConfirmAction = async() => {
    const { type } = confirmDialog;
    setConfirmDialog({ open: false, type: null, title: '', content: '' });

    if (type === 'pipeline') {
      await executeTriggerPipeline();
    } else if (type === 'rss') {
      await executeUpdateRSSFeeds();
    } else if (type === 'analysis') {
      await executeRunAIAnalysis();
    } else if (type === 'master') {
      await executeMasterSwitch();
    }
  };

  const executeTriggerPipeline = async() => {
    try {
      setActionLoading(prev => ({ ...prev, pipeline: true }));
      setActionMessage(null);

      const result = await apiService.triggerPipeline();

      // Set pipeline as running with initial ETA
      setPipelineRunning(true);
      const eta = new Date(Date.now() + 30 * 60 * 1000); // 30 minutes from now
      setPipelineETA(eta);
      setPipelineProgress(0);
      saveProcessStatus('pipeline', true, eta, 0);

      setActionMessage({
        type: 'success',
        text: result.message || 'Pipeline triggered successfully',
      });

      // Refresh data more frequently when pipeline is running
      const interval = setInterval(() => {
        loadMonitoringData();
      }, 5000); // Check every 5 seconds

      // Clear interval after 35 minutes (pipeline should be done)
      setTimeout(() => {
        clearInterval(interval);
      }, 35 * 60 * 1000);
    } catch (error: any) {
      setActionMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to trigger pipeline',
      });
    } finally {
      setActionLoading(prev => ({ ...prev, pipeline: false }));
    }
  };

  const handleUpdateRSSFeeds = () => {
    // Check if any process is already running
    if (pipelineRunning || rssRunning || analysisRunning || masterRunning) {
      setActionMessage({
        type: 'warning',
        text: `RSS feeds are already updating or another process is active. ETA: ${formatETA(
          displayRssETA || rssETA,
        )}`,
      });
      return;
    }

    setConfirmDialog({
      open: true,
      type: 'rss',
      title: 'Update RSS Feeds',
      content: `This will refresh all RSS feeds, which:

• **What it does:**
  - Fetches the latest articles from all active RSS feeds
  - Downloads new content and metadata
  - Processes and validates article data
  - Updates the database with new articles

• **Benefits:**
  - Keeps content fresh and up-to-date
  - Discovers new articles and stories
  - Maintains real-time news coverage
  - Ensures continuous data flow

• **Risks:**
  - May take a few minutes to complete
  - Uses network bandwidth during fetching
  - May encounter feed errors or timeouts
  - Some feeds may be temporarily unavailable

• **Estimated time:** 2-5 minutes
• **Feeds to update:** 1 active feed

Do you want to proceed with updating RSS feeds?`,
    });
  };

  const executeUpdateRSSFeeds = async() => {
    try {
      setActionLoading(prev => ({ ...prev, rss: true }));
      setActionMessage(null);

      // Set RSS as running while processing
      setRssRunning(true);
      setRssProgress(50);
      saveProcessStatus('rss', true, new Date(Date.now() + 2 * 60 * 1000), 50);

      const result = await apiService.updateRSSFeeds();

      // Complete - API runs synchronously now
      setRssProgress(100);

      if (result.success) {
        setActionMessage({
          type: 'success',
          text:
            result.message ||
            `RSS feeds update completed - ${
              result.articles_added || 0
            } articles added`,
        });
      } else {
        setActionMessage({
          type: 'error',
          text: result.error || 'RSS feeds update failed',
        });
      }

      // Clear running state after brief display
      setTimeout(() => {
        setRssRunning(false);
        setRssETA(null);
        setRssProgress(0);
        saveProcessStatus('rss', false, null, 0);
      }, 2000);

      // Refresh data after completion
      setTimeout(() => {
        loadMonitoringData();
      }, 2000);
    } catch (error: any) {
      setActionMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to update RSS feeds',
      });
      setRssRunning(false);
      setRssETA(null);
      setRssProgress(0);
      saveProcessStatus('rss', false, null, 0);
    } finally {
      setActionLoading(prev => ({ ...prev, rss: false }));
    }
  };

  const handleRunAIAnalysis = () => {
    // Check if any process is already running
    if (pipelineRunning || rssRunning || analysisRunning || masterRunning) {
      setActionMessage({
        type: 'warning',
        text: `AI analysis is already running or another process is active. ETA: ${formatETA(
          displayAnalysisETA || analysisETA,
        )}`,
      });
      return;
    }

    setConfirmDialog({
      open: true,
      type: 'analysis',
      title: 'Run AI Sentiment Analysis',
      content: `This will start the Sentiment Analysis Pipeline, which:

• **What it does:**
  - Analyzes the emotional tone of articles (positive, negative, neutral)
  - Applies machine learning models to detect sentiment
  - Processes up to 1,000 articles in the queue
  - Updates articles with sentiment scores and classifications

• **Benefits:**
  - Provides insights into public opinion and mood
  - Enables sentiment-based filtering and search
  - Helps identify trending topics and reactions
  - Enhances content understanding and categorization

• **Risks:**
  - May take up to 30 minutes to complete
  - Uses system resources during processing
  - Will temporarily increase CPU usage
  - Cannot be stopped once started

• **Estimated time:** 30 minutes
• **Articles to process:** Up to 1,000

Do you want to proceed with running AI sentiment analysis?`,
    });
  };

  const executeRunAIAnalysis = async() => {
    try {
      setActionLoading(prev => ({ ...prev, analysis: true }));
      setActionMessage(null);

      const result = await apiService.runAIAnalysis();

      // Set analysis as running with ETA (30 minutes)
      setAnalysisRunning(true);
      const eta = new Date(Date.now() + 30 * 60 * 1000); // 30 minutes from now
      setAnalysisETA(eta);
      setAnalysisProgress(0);
      saveProcessStatus('analysis', true, eta, 0);

      setActionMessage({
        type: 'success',
        text: result.message || 'AI analysis started',
      });

      // Refresh data after a short delay
      setTimeout(() => {
        loadMonitoringData();
      }, 2000);
    } catch (error: any) {
      setActionMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to run AI analysis',
      });
    } finally {
      setActionLoading(prev => ({ ...prev, analysis: false }));
    }
  };

  const executeMasterSwitch = async() => {
    try {
      setActionLoading(prev => ({
        ...prev,
        pipeline: true,
        rss: true,
        analysis: true,
      }));
      setActionMessage(null);

      // Calculate remaining time based on what's already running
      let remainingTime = 0;
      if (!rssRunning) remainingTime += 5;
      if (!pipelineRunning) remainingTime += 30;
      if (!analysisRunning) remainingTime += 30;

      // Set master as running with calculated ETA
      setMasterRunning(true);
      const totalETA = new Date(Date.now() + remainingTime * 60 * 1000);
      setMasterETA(totalETA);
      saveProcessStatus('master', true, totalETA, 0);

      const executedProcesses = [];

      setActionMessage({
        type: 'success',
        text: `Master process started! Completing remaining processes (${remainingTime} minutes estimated)...`,
      });

      // Execute only the processes that aren't already running
      if (!rssRunning) {
        executedProcesses.push('RSS Feed Update');
        await executeUpdateRSSFeeds();
        await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
      } else {
        executedProcesses.push('RSS Feed Update (already running)');
      }

      if (!pipelineRunning) {
        executedProcesses.push('Pipeline Processing');
        await executeTriggerPipeline();
        await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
      } else {
        executedProcesses.push('Pipeline Processing (already running)');
      }

      if (!analysisRunning) {
        executedProcesses.push('AI Analysis');
        await executeRunAIAnalysis();
      } else {
        executedProcesses.push('AI Analysis (already running)');
      }

      // Master process completed
      setMasterRunning(false);
      setMasterETA(null);
      saveProcessStatus('master', false, null, 0);

      setActionMessage({
        type: 'success',
        text: `All processes completed successfully! Executed: ${executedProcesses.join(
          ', ',
        )}`,
      });
    } catch (error: any) {
      setActionMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to run master process',
      });
    } finally {
      setActionLoading(prev => ({
        ...prev,
        pipeline: false,
        rss: false,
        analysis: false,
      }));
    }
  };

  const getStatusColor = status => {
    switch (status?.toLowerCase()) {
    case 'healthy':
      return 'success';
    case 'degraded':
      return 'warning';
    case 'error':
      return 'error';
    case 'idle':
      return 'info';
    case 'running':
      return 'success';
    default:
      return 'default';
    }
  };

  const getStatusIcon = status => {
    switch (status?.toLowerCase()) {
    case 'healthy':
      return <CheckCircleIcon />;
    case 'degraded':
      return <WarningIcon />;
    case 'error':
      return <ErrorIcon />;
    case 'idle':
      return <Schedule />;
    case 'running':
      return <SpeedIcon />;
    default:
      return <WarningIcon />;
    }
  };

  const formatDate = dateString => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatDuration = milliseconds => {
    if (!milliseconds) return '0ms';
    if (milliseconds < 1000) return `${milliseconds}ms`;
    if (milliseconds < 60000) return `${(milliseconds / 1000).toFixed(1)}s`;
    return `${(milliseconds / 60000).toFixed(1)}m`;
  };

  const formatETA = (eta: Date | string | null) => {
    if (!eta) return 'Calculating...';
    const now = new Date();
    const etaDate = typeof eta === 'string' ? new Date(eta) : (eta as Date);
    const diff = etaDate.getTime() - now.getTime();

    if (diff <= 0) return 'Completing soon...';

    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m remaining`;
    if (minutes > 0) return `${minutes}m remaining`;
    return 'Less than 1m remaining';
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
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
          System Monitoring
        </Typography>
        <Box display='flex' alignItems='center' gap={2}>
          <Typography variant='body2' color='text.secondary'>
            Last updated:{' '}
            {lastUpdate ? lastUpdate.toLocaleTimeString() : 'Never'}
          </Typography>
          <Tooltip title='Refresh Data'>
            <span>
              <IconButton onClick={handleRefresh} disabled={loading}>
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

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      <Grid container spacing={3}>
        {/* System Health Overview */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant='h6' gutterBottom>
                <NetworkIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                System Health Overview
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Chip
                      icon={getStatusIcon(systemStatus?.overall)}
                      label={systemStatus?.overall?.toUpperCase() || 'UNKNOWN'}
                      color={getStatusColor(systemStatus?.overall)}
                      size='medium'
                    />
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mt: 1 }}
                    >
                      Overall Status
                    </Typography>
                    {systemStatus?.overall === 'degraded' && degradedReasons?.length ? (
                      <Typography variant='caption' display='block' color='text.secondary' sx={{ mt: 0.5, textAlign: 'center' }}>
                        {degradedReasons.join(' · ')}
                      </Typography>
                    ) : null}
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {systemStatus?.monitoringData?.data?.database?.status ===
                      'healthy'
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
                      {['healthy', 'not_used'].includes(systemStatus?.monitoringData?.data?.redis?.status ?? '')
                        ? '—'
                        : '✗'}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Redis (not used)
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {systemStatus?.health?.data?.services?.system ===
                      'healthy'
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

        {/* Resource & Health — Database, Devices, API Health */}
        <Grid item xs={12}>
          <Typography variant='h6' sx={{ mb: 1 }}>
            <StorageIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Resource & Health (all domains)
          </Typography>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant='subtitle1' gutterBottom color='primary'>
                Database
              </Typography>
              {dbStats ? (
                <>
                  <Typography variant='body2'>
                    <strong>Size:</strong> {dbStats.size_pretty}
                  </Typography>
                  <Typography variant='body2'>
                    <strong>Tables:</strong> {dbStats.total_tables ?? 0}
                  </Typography>
                  <Typography variant='body2'>
                    <strong>Articles:</strong> {(dbStats.totals?.articles ?? 0).toLocaleString()}
                  </Typography>
                  <Typography variant='body2'>
                    <strong>Storylines:</strong> {(dbStats.totals?.storylines ?? 0).toLocaleString()}
                  </Typography>
                  <Typography variant='body2'>
                    <strong>RSS feeds:</strong> {(dbStats.totals?.rss_feeds ?? 0).toLocaleString()}
                  </Typography>
                </>
              ) : (
                <Typography variant='body2' color='text.secondary'>Loading…</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant='subtitle1' gutterBottom color='primary'>
                Devices (Legion, Widow, NAS)
              </Typography>
              {devices?.devices?.length ? (
                <Box component='ul' sx={{ m: 0, pl: 2 }}>
                  {devices.devices.map((d: any) => (
                    <li key={d.name}>
                      <Typography variant='body2'>
                        <strong>{d.name}</strong> ({d.type})
                        {d.disk != null && (
                          <> — Disk: {d.disk.percent}% used</>
                        )}
                        {d.project_usage_bytes != null && (
                          <> — Project: {(d.project_usage_bytes / 1024 / 1024).toFixed(1)} MB</>
                        )}
                        {d.processes?.length != null && (
                          <> — {d.processes.length} processes</>
                        )}
                        {d.status && d.status !== 'ok' && (
                          <Chip size='small' label={d.status} sx={{ ml: 0.5 }} />
                        )}
                      </Typography>
                    </li>
                  ))}
                </Box>
              ) : (
                <Typography variant='body2' color='text.secondary'>Loading…</Typography>
              )}
              {devices?.total_project_usage_bytes != null && (
                <Typography variant='body2' sx={{ mt: 1 }}>
                  Total project space: {(devices.total_project_usage_bytes / 1024 / 1024).toFixed(1)} MB
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant='subtitle1' gutterBottom color='primary'>
                API Health Feeds
              </Typography>
              {healthFeeds?.feeds?.length ? (
                <Box component='ul' sx={{ m: 0, pl: 2 }}>
                  {healthFeeds.feeds.map((f: any) => (
                    <li key={f.name}>
                      <Typography variant='body2'>
                        {f.last_ok === true ? (
                          <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main', verticalAlign: 'middle', mr: 0.5 }} />
                        ) : f.last_ok === false ? (
                          <WarningIcon sx={{ fontSize: 16, color: 'warning.main', verticalAlign: 'middle', mr: 0.5 }} />
                        ) : null}
                        <strong>{f.name}</strong>
                        {f.last_message != null && ` — ${f.last_message}`}
                        {f.last_check_at && (
                          <Typography component='span' variant='caption' display='block'>
                            Last check: {new Date(f.last_check_at).toLocaleString()}
                          </Typography>
                        )}
                      </Typography>
                    </li>
                  ))}
                </Box>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  {healthFeeds ? 'No feeds configured or health monitor not run yet.' : 'Loading…'}
                </Typography>
              )}
              {healthFeeds?.interval_seconds && (
                <Typography variant='caption' color='text.secondary' display='block' sx={{ mt: 1 }}>
                  Health monitor runs every {healthFeeds.interval_seconds}s; alerts created on failure.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Pipeline Status */}
        <Grid item xs={12} md={6}>
          <Card
            sx={{ height: '300px', display: 'flex', flexDirection: 'column' }}
          >
            <CardContent
              sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <Typography variant='h6' gutterBottom>
                <SpeedIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Pipeline Status
              </Typography>
              <Box display='flex' alignItems='center' gap={2} mb={2}>
                <Chip
                  icon={getStatusIcon(pipelineStatus?.system_status)}
                  label={pipelineStatus?.system_status || 'Unknown'}
                  color={getStatusColor(pipelineStatus?.system_status)}
                  size='medium'
                />
                <Typography variant='body2' color='text.secondary'>
                  Active traces: {pipelineStatus?.active_traces_count || 0}
                </Typography>
              </Box>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {pipelinePerformance?.total_traces || 0}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Total Traces
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {pipelinePerformance?.success_rate || 0}%
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Success Rate
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Orchestrator Coordinator */}
        <Grid item xs={12} md={6}>
          <Card
            sx={{ height: '300px', display: 'flex', flexDirection: 'column' }}
          >
            <CardContent
              sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <Typography variant='h6' gutterBottom>
                <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Orchestrator
              </Typography>
              {orchestratorDashboard ? (
                <>
                  <Box display='flex' alignItems='center' gap={2} mb={2}>
                    <Chip
                      icon={orchestratorDashboard.status?.running ? getStatusIcon('running') : getStatusIcon('idle')}
                      label={orchestratorDashboard.status?.running ? 'Running' : 'Idle'}
                      color={orchestratorDashboard.status?.running ? 'success' : 'default'}
                      size='medium'
                    />
                    <Typography variant='body2' color='text.secondary'>
                      Cycle: {orchestratorDashboard.status?.current_cycle ?? '—'}
                    </Typography>
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant='body2' color='text.secondary' paragraph>
                      Collection governor, learning, and resource coordination. Decision log and metrics available via API.
                    </Typography>
                    <Button
                      size='small'
                      variant='outlined'
                      href='/api/orchestrator/dashboard'
                      target='_blank'
                      rel='noopener noreferrer'
                    >
                      Open dashboard API
                    </Button>
                  </Box>
                </>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  Orchestrator dashboard unavailable (API not running or not configured).
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Performance Metrics */}
        <Grid item xs={12} md={6}>
          <Card
            sx={{ height: '300px', display: 'flex', flexDirection: 'column' }}
          >
            <CardContent
              sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <Typography variant='h6' gutterBottom>
                <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Performance Metrics
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {pipelinePerformance?.total_articles_processed || 0}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Articles Processed
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {pipelinePerformance?.total_feeds_processed || 0}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Feeds Processed
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign='center'>
                    <Typography variant='h4' color='primary'>
                      {pipelinePerformance?.error_count || 0}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Errors
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Pipeline Traces */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant='h6' gutterBottom>
                <TimelineIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Recent Pipeline Traces
              </Typography>
              {!Array.isArray(pipelineTraces) || pipelineTraces.length === 0 ? (
                <Box textAlign='center' py={4}>
                  <TimelineIcon
                    sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }}
                  />
                  <Typography variant='h6' color='text.secondary' gutterBottom>
                    No pipeline traces found
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Pipeline traces will appear here once the system starts
                    processing articles
                  </Typography>
                </Box>
              ) : (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Trace ID</TableCell>
                        <TableCell>Stage</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Created At</TableCell>
                        <TableCell>Error Message</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(Array.isArray(pipelineTraces)
                        ? pipelineTraces
                        : []
                      ).map(trace => (
                        <TableRow key={trace.id || trace.trace_id}>
                          <TableCell>
                            <Typography variant='body2' fontFamily='monospace'>
                              {trace.trace_id || trace.id || 'N/A'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={trace.stage || 'Unknown'}
                              size='small'
                              variant='outlined'
                            />
                          </TableCell>
                          <TableCell>
                            <Chip
                              icon={getStatusIcon(trace.status)}
                              label={trace.status || 'Unknown'}
                              color={getStatusColor(trace.status)}
                              size='small'
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant='body2'>
                              {trace.created_at ? formatDate(trace.created_at) : 'N/A'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant='body2' color={trace.error_message ? 'error' : 'text.secondary'}>
                              {trace.error_message || '-'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* AI Analysis Features Status */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant='h6' gutterBottom>
                <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                AI Analysis Features Status
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <AutoAwesomeIcon
                      color='primary'
                      sx={{ fontSize: 40, mb: 1 }}
                    />
                    <Typography variant='h6'>
                      Multi-Perspective Analysis
                    </Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mt: 1 }}
                    >
                      Analyze news from multiple viewpoints
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <AssessmentIcon
                      color='primary'
                      sx={{ fontSize: 40, mb: 1 }}
                    />
                    <Typography variant='h6'>Impact Assessment</Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mt: 1 }}
                    >
                      Evaluate potential impacts across dimensions
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <HistoryIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant='h6'>Historical Context</Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mt: 1 }}
                    >
                      Connect current events to historical patterns
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <PredictionIcon
                      color='primary'
                      sx={{ fontSize: 40, mb: 1 }}
                    />
                    <Typography variant='h6'>Predictive Analysis</Typography>
                    <Chip
                      label='Available'
                      color='success'
                      size='small'
                      sx={{ mt: 1 }}
                    />
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mt: 1 }}
                    >
                      Forecast future developments and trends
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* System Resources */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant='h6' gutterBottom>
                <MemoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                System Resources
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemIcon>
                    <MemoryIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary='Memory Usage'
                    secondary={`${
                      systemStatus?.monitoringData?.data?.system
                        ?.memory_percent || 0
                    }%`}
                  />
                  <LinearProgress
                    variant='determinate'
                    value={
                      systemStatus?.monitoringData?.data?.system
                        ?.memory_percent || 0
                    }
                    sx={{ width: 100, ml: 2 }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <StorageIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary='Disk Usage'
                    secondary={`${
                      systemStatus?.monitoringData?.data?.system
                        ?.disk_percent || 0
                    }%`}
                  />
                  <LinearProgress
                    variant='determinate'
                    value={
                      systemStatus?.monitoringData?.data?.system
                        ?.disk_percent || 0
                    }
                    sx={{ width: 100, ml: 2 }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <SpeedIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary='CPU Usage'
                    secondary={`${
                      systemStatus?.monitoringData?.data?.system?.cpu_percent ||
                      0
                    }%`}
                  />
                  <LinearProgress
                    variant='determinate'
                    value={
                      systemStatus?.monitoringData?.data?.system?.cpu_percent ||
                      0
                    }
                    sx={{ width: 100, ml: 2 }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MemoryIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary='GPU VRAM Usage'
                    secondary={
                      systemStatus?.monitoringData?.data?.system
                        ?.gpu_vram_percent
                        ? `${systemStatus.monitoringData.data.system.gpu_vram_percent}%`
                        : 'No GPU data available'
                    }
                  />
                  <LinearProgress
                    variant='determinate'
                    value={
                      systemStatus?.monitoringData?.data?.system
                        ?.gpu_vram_percent || 0
                    }
                    sx={{ width: 100, ml: 2 }}
                    color={
                      (systemStatus?.monitoringData?.data?.system
                        ?.gpu_vram_percent || 0) > 80
                        ? 'error'
                        : 'primary'
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <SpeedIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary='GPU Utilization'
                    secondary={
                      systemStatus?.monitoringData?.data?.system
                        ?.gpu_utilization_percent
                        ? `${systemStatus.monitoringData.data.system.gpu_utilization_percent}%`
                        : 'No GPU data available'
                    }
                  />
                  <LinearProgress
                    variant='determinate'
                    value={
                      systemStatus?.monitoringData?.data?.system
                        ?.gpu_utilization_percent || 0
                    }
                    sx={{ width: 100, ml: 2 }}
                    color='secondary'
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant='h6' gutterBottom>
                Quick Actions
              </Typography>
              <Box display='flex' flexDirection='column' gap={2}>
                <Button
                  variant='contained'
                  startIcon={<Refresh />}
                  onClick={handleRefresh}
                  disabled={loading}
                >
                  Refresh All Data
                </Button>
                <Button
                  variant='contained'
                  color='secondary'
                  startIcon={<SpeedIcon />}
                  onClick={handleMasterSwitch}
                  disabled={
                    actionLoading.pipeline ||
                    actionLoading.rss ||
                    actionLoading.analysis ||
                    masterRunning ||
                    pipelineRunning ||
                    rssRunning ||
                    analysisRunning
                  }
                  sx={{ mt: 1 }}
                >
                  {masterRunning
                    ? 'Master Process Running'
                    : 'Complete All Processes'}
                </Button>
                <Button
                  variant='outlined'
                  startIcon={<SpeedIcon />}
                  onClick={handleTriggerPipeline}
                  disabled={
                    actionLoading.pipeline ||
                    pipelineRunning ||
                    masterRunning ||
                    rssRunning ||
                    analysisRunning
                  }
                  color={
                    pipelineRunning
                      ? 'warning'
                      : masterRunning && !pipelineRunning
                        ? 'info'
                        : 'primary'
                  }
                >
                  {actionLoading.pipeline
                    ? 'Triggering...'
                    : pipelineRunning
                      ? `Pipeline Running (${pipelineProgress.toFixed(0)}%)`
                      : masterRunning && !pipelineRunning
                        ? 'Pipeline Queued'
                        : 'Trigger Pipeline'}
                </Button>
                {pipelineRunning && (
                  <Box
                    sx={{
                      mt: 1,
                      p: 2,
                      bgcolor: 'warning.light',
                      borderRadius: 1,
                    }}
                  >
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>Pipeline Status:</strong> Running
                    </Typography>
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>Progress:</strong> {pipelineProgress.toFixed(0)}%
                    </Typography>
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>ETA:</strong> {formatETA(displayPipelineETA)}
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={pipelineProgress}
                      sx={{ mt: 1, bgcolor: 'warning.dark' }}
                    />
                    <Typography
                      variant='caption'
                      color='warning.contrastText'
                      sx={{ mt: 1, display: 'block' }}
                    >
                      ⚠️ Pipeline is running. Button is disabled until
                      completion.
                    </Typography>
                  </Box>
                )}
                {masterRunning && !pipelineRunning && (
                  <Box
                    sx={{ mt: 1, p: 2, bgcolor: 'info.light', borderRadius: 1 }}
                  >
                    <Typography
                      variant='body2'
                      color='info.contrastText'
                      gutterBottom
                    >
                      <strong>Pipeline Status:</strong> Queued for execution
                    </Typography>
                    <Typography
                      variant='caption'
                      color='info.contrastText'
                      sx={{ display: 'block' }}
                    >
                      ⏳ Pipeline will start after RSS feeds complete
                    </Typography>
                  </Box>
                )}
                <Button
                  variant='outlined'
                  startIcon={<Analytics />}
                  onClick={handleRunAIAnalysis}
                  disabled={
                    actionLoading.analysis ||
                    analysisRunning ||
                    masterRunning ||
                    pipelineRunning ||
                    rssRunning
                  }
                  color={
                    analysisRunning
                      ? 'warning'
                      : masterRunning && !analysisRunning
                        ? 'info'
                        : 'primary'
                  }
                >
                  {actionLoading.analysis
                    ? 'Running...'
                    : analysisRunning
                      ? `AI Analysis Running (${analysisProgress.toFixed(0)}%)`
                      : masterRunning && !analysisRunning
                        ? 'AI Analysis Queued'
                        : 'Run AI Analysis'}
                </Button>
                {analysisRunning && (
                  <Box
                    sx={{
                      mt: 1,
                      p: 2,
                      bgcolor: 'warning.light',
                      borderRadius: 1,
                    }}
                  >
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>AI Analysis Status:</strong> Running
                    </Typography>
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>Progress:</strong> {analysisProgress.toFixed(0)}%
                    </Typography>
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>ETA:</strong> {formatETA(displayAnalysisETA)}
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={analysisProgress}
                      sx={{ mt: 1, bgcolor: 'warning.dark' }}
                    />
                    <Typography
                      variant='caption'
                      color='warning.contrastText'
                      sx={{ mt: 1, display: 'block' }}
                    >
                      ⚠️ AI Analysis is running. Button is disabled until
                      completion.
                    </Typography>
                  </Box>
                )}
                {masterRunning && !analysisRunning && (
                  <Box
                    sx={{ mt: 1, p: 2, bgcolor: 'info.light', borderRadius: 1 }}
                  >
                    <Typography
                      variant='body2'
                      color='info.contrastText'
                      gutterBottom
                    >
                      <strong>AI Analysis Status:</strong> Queued for execution
                    </Typography>
                    <Typography
                      variant='caption'
                      color='info.contrastText'
                      sx={{ display: 'block' }}
                    >
                      ⏳ AI Analysis will start after pipeline completes
                    </Typography>
                  </Box>
                )}
                <Button
                  variant='outlined'
                  startIcon={<RssFeedIcon />}
                  onClick={handleUpdateRSSFeeds}
                  disabled={
                    actionLoading.rss ||
                    rssRunning ||
                    masterRunning ||
                    pipelineRunning ||
                    analysisRunning
                  }
                  color={
                    rssRunning
                      ? 'warning'
                      : masterRunning && !rssRunning
                        ? 'info'
                        : 'primary'
                  }
                >
                  {actionLoading.rss
                    ? 'Updating...'
                    : rssRunning
                      ? `RSS Updating (${rssProgress.toFixed(0)}%)`
                      : masterRunning && !rssRunning
                        ? 'RSS Feeds Queued'
                        : 'Update RSS Feeds'}
                </Button>
                {rssRunning && (
                  <Box
                    sx={{
                      mt: 1,
                      p: 2,
                      bgcolor: 'warning.light',
                      borderRadius: 1,
                    }}
                  >
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>RSS Update Status:</strong> Running
                    </Typography>
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>Progress:</strong> {rssProgress.toFixed(0)}%
                    </Typography>
                    <Typography
                      variant='body2'
                      color='warning.contrastText'
                      gutterBottom
                    >
                      <strong>ETA:</strong> {formatETA(displayRssETA)}
                    </Typography>
                    <LinearProgress
                      variant='determinate'
                      value={rssProgress}
                      sx={{ mt: 1, bgcolor: 'warning.dark' }}
                    />
                    <Typography
                      variant='caption'
                      color='warning.contrastText'
                      sx={{ mt: 1, display: 'block' }}
                    >
                      ⚠️ RSS feeds are updating. Button is disabled until
                      completion.
                    </Typography>
                  </Box>
                )}
                {masterRunning && !rssRunning && (
                  <Box
                    sx={{ mt: 1, p: 2, bgcolor: 'info.light', borderRadius: 1 }}
                  >
                    <Typography
                      variant='body2'
                      color='info.contrastText'
                      gutterBottom
                    >
                      <strong>RSS Update Status:</strong> Queued for execution
                    </Typography>
                    <Typography
                      variant='caption'
                      color='info.contrastText'
                      sx={{ display: 'block' }}
                    >
                      ⏳ RSS feeds will update first in the sequence
                    </Typography>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Action Messages */}
        {actionMessage && (
          <Grid item xs={12}>
            <Alert
              severity={actionMessage.type}
              onClose={() => setActionMessage(null)}
              sx={{ mt: 2 }}
            >
              {actionMessage.text}
            </Alert>
          </Grid>
        )}
      </Grid>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialog.open}
        onClose={() =>
          setConfirmDialog({ open: false, type: null, title: '', content: '' })
        }
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>{confirmDialog.title}</DialogTitle>
        <DialogContent>
          <Typography variant='body1' sx={{ whiteSpace: 'pre-line', mt: 1 }}>
            {confirmDialog.content}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() =>
              setConfirmDialog({
                open: false,
                type: null,
                title: '',
                content: '',
              })
            }
            color='inherit'
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirmAction}
            variant='contained'
            color='primary'
            autoFocus
          >
            Proceed
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Monitoring;
