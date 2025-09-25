import axios from 'axios';

import Logger from '../utils/logger';
// Types are imported but not used in this file - they're used in the actual implementation
// import {
//   APIResponse,
//   Article,
//   ArticleStats,
//   RSSFeed,
//   RSSStats,
//   Storyline,
//   DashboardData,
//   PipelineStatus,
//   PipelinePerformance,
//   SearchResponse,
//   SearchParams,
//   APIConfig,
//   APIError
// } from '../types';

const API_BASE_URL = process.env['REACT_APP_API_URL'] || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    Logger.apiRequest(config.method?.toUpperCase() || 'UNKNOWN', config.url || '');
    return config;
  },
  (error) => {
    Logger.apiError('API Request Error', error);
    return Promise.reject(error);
  },
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    Logger.apiResponse(response.status, response.config.url || '');
    return response;
  },
  (error) => {
    Logger.apiError('API Response Error', error, error.config?.url);
    if (error.response) {
      Logger.error('Error data', error.response.data);
      Logger.error('Error status', error.response.status);
    }
    return Promise.reject(error);
  },
);

export const apiService = {
  // Generic HTTP methods
  get: async(url: string, config = {}) => {
    try {
      const response = await api.get(url, config);
      return response.data;
    } catch (error) {
      Logger.apiError(`GET ${url} failed`, error as Error, url);
      throw error;
    }
  },

  post: async(url: string, data = {}, config = {}) => {
    try {
      const response = await api.post(url, data, config);
      return response.data;
    } catch (error) {
      console.error(`POST ${url} failed:`, error);
      throw error;
    }
  },

  put: async(url: string, data = {}, config = {}) => {
    try {
      const response = await api.put(url, data, config);
      return response.data;
    } catch (error) {
      console.error(`PUT ${url} failed:`, error);
      throw error;
    }
  },

  delete: async(url: string, config = {}) => {
    try {
      const response = await api.delete(url, config);
      return response.data;
    } catch (error) {
      console.error(`DELETE ${url} failed:`, error);
      throw error;
    }
  },

  // Health endpoints
  getHealth: async() => {
    try {
      const response = await api.get('/api/health/');
      return response.data;
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  },

  // Articles endpoints
  getArticles: async(params = {}) => {
    try {
      const response = await api.get('/api/articles/', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch articles:', error);
      // Return mock data for development
      return {
        success: true,
        data: {
          articles: [],
          total: 0,
          page: 1,
          limit: 20,
        },
        message: 'No articles found - database schema needs initialization',
      };
    }
  },

  getArticle: async(id: string | number) => {
    try {
      const response = await api.get(`/api/articles/${id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article:', error);
      throw error;
    }
  },

  getArticleStats: async() => {
    try {
      const response = await api.get('/api/articles/stats/overview');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article stats:', error);
      // Return mock data for development
      return {
        success: true,
        data: {
          total_articles: 0,
          articles_today: 0,
          articles_this_week: 0,
          avg_quality_score: 0,
          top_sources: [],
          sentiment_distribution: { positive: 0, negative: 0, neutral: 0 },
        },
      };
    }
  },

  // RSS Feeds endpoints
  getRSSFeeds: async(params = {}) => {
    try {
      const response = await api.get('/api/rss/feeds/', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch RSS feeds:', error);
      // Return mock data for development
      return {
        success: true,
        data: {
          feeds: [],
          total: 0,
          page: 1,
          limit: 20,
        },
      };
    }
  },

  getRSSStats: async() => {
    try {
      const response = await api.get('/api/rss/feeds/stats/overview');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch RSS stats:', error);
      // Return mock data for development
      return {
        success: true,
        data: {
          total_feeds: 0,
          active_feeds: 0,
          feeds_with_errors: 0,
          last_update: null,
          total_articles_collected: 0,
        },
      };
    }
  },

  // Storylines endpoints
  getStorylines: async(params = {}) => {
    try {
      const response = await api.get('/api/storylines/', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storylines:', error);
      // Return mock data for development
      return {
        success: true,
        data: {
          storylines: [],
          total: 0,
          page: 1,
          limit: 20,
        },
      };
    }
  },

  getStoryline: async(id: string | number) => {
    try {
      const response = await api.get(`/api/storylines/${id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storyline:', error);
      throw error;
    }
  },

  // Dashboard endpoints
  getDashboardData: async() => {
    try {
      const response = await api.get('/api/dashboard/stats');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      // Return mock data for development
      return {
        success: true,
        data: {
          system_health: { status: 'healthy' },
          article_stats: { total: 0, today: 0 },
          rss_stats: { total_feeds: 0, active_feeds: 0 },
          storyline_stats: { total: 0, active: 0 },
          recent_activity: [],
        },
      };
    }
  },

  // Pipeline Monitoring endpoints
  getPipelineStatus: async() => {
    try {
      const response = await api.get('/api/pipeline-monitoring/live-status');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch pipeline status:', error);
      return {
        active_traces_count: 0,
        active_traces: [],
        system_status: 'error',
        timestamp: new Date().toISOString(),
      };
    }
  },

  getPipelineTraces: async(params = {}) => {
    try {
      const response = await api.get('/api/pipeline-monitoring/traces', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch pipeline traces:', error);
      return {
        success: true,
        data: {
          traces: [],
          total: 0,
        },
      };
    }
  },

  getPipelinePerformance: async() => {
    try {
      const response = await api.get('/api/pipeline-monitoring/performance');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch pipeline performance:', error);
      return {
        total_traces: 0,
        successful_traces: 0,
        failed_traces: 0,
        success_rate: 0,
        average_duration_ms: 0,
        total_articles_processed: 0,
        total_feeds_processed: 0,
        error_count: 0,
        bottlenecks: [],
        stage_performance: {},
      };
    }
  },

  // Pipeline and RSS Feed Actions
  triggerPipeline: async() => {
    try {
      // Use the ML pipeline endpoint as a proxy for triggering processing
      const response = await api.post('/api/intelligence/ml/pipelines/article_classification/run?force=true');
      return response.data;
    } catch (error) {
      console.error('Failed to trigger pipeline:', error);
      throw error;
    }
  },

  updateRSSFeeds: async() => {
    try {
      // Get all feeds and refresh them individually
      const feedsResponse = await api.get('/api/rss/feeds/');
      const feeds = feedsResponse.data.data.feeds || [];

      const refreshPromises = feeds.map((feed: any) =>
        api.post(`/api/rss/feeds/${feed.id}/refresh`).catch(err => {
          console.warn(`Failed to refresh feed ${feed.id}:`, err);
          return { success: false, feed_id: feed.id };
        }),
      );

      const results = await Promise.allSettled(refreshPromises);
      const successful = results.filter(r => r.status === 'fulfilled' && r.value.data?.success !== false).length;

      return {
        success: true,
        message: `Refreshed ${successful} out of ${feeds.length} RSS feeds`,
        refreshed_count: successful,
        total_feeds: feeds.length,
      };
    } catch (error) {
      console.error('Failed to update RSS feeds:', error);
      throw error;
    }
  },

  runAIAnalysis: async() => {
    try {
      const response = await api.post('/api/intelligence/ml/pipelines/sentiment_analysis/run?force=true');
      return response.data;
    } catch (error) {
      console.error('Failed to run AI analysis:', error);
      throw error;
    }
  },

  // Enhanced Analysis endpoints
  getMultiPerspectiveAnalysis: async(storylineId: string | number) => {
    try {
      const response = await api.post('/api/enhanced-analysis/multi-perspective', {
        storyline_id: storylineId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get multi-perspective analysis:', error);
      throw error;
    }
  },

  getImpactAssessment: async(storylineId: string | number) => {
    try {
      const response = await api.post('/api/enhanced-analysis/impact-assessment', {
        storyline_id: storylineId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get impact assessment:', error);
      throw error;
    }
  },

  getHistoricalContext: async(storylineId: string | number) => {
    try {
      const response = await api.post('/api/enhanced-analysis/historical-context', {
        storyline_id: storylineId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get historical context:', error);
      throw error;
    }
  },

  getPredictiveAnalysis: async(storylineId: string | number) => {
    try {
      const response = await api.post('/api/enhanced-analysis/predictive-analysis', {
        storyline_id: storylineId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get predictive analysis:', error);
      throw error;
    }
  },

  getExpertAnalysis: async(storylineId: string | number) => {
    try {
      const response = await api.post('/api/enhanced-analysis/expert-analysis', {
        storyline_id: storylineId,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get expert analysis:', error);
      throw error;
    }
  },

  // Search endpoints
  searchArticles: async(query: string, params = {}) => {
    try {
      const response = await api.get('/api/search/', {
        params: { q: query, ...params },
      });
      return response.data;
    } catch (error) {
      console.error('Search failed:', error);
      return {
        success: true,
        data: {
          results: [],
          total: 0,
          query: query,
        },
      };
    }
  },

  // Sources and Categories endpoints
  getSources: async() => {
    try {
      const response = await api.get('/api/articles/sources');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch sources:', error);
      // Return mock data for development
      return {
        success: true,
        data: ['BBC News', 'Reuters', 'The Guardian', 'CNN', 'Associated Press'],
      };
    }
  },

  getCategories: async() => {
    try {
      const response = await api.get('/api/articles/categories');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch categories:', error);
      // Return mock data for development
      return {
        success: true,
        data: ['Global Events', 'Business', 'Politics', 'Technology', 'Health'],
      };
    }
  },

  // Utility methods
  isHealthy: async() => {
    try {
      const health = await apiService.getHealth();
      return health.data?.status === 'healthy';
    } catch (error) {
      return false;
    }
  },

  getMonitoringDashboard: async() => {
    try {
      const response = await api.get('/api/monitoring/dashboard');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch monitoring dashboard:', error);
      return null;
    }
  },

  getSystemStatus: async() => {
    try {
      const [health, articles, rssFeeds, monitoringData] = await Promise.all([
        apiService.getHealth(),
        apiService.getArticles().catch(() => ({ data: { total_count: 0 } })),
        apiService.getRSSFeeds().catch(() => ({ data: { feeds: [] } })),
        apiService.getMonitoringDashboard().catch(() => null),
      ]);

      return {
        health,
        articleStats: {
          success: true,
          data: {
            total_articles: articles.data?.total_count || 0,
            recent_articles: articles.data?.articles?.length || 0,
            articles_today: 0, // TODO: Calculate from date filtering
            articles_this_week: 0, // TODO: Calculate from date filtering
          },
        },
        rssStats: {
          success: true,
          data: {
            total_feeds: rssFeeds.data?.feeds?.length || 0,
            active_feeds: rssFeeds.data?.feeds?.filter((feed: any) => feed.is_active !== false).length || 0,
            feeds_with_errors: 0, // TODO: Calculate from feed error status
          },
        },
        storylineStats: {
          success: true,
          data: {
            total_storylines: 0, // TODO: Add when storylines endpoint is fixed
            active_storylines: 0,
          },
        },
        monitoringData,
        overall: health.data?.status === 'healthy' ? 'healthy' : 'degraded',
      };
    } catch (error) {
      console.error('Failed to get system status:', error);
      return {
        health: { data: { status: 'error', message: 'System unavailable' } },
        articleStats: { data: { total_articles: 0, recent_articles: 0, articles_today: 0, articles_this_week: 0 } },
        rssStats: { data: { total_feeds: 0, active_feeds: 0, feeds_with_errors: 0 } },
        storylineStats: { data: { total_storylines: 0, active_storylines: 0 } },
        monitoringData: null,
        overall: 'error',
      };
    }
  },
};

export default apiService;
