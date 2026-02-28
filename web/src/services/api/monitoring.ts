/**
 * System monitoring API — health, pipeline, deduplication, intelligence, finance.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

export const monitoringApi = {
  async getHealth() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/health');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch health', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMonitoringDashboard() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch monitoring dashboard', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getPipelineStatus() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/pipeline_status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch pipeline status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerPipeline() {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/pipeline/trigger');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger pipeline', error as Error);
      return { success: false, error: (error as any).message || 'Pipeline trigger API not yet implemented' };
    }
  },

  async getSystemHealth() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/health');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get system health', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getSystemMetrics() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/metrics');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get system metrics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDatabaseMetrics() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/dashboard');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get database metrics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getLogStatistics(days: number = 7) {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/logs/stats', {
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
      const response = await getApi().get('/api/v4/system_monitoring/logs/realtime', {
        params: { limit },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get realtime logs', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getAPIStatus() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get API status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDuplicateStats() {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get duplicate stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async detectDuplicates(params: {
    similarity_threshold?: number;
    check_url?: boolean;
    check_content?: boolean;
  } = {}) {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/detect', {
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
      const response = await getApi().get('/api/v4/articles/duplicates/url');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get URL duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getContentDuplicates() {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/content');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get content duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getSimilarArticles(articleId: number, threshold: number = 0.8) {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/similar', {
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
        '/api/v4/articles/duplicates/auto_merge',
        { dry_run: dryRun },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to auto-merge duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async preventDuplicates() {
    try {
      const response = await getApi().post('/api/v4/articles/duplicates/prevent');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to prevent duplicates', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async analyzeSimilarity(articleId1: number, articleId2: number) {
    try {
      const response = await getApi().post(
        '/api/v4/articles/duplicates/analyze_similarity',
        { article_id_1: articleId1, article_id_2: articleId2 },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to analyze similarity', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDeduplicationStats() {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get deduplication stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMLQueueStatus() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/ml/queue_status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get ML queue status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getAllMLProcessingStatus() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/ml/processing_status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get ML processing status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMLTimingStats() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/ml/timing_stats');
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
    model?: string,
  ) {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/ml/queue', {
        article_id: articleId,
        operation,
        priority,
        model,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to queue article for ML processing', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getFeedbackLoopStatus() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/feedback_loop/status');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get feedback loop status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async startFeedbackLoop() {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/feedback_loop/start');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to start feedback loop', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async stopFeedbackLoop() {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/feedback_loop/stop');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to stop feedback loop', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async runAIAnalysis() {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/ai-analysis/run');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to run AI analysis', error as Error);
      return { success: false, error: (error as any).message || 'AI analysis API not yet implemented' };
    }
  },

  async getMarketTrends(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/finance/market-trends`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch market trends', error as Error);
      return { success: false, error: (error as any).message || 'Market trends API not yet implemented', data: null };
    }
  },

  async getMarketPatterns(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/finance/market-patterns`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch market patterns', error as Error);
      return { success: false, error: (error as any).message || 'Market patterns API not yet implemented', data: null };
    }
  },

  async getCorporateAnnouncements(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/finance/corporate-announcements`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch corporate announcements', error as Error);
      return { success: false, error: (error as any).message || 'Corporate announcements API not yet implemented', data: null };
    }
  },

  // Finance infrastructure data (FRED, market store)
  async getFinanceDataSources(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/finance/data-sources`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch finance data sources', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getFinanceMarketData(params: { source?: string; symbol?: string; start_date?: string; end_date?: string } = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/finance/market-data`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch finance market data', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getGoldData(params: { source?: string; start_date?: string; end_date?: string; fetch?: boolean } = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/finance/gold`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch gold data', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerGoldFetch(params: { start_date?: string; end_date?: string } = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/finance/gold/fetch`,
        null,
        { params: params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger gold fetch', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerFredFetch(params: { symbol: string; start_date?: string; end_date?: string }, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/finance/fetch-fred`,
        null,
        { params: params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger FRED fetch', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
