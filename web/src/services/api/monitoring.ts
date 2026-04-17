/**
 * System monitoring API — health, pipeline, deduplication, intelligence, finance.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

export const monitoringApi = {
  async getHealth() {
    try {
      const response = await getApi().get('/api/system_monitoring/health');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch health', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  /** Enhanced monitoring: connection status (API, database, webserver) + live activity feed */
  async getMonitoringOverview() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/monitoring/overview',
        // DB check + activity enrich can be slow under pool pressure; align with other monitor GETs
        { timeout: 120000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch monitoring overview', error as Error);
      return {
        success: false,
        connections: {},
        activities: { current: [], recent: [] },
        error: (error as any).message,
      };
    }
  },

  async getDatabaseStats() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/database/stats'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch database stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDevices() {
    try {
      const response = await getApi().get('/api/system_monitoring/devices');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch devices', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getHealthFeeds() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/health/feeds'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch health feeds', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMonitoringDashboard() {
    try {
      const response = await getApi().get('/api/system_monitoring/status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch monitoring dashboard', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getPipelineStatus() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/pipeline_status',
        { timeout: 120000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch pipeline status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getOrchestratorDashboard(params?: { decision_log_limit?: number }) {
    try {
      const response = await getApi().get('/api/orchestrator/dashboard', {
        params,
        timeout: 60000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch orchestrator dashboard', error as Error);
      return { success: false, status: {}, error: (error as any).message };
    }
  },

  /** Data sources actually pulled in the last N minutes (RSS feeds, orchestrator sources, pipeline stages). */
  async getSourcesCollected(minutes: number = 30) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/sources_collected',
        {
          params: { minutes },
          timeout: 60000,
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch sources collected', error as Error);
      return { success: false, data: {}, error: (error as any).message };
    }
  },

  /** What has been running vs not triggered recently (phases, pipeline checkpoints, activity log). */
  async getProcessRunSummary(hours: number = 24, activityLines: number = 80) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/process_run_summary',
        {
          params: { hours, activity_lines: activityLines },
          timeout: 60000,
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch process run summary', error as Error);
      return { success: false, data: {}, error: (error as any).message };
    }
  },

  /** Automation manager: phases with last_run, queue_size, active_workers (phase workers), phase_workers_configured, max_concurrent_tasks. */
  async getAutomationStatus() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/automation/status',
        { timeout: 60000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch automation status', error as Error);
      return {
        success: false,
        data: { phases: [], queue_size: 0 },
        error: (error as any).message,
      };
    }
  },

  /** Backlog progression: articles/documents/storylines remaining and catch-up ETA. */
  async getBacklogStatus() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/backlog_status',
        // Many cross-schema + intelligence.* queries; 12s was too tight under DB load.
        { timeout: 60000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch backlog status', error as Error);
      return { success: false, data: null, error: (error as any).message };
    }
  },

  /** Full processing pulse including per-phase unprocessed row counts (backlog_metrics). */
  async getProcessingProgress() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/processing_progress',
        {
          params: { include_pending_metrics: true },
          timeout: 300000,
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch processing progress', error as Error);
      return { success: false, data: null, error: (error as any).message };
    }
  },

  /** Hourly GPU utilization + VRAM % (from nvidia-smi samples; requires migration 209). */
  async getGpuMetricHistory(hours: number = 72) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/gpu_metric_history',
        { params: { hours }, timeout: 30000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch GPU metric history', error as Error);
      return { success: false, data: null, error: (error as any).message };
    }
  },

  /** PDF document collectors: success vs HTTP 403/404 / parser failures by source (last N days). */
  async getDocumentSourcesHealth(windowDays: number = 30) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/document_sources/health',
        { params: { window_days: windowDays }, timeout: 15000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to fetch document sources health',
        error as Error
      );
      return { success: false, data: null, error: (error as any).message };
    }
  },

  /** Live DB sessions (pg_stat_activity) for monitoring long-held connections. */
  async getDatabaseConnections(params?: {
    limit?: number;
    long_running_seconds?: number;
  }) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/database/connections',
        // pg_stat_activity under load can exceed 20s; align with heavy Monitor calls.
        { params, timeout: 60000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch database connections', error as Error);
      return {
        success: false,
        data: { sessions: [] },
        error: (error as any).message,
      };
    }
  },

  /** Request that a phase run now (e.g. rss_processing, digest_generation). */
  async triggerPhase(
    phase: string,
    options?: {
      domain?: string;
      storyline_id?: number;
      /** Only for phase nightly_enrichment_context: run unified drain outside 02:00–05:00 local */
      force_nightly_unified_pipeline?: boolean;
    }
  ) {
    try {
      const response = await getApi().post(
        '/api/system_monitoring/monitoring/trigger_phase',
        {
          phase,
          ...options,
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger phase', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerPipeline() {
    try {
      const response = await getApi().post(
        '/api/system_monitoring/pipeline/trigger'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger pipeline', error as Error);
      return {
        success: false,
        error:
          (error as any).message || 'Pipeline trigger API not yet implemented',
      };
    }
  },

  async getSystemHealth() {
    try {
      const response = await getApi().get('/api/system_monitoring/health');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get system health', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getSystemMetrics() {
    try {
      const response = await getApi().get('/api/system_monitoring/metrics');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get system metrics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDatabaseMetrics() {
    try {
      const response = await getApi().get('/api/system_monitoring/dashboard');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get database metrics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getLogStatistics(days: number = 7) {
    try {
      const response = await getApi().get('/api/system_monitoring/logs/stats', {
        params: { days },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get log statistics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getRealtimeLogs(limit: number = 50) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/logs/realtime',
        {
          params: { limit },
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get realtime logs', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getAPIStatus() {
    try {
      const response = await getApi().get('/api/system_monitoring/status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get API status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  /** Read-only SQL explorer (requires NEWS_INTEL_SQL_EXPLORER=true on API). */
  async getSqlExplorerEnabled() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/sql_explorer/enabled'
      );
      return response.data as { success?: boolean; enabled?: boolean };
    } catch (error) {
      Logger.apiError('SQL explorer enabled check failed', error as Error);
      return { success: false, enabled: false, error: (error as any).message };
    }
  },

  async getSqlExplorerSchema() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/sql_explorer/schema',
        { timeout: 60000 }
      );
      return response.data as {
        success?: boolean;
        tables?: Array<{
          schema: string;
          table: string;
          columns: Array<{
            name: string;
            data_type: string;
            nullable: boolean;
          }>;
        }>;
        error?: string;
      };
    } catch (error) {
      Logger.apiError('SQL explorer schema failed', error as Error);
      return { success: false, tables: [], error: (error as any).message };
    }
  },

  async postSqlExplorerQuery(sql: string, maxRows: number = 500) {
    try {
      const response = await getApi().post(
        '/api/system_monitoring/sql_explorer/query',
        { sql, max_rows: maxRows },
        { timeout: 120000 }
      );
      return response.data as {
        success?: boolean;
        columns?: string[];
        rows?: unknown[][];
        row_count_returned?: number;
        truncated?: boolean;
        cursor_rowcount?: number | null;
        detail?: string;
      };
    } catch (error: unknown) {
      Logger.apiError('SQL explorer query failed', error as Error);
      const ax = error as {
        response?: { data?: { detail?: unknown } };
        message?: string;
      };
      const detail = ax?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail
              .map((d: { msg?: string }) => d?.msg)
              .filter(Boolean)
              .join('; ')
          : ax?.message ?? 'Request failed';
      return {
        success: false,
        columns: [],
        rows: [],
        error: msg || 'Request failed',
      };
    }
  },

  async getDuplicateStats() {
    try {
      const response = await getApi().get('/api/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get duplicate stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async detectDuplicates(
    params: {
      similarity_threshold?: number;
      check_url?: boolean;
      check_content?: boolean;
    } = {}
  ) {
    try {
      const response = await getApi().get('/api/articles/duplicates/detect', {
        params,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to detect duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getURLDuplicates() {
    try {
      const response = await getApi().get('/api/articles/duplicates/url');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get URL duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getContentDuplicates() {
    try {
      const response = await getApi().get('/api/articles/duplicates/content');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get content duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getSimilarArticles(articleId: number, threshold: number = 0.8) {
    try {
      const response = await getApi().get('/api/articles/duplicates/similar', {
        params: { article_id: articleId, threshold },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get similar articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async autoMergeDuplicates(dryRun: boolean = true) {
    try {
      const response = await getApi().post(
        '/api/articles/duplicates/auto_merge',
        { dry_run: dryRun }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to auto-merge duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async preventDuplicates() {
    try {
      const response = await getApi().post('/api/articles/duplicates/prevent');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to prevent duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async analyzeSimilarity(articleId1: number, articleId2: number) {
    try {
      const response = await getApi().post(
        '/api/articles/duplicates/analyze_similarity',
        { article_id_1: articleId1, article_id_2: articleId2 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to analyze similarity', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDeduplicationStats() {
    try {
      const response = await getApi().get('/api/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get deduplication stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMLQueueStatus() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/ml/queue_status'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get ML queue status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getAllMLProcessingStatus() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/ml/processing_status'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get ML processing status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMLTimingStats() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/ml/timing_stats'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get ML timing stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async queueArticleForMLProcessing(
    articleId: number,
    operation: string,
    priority: string = 'normal',
    model?: string
  ) {
    try {
      const response = await getApi().post('/api/system_monitoring/ml/queue', {
        article_id: articleId,
        operation,
        priority,
        model,
      });
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to queue article for ML processing',
        error as Error
      );
      return { success: false, error: (error as any).message };
    }
  },

  async getFeedbackLoopStatus() {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/feedback_loop/status'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get feedback loop status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async startFeedbackLoop() {
    try {
      const response = await getApi().post(
        '/api/system_monitoring/feedback_loop/start'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to start feedback loop', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async stopFeedbackLoop() {
    try {
      const response = await getApi().post(
        '/api/system_monitoring/feedback_loop/stop'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to stop feedback loop', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async runAIAnalysis() {
    try {
      const response = await getApi().post(
        '/api/system_monitoring/ai-analysis/run'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to run AI analysis', error as Error);
      return {
        success: false,
        error: (error as any).message || 'AI analysis API not yet implemented',
      };
    }
  },

  async getMarketTrends(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/market-trends`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch market trends', error as Error);
      return {
        success: false,
        error:
          (error as any).message || 'Market trends API not yet implemented',
        data: null,
      };
    }
  },

  async getMarketPatterns(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/market-patterns`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch market patterns', error as Error);
      return {
        success: false,
        error:
          (error as any).message || 'Market patterns API not yet implemented',
        data: null,
      };
    }
  },

  async getCorporateAnnouncements(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/corporate-announcements`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to fetch corporate announcements',
        error as Error
      );
      return {
        success: false,
        error:
          (error as any).message ||
          'Corporate announcements API not yet implemented',
        data: null,
      };
    }
  },

  // Finance infrastructure data (FRED, market store)
  async getFinanceDataSources(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/data-sources`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch finance data sources', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getFinanceMarketData(
    params: {
      source?: string;
      symbol?: string;
      start_date?: string;
      end_date?: string;
    } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/market-data`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch finance market data', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getGoldData(
    params: {
      source?: string;
      start_date?: string;
      end_date?: string;
      fetch?: boolean;
    } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/finance/gold`, {
        params,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch gold data', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerGoldFetch(
    params: { start_date?: string; end_date?: string } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/finance/gold/fetch`,
        null,
        { params: params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger gold fetch', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getGoldHistory(
    params: { days?: number; fetch_if_empty?: boolean } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/gold/history`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch gold history', error as Error);
      return {
        success: false,
        data: { observations: [] },
        error: (error as Error).message,
      };
    }
  },

  async getGoldSpot(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/gold/spot`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch gold spot', error as Error);
      return { success: false, data: {}, error: (error as Error).message };
    }
  },

  async getGoldAuthority(
    params: { authorities?: string } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/gold/authority`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch gold authority', error as Error);
      return { success: false, data: {}, error: (error as Error).message };
    }
  },

  async getGoldGeoEvents(params: { limit?: number } = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/gold/geo-events`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch gold geo-events', error as Error);
      return {
        success: false,
        data: { events: [], by_region: {} },
        error: (error as Error).message,
      };
    }
  },

  /** List of commodities from registry (id, label) for dashboard/nav. */
  async getCommodities(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodities`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch commodities list', error as Error);
      return { success: false, data: [], error: (error as Error).message };
    }
  },

  /** Commodity-relevant news (financial relevance filter applied). */
  async getCommodityNews(
    commodity: string,
    params: { hours?: number; max_items?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/${commodity}/news`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(`Failed to fetch ${commodity} news`, error as Error);
      return {
        success: false,
        data: { items: [] },
        error: (error as Error).message,
      };
    }
  },

  /** Commodity-relevant supply-chain contexts (mining, EDGAR). */
  async getCommoditySupplyChain(
    commodity: string,
    params: { hours?: number; max_items?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/${commodity}/supply-chain`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        `Failed to fetch ${commodity} supply-chain`,
        error as Error
      );
      return {
        success: false,
        data: { items: [] },
        error: (error as Error).message,
      };
    }
  },

  /** Commodity id from registry (e.g. gold, silver, platinum, oil, gas). */
  async getCommodityHistory(
    commodity: string,
    params: { days?: number; fetch_if_empty?: boolean } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/${commodity}/history`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(`Failed to fetch ${commodity} history`, error as Error);
      return {
        success: false,
        data: { observations: [] },
        error: (error as Error).message,
      };
    }
  },

  /** Persist a window of prices (FRED / amalgamator / metals fallback). Use for oil/gas backfill or after config changes. */
  async triggerCommodityPriceFetch(
    commodity: string,
    params: { days?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/finance/commodity/${commodity}/fetch`,
        null,
        { params: { days: params.days ?? 365 } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        `Failed to trigger ${commodity} price fetch`,
        error as Error
      );
      return {
        success: false,
        data: {},
        error: (error as Error).message,
      };
    }
  },

  async getCommoditySpot(commodity: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/${commodity}/spot`
      );
      return response.data;
    } catch (error) {
      Logger.apiError(`Failed to fetch ${commodity} spot`, error as Error);
      return { success: false, data: {}, error: (error as Error).message };
    }
  },

  async getCommodityAuthority(
    commodity: string,
    params: { authorities?: string } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/${commodity}/authority`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(`Failed to fetch ${commodity} authority`, error as Error);
      return { success: false, data: {}, error: (error as Error).message };
    }
  },

  async getCommodityGeoEvents(
    params: {
      limit?: number;
      commodity?: string;
      include_cross_domain?: boolean;
      include_map_overlays?: boolean;
      include_supply_chain_geo?: boolean;
    } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/geo-events`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch commodity geo-events', error as Error);
      return {
        success: false,
        data: { events: [], by_region: {} },
        error: (error as Error).message,
      };
    }
  },

  async getCommodityContextLens(
    commodity: string,
    params: { limit?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/${commodity}/context-lens`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch commodity context lens', error as Error);
      return {
        success: false,
        data: { lens_text: '', cited_event_ids: [] },
        error: (error as Error).message,
      };
    }
  },

  async getCommodityRegulatoryEvents(
    params: { limit?: number; commodity?: string } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/commodity/regulatory-events`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to fetch commodity regulatory-events',
        error as Error
      );
      return {
        success: false,
        data: { events: [] },
        error: (error as Error).message,
      };
    }
  },

  async triggerGoldFetchHistory(
    params: { days?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/finance/gold/fetch-history`,
        null,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger gold history fetch', error as Error);
      return { success: false, error: (error as Error).message };
    }
  },

  async triggerFredFetch(
    params: { symbol: string; start_date?: string; end_date?: string },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/finance/fetch-fred`,
        null,
        { params: params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger FRED fetch', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
