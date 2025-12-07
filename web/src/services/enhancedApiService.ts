/**
 * News Intelligence System v3.3.0 - Enhanced API Service
 * Integrates with comprehensive logging, monitoring, and documentation systems
 */

import axios, { AxiosResponse, AxiosError } from 'axios';
import Logger from '../utils/logger';

// Enhanced types for Phase 2 integration
export interface SystemHealth {
  status: string;
  timestamp: string;
  services: {
    database: string;
    redis: string;
    system: string;
  };
  details: {
    database: { status: string };
    redis: { status: string };
    system: { status: string };
  };
}

export interface LogStats {
  period_days: number;
  total_entries: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  debug_count: number;
  time_range: {
    start: string;
    end: string;
  };
  top_loggers: Array<{ logger: string; count: number }>;
  top_errors: Array<{ error: string; count: number }>;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  module?: string;
  function?: string;
  line?: number;
  exception?: any;
  extra_data?: any;
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  load_average: number[];
  uptime: string;
  last_health_check: string;
}

export interface DatabaseMetrics {
  total_articles: number;
  recent_articles: number;
  total_rss_feeds: number;
  total_storylines: number;
  database_size: string;
  connection_status: string;
}

export interface DeduplicationStats {
  total_articles: number;
  articles_with_content_hash: number;
  total_clusters: number;
  total_duplicate_pairs: number;
  system_status: string;
}

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  message: string;
  error?: string;
  timestamp: string;
  meta?: any;
}

const API_BASE_URL =
  process.env['REACT_APP_API_URL'] || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  config => {
    Logger.info(`API Request: ${config.method?.toUpperCase()} ${config.url}`, {
      method: config.method,
      url: config.url,
      params: config.params,
      timestamp: new Date().toISOString(),
    });
    return config;
  },
  error => {
    Logger.error('API Request Error', error);
    return Promise.reject(error);
  },
);

// Response interceptor for logging and error handling
api.interceptors.response.use(
  (response: AxiosResponse) => {
    Logger.info(`API Response: ${response.status} ${response.config.url}`, {
      status: response.status,
      url: response.config.url,
      data: response.data,
      timestamp: new Date().toISOString(),
    });
    return response;
  },
  (error: AxiosError) => {
    const errorInfo = {
      status: error.response?.status,
      url: error.config?.url,
      message: error.message,
      data: error.response?.data,
      timestamp: new Date().toISOString(),
    };

    Logger.error('API Response Error', errorInfo);
    return Promise.reject(error);
  },
);

export const enhancedApiService = {
  // System Health and Monitoring
  getSystemHealth: async(): Promise<SystemHealth> => {
    try {
      const response = await api.get('/api/health/');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get system health', error);
      throw error;
    }
  },

  getSystemMetrics: async(): Promise<SystemMetrics> => {
    try {
      const response = await api.get('/api/monitoring/metrics');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get system metrics', error);
      throw error;
    }
  },

  getDatabaseMetrics: async(): Promise<DatabaseMetrics> => {
    try {
      const response = await api.get('/api/monitoring/dashboard');
      return response.data.data.database_metrics;
    } catch (error) {
      Logger.error('Failed to get database metrics', error);
      throw error;
    }
  },

  // Log Management Integration
  getLogStatistics: async(days: number = 7): Promise<LogStats> => {
    try {
      const response = await api.get(`/api/logs/statistics?days=${days}`);
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get log statistics', error);
      throw error;
    }
  },

  getRealtimeLogs: async(limit: number = 50): Promise<LogEntry[]> => {
    try {
      const response = await api.get(`/api/logs/realtime?limit=${limit}`);
      return response.data.data.entries;
    } catch (error) {
      Logger.error('Failed to get realtime logs', error);
      throw error;
    }
  },

  getLogEntries: async(
    params: {
      start_time?: string;
      end_time?: string;
      level?: string;
      logger_name?: string;
      limit?: number;
    } = {},
  ): Promise<LogEntry[]> => {
    try {
      const response = await api.get('/api/logs/entries', { params });
      return response.data.data.entries;
    } catch (error) {
      Logger.error('Failed to get log entries', error);
      throw error;
    }
  },

  getSystemHealthFromLogs: async(): Promise<{
    error_rate_last_hour: number;
    total_errors_last_24h: number;
    hourly_error_trend: number[];
    system_health_score: number;
    timestamp: string;
  }> => {
    try {
      const response = await api.get('/api/logs/health');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get system health from logs', error);
      throw error;
    }
  },

  // Deduplication System Integration
  getDeduplicationStats: async(): Promise<DeduplicationStats> => {
    try {
      const response = await api.get('/api/deduplication/statistics');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get deduplication stats', error);
      throw error;
    }
  },

  testDeduplicationSystem: async(): Promise<APIResponse> => {
    try {
      const response = await api.get('/api/deduplication/test');
      return response.data;
    } catch (error) {
      Logger.error('Failed to test deduplication system', error);
      throw error;
    }
  },

  // API Documentation Integration
  getAPIOverview: async(): Promise<any> => {
    try {
      const response = await api.get('/api/docs/overview');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get API overview', error);
      throw error;
    }
  },

  getAPIEndpoints: async(): Promise<any> => {
    try {
      const response = await api.get('/api/docs/endpoints');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get API endpoints', error);
      throw error;
    }
  },

  getAPISchemas: async(): Promise<any> => {
    try {
      const response = await api.get('/api/docs/schemas');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get API schemas', error);
      throw error;
    }
  },

  getAPIExamples: async(): Promise<any> => {
    try {
      const response = await api.get('/api/docs/examples');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get API examples', error);
      throw error;
    }
  },

  getAPIStatus: async(): Promise<any> => {
    try {
      const response = await api.get('/api/docs/status');
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get API status', error);
      throw error;
    }
  },

  // Enhanced Article Management
  getArticles: async(
    params: {
      page?: number;
      limit?: number;
      status?: string;
      source?: string;
      category?: string;
      date_from?: string;
      date_to?: string;
      quality_min?: number;
      quality_max?: number;
    } = {},
  ): Promise<{
    items: any[];
    total: number;
    page: number;
    limit: number;
    pages: number;
  }> => {
    try {
      const response = await api.get('/api/articles', { params });
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get articles', error);
      throw error;
    }
  },

  getArticle: async(id: number): Promise<any> => {
    try {
      const response = await api.get(`/api/articles/${id}`);
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get article', error);
      throw error;
    }
  },

  // Enhanced RSS Feed Management
  getRSSFeeds: async(active_only: boolean = false): Promise<any[]> => {
    try {
      const response = await api.get('/api/rss/feeds', {
        params: { active_only },
      });
      return response.data.data.feeds;
    } catch (error) {
      Logger.error('Failed to get RSS feeds', error);
      throw error;
    }
  },

  addRSSFeed: async(feedData: {
    name: string;
    url: string;
    description?: string;
    category?: string;
    subcategory?: string;
    country?: string;
    tier?: number;
    priority?: number;
    max_articles?: number;
    update_frequency?: number;
  }): Promise<any> => {
    try {
      const response = await api.post('/api/rss/feeds', feedData);
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to add RSS feed', error);
      throw error;
    }
  },

  // Enhanced Storyline Management
  getStorylines: async(
    params: {
      status?: string;
      category?: string;
      min_articles?: number;
      max_articles?: number;
      ml_processed?: boolean;
    } = {},
  ): Promise<any[]> => {
    try {
      const response = await api.get('/api/storylines', { params });
      return response.data.data.storylines;
    } catch (error) {
      Logger.error('Failed to get storylines', error);
      throw error;
    }
  },

  getStoryline: async(id: string): Promise<any> => {
    try {
      const response = await api.get(`/api/storylines/${id}/report`);
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to get storyline', error);
      throw error;
    }
  },

  createStoryline: async(storylineData: {
    title: string;
    description?: string;
    category?: string;
    tags?: string[];
    priority?: number;
  }): Promise<any> => {
    try {
      const response = await api.post('/api/storylines', storylineData);
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to create storyline', error);
      throw error;
    }
  },

  addArticleToStoryline: async(
    storylineId: string,
    articleId: string,
    relevanceScore?: number,
    importanceScore?: number,
  ): Promise<any> => {
    try {
      const response = await api.post(
        `/api/storylines/${storylineId}/add-article`,
        {
          article_id: articleId,
          relevance_score: relevanceScore,
          importance_score: importanceScore,
        },
      );
      return response.data.data;
    } catch (error) {
      Logger.error('Failed to add article to storyline', error);
      throw error;
    }
  },

  // Pipeline Operations
  processRSSFeeds: async(): Promise<any> => {
    try {
      const response = await api.post(
        '/api/article-processing/process-rss-feeds',
      );
      return response.data;
    } catch (error) {
      Logger.error('Failed to process RSS feeds', error);
      throw error;
    }
  },

  runAIAnalysis: async(): Promise<any> => {
    try {
      const response = await api.post(
        '/api/intelligence/ml/pipelines/sentiment_analysis/run?force=true',
      );
      return response.data;
    } catch (error) {
      Logger.error('Failed to run AI analysis', error);
      throw error;
    }
  },

  // Utility functions
  exportLogs: async(
    params: {
      start_time?: string;
      end_time?: string;
      format?: 'json' | 'csv';
    } = {},
  ): Promise<Blob> => {
    try {
      const response = await api.post('/api/logs/export', null, {
        params,
        responseType: 'blob',
      });
      return response.data;
    } catch (error) {
      Logger.error('Failed to export logs', error);
      throw error;
    }
  },

  cleanupLogs: async(): Promise<any> => {
    try {
      const response = await api.post('/api/logs/cleanup');
      return response.data;
    } catch (error) {
      Logger.error('Failed to cleanup logs', error);
      throw error;
    }
  },
};

export default enhancedApiService;
