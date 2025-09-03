import axios from 'axios';

// Base URL for API calls - now using unified port 8000
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    // Log API requests in development only
    if (process.env.NODE_ENV === 'development') {
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    }
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const newsSystemService = {
  // System Health
  async getHealth() {
    return api.get('/api/health/');
  },

  async getSystemMetrics() {
    return api.get('/api/health/metrics');
  },

  // Dashboard
  async getDashboardStats() {
    return api.get('/api/dashboard/');
  },

  async getIngestionStats(period = 'hour') {
    return api.get('/api/dashboard/ingestion', { params: { period } });
  },

  async getMLPipelineStats() {
    return api.get('/api/dashboard/ml-pipeline');
  },

  async getStoryEvolutionStats() {
    return api.get('/api/dashboard/story-evolution');
  },

  async getSystemAlerts() {
    return api.get('/api/dashboard/alerts');
  },

  async getRecentActivity(limit = 10) {
    return api.get('/api/dashboard/recent-activity', { params: { limit } });
  },

  // Articles
  async getArticles(filters = {}) {
    try {
      const response = await api.get('/api/articles', { params: filters });
      return response;
    } catch (error) {
      console.error('Failed to get articles:', error);
      return {
        success: false,
        articles: [],
        total: 0,
        error: error.message
      };
    }
  },

  async getArticleStats() {
    return api.get('/api/articles/stats/overview');
  },

  async getArticleById(id) {
    try {
      const response = await api.get(`/api/articles/${id}`);
      return response;
    } catch (error) {
      console.error('Failed to get article:', error);
      return {
        success: false,
        article: null,
        error: error.message
      };
    }
  },

  // Stories
  async getStories(filters = {}) {
    try {
      const response = await api.get('/api/stories', { params: filters });
      return response;
    } catch (error) {
      console.error('Failed to get stories:', error);
      return {
        success: false,
        stories: [],
        total: 0,
        error: error.message
      };
    }
  },

  async getStoryStats() {
    return api.get('/api/stories/stats/overview');
  },

  async getStoryById(id) {
    try {
      const response = await api.get(`/api/stories/${id}`);
      return response;
    } catch (error) {
      console.error('Failed to get story:', error);
      return {
        success: false,
        story: null,
        error: error.message
      };
    }
  },

  // Intelligence Endpoints
  async getIntelligenceInsights(category = 'all', limit = 10) {
    try {
      const response = await api.get('/api/intelligence/insights', { 
        params: { category, limit } 
      });
      return response;
    } catch (error) {
      console.error('Failed to get intelligence insights:', error);
      return {
        success: false,
        insights: [],
        total: 0,
        error: error.message
      };
    }
  },

  async getIntelligenceTrends() {
    try {
      const response = await api.get('/api/intelligence/trends');
      return response;
    } catch (error) {
      console.error('Failed to get intelligence trends:', error);
      return {
        success: false,
        trends: [],
        total: 0,
        error: error.message
      };
    }
  },

  async getIntelligenceAlerts() {
    try {
      const response = await api.get('/api/intelligence/alerts');
      return response;
    } catch (error) {
      console.error('Failed to get intelligence alerts:', error);
      return {
        success: false,
        alerts: [],
        total: 0,
        error: error.message
      };
    }
  },

  // RSS Management
  async getRSSFeeds() {
    try {
      const response = await api.get('/api/rss/feeds');
      return response;
    } catch (error) {
      console.error('Failed to get RSS feeds:', error);
      return {
        success: false,
        feeds: [],
        total: 0,
        error: error.message
      };
    }
  },

  async addRSSFeed(feedData) {
    try {
      const response = await api.post('/api/rss/feeds', feedData);
      return response;
    } catch (error) {
      console.error('Failed to add RSS feed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async updateRSSFeed(feedId, feedData) {
    try {
      const response = await api.put(`/api/rss/feeds/${feedId}`, feedData);
      return response;
    } catch (error) {
      console.error('Failed to update RSS feed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async deleteRSSFeed(feedId) {
    try {
      const response = await api.delete(`/api/rss/feeds/${feedId}`);
      return response;
    } catch (error) {
      console.error('Failed to delete RSS feed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async testRSSFeed(feedId) {
    try {
      const response = await api.post(`/api/rss/feeds/${feedId}/test`);
      return response;
    } catch (error) {
      console.error('Failed to test RSS feed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async refreshRSSFeed(feedId) {
    try {
      const response = await api.post(`/api/rss/feeds/${feedId}/refresh`);
      return response;
    } catch (error) {
      console.error('Failed to refresh RSS feed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async toggleRSSFeed(feedId, isActive) {
    try {
      const response = await api.put(`/api/rss/feeds/${feedId}/toggle`, { is_active: isActive });
      return response;
    } catch (error) {
      console.error('Failed to toggle RSS feed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getRSSStats() {
    try {
      const response = await api.get('/api/rss/stats');
      return response;
    } catch (error) {
      console.error('Failed to get RSS stats:', error);
      return {
        success: false,
        total_feeds: 0,
        active_feeds: 0,
        articles_today: 0,
        articles_this_hour: 0,
        avg_articles_per_feed: 0,
        success_rate: 0,
        top_feeds: [],
        error: error.message
      };
    }
  },

  // Deduplication Management
  async getDuplicates() {
    try {
      const response = await api.get('/api/deduplication/duplicates');
      return response;
    } catch (error) {
      console.error('Failed to get duplicates:', error);
      return {
        success: false,
        duplicates: [],
        total: 0,
        error: error.message
      };
    }
  },

  async detectDuplicates(settings) {
    try {
      const response = await api.post('/api/deduplication/detect', settings);
      return response;
    } catch (error) {
      console.error('Failed to detect duplicates:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async removeDuplicates(duplicateIds, autoRemove = false) {
    try {
      const response = await api.post('/api/deduplication/remove', {
        duplicate_ids: duplicateIds,
        auto_remove: autoRemove
      });
      return response;
    } catch (error) {
      console.error('Failed to remove duplicates:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async markAsNotDuplicate(duplicateId) {
    try {
      const response = await api.post(`/api/deduplication/mark-not-duplicate/${duplicateId}`);
      return response;
    } catch (error) {
      console.error('Failed to mark as not duplicate:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getDeduplicationStats() {
    try {
      const response = await api.get('/api/deduplication/stats');
      return response;
    } catch (error) {
      console.error('Failed to get deduplication stats:', error);
      return {
        success: false,
        total_duplicates: 0,
        pending_review: 0,
        high_similarity: 0,
        very_high_similarity: 0,
        avg_similarity_score: 0,
        detection_rate: 0,
        false_positive_rate: 0,
        processing_time: 0,
        error: error.message
      };
    }
  },

  async getDeduplicationSettings() {
    try {
      const response = await api.get('/api/deduplication/settings');
      return response;
    } catch (error) {
      console.error('Failed to get deduplication settings:', error);
      return {
        success: false,
        settings: {},
        error: error.message
      };
    }
  },

  async updateDeduplicationSettings(settings) {
    try {
      const response = await api.put('/api/deduplication/settings', settings);
      return response;
    } catch (error) {
      console.error('Failed to update deduplication settings:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  // ML Pipeline
  async getMLPipelineStatus() {
    return api.get('/api/ml/status');
  },

  async triggerMLProcessing() {
    return api.post('/api/ml/process');
  },

  async getMLModels() {
    return api.get('/api/ml/models');
  },

  // Monitoring
  async getPrometheusMetrics() {
    return api.get('/api/monitoring/metrics');
  },

  async getSystemMetrics() {
    return api.get('/api/monitoring/system');
  },

  async getMonitoringHealth() {
    return api.get('/api/monitoring/health');
  },

  // System Status
  async getSystemStatus() {
    try {
      const response = await api.get('/api/system/status');
      return response;
    } catch (error) {
      console.error('Failed to get system status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  // Dashboard Data - Use the real endpoint that exists
  async getDashboardData() {
    try {
      const response = await api.get('/api/dashboard/real');
      return response;
    } catch (error) {
      console.error('Failed to get dashboard data:', error);
      return {
        success: false,
        articleCount: 0,
        clusterCount: 0,
        entityCount: 0,
        sourceCount: 0,
        recentArticles: [],
        topSources: [],
        topEntities: [],
        feedHealth: [],
        error: error.message
      };
    }
  },

  // Articles - Use the correct endpoint
  async getArticles(filters = {}) {
    try {
      const response = await api.get('/api/articles', { params: filters });
      return response;
    } catch (error) {
      console.error('Failed to get articles:', error);
      return {
        success: false,
        articles: [],
        total: 0,
        error: error.message
      };
    }
  },

  // Clusters - Now using real API endpoint
  async getClusters() {
    try {
      const response = await api.get('/api/clusters');
      return {
        success: true,
        list: response.data.clusters || [],
        total: response.data.total || 0
      };
    } catch (error) {
      console.error('Failed to get clusters:', error);
      return {
        success: false,
        list: [],
        total: 0,
        error: error.message
      };
    }
  },

  // Entities - Now using real API endpoint
  async getEntities() {
    try {
      const response = await api.get('/api/entities');
      return {
        success: true,
        data: response.data.entities || [],
        total: response.data.total || 0
      };
    } catch (error) {
      console.error('Failed to get entities:', error);
      return {
        success: false,
        data: [],
        total: 0,
        error: error.message
      };
    }
  },

  // Sources - Now using real API endpoint
  async getSources() {
    try {
      const response = await api.get('/api/sources');
      return {
        success: true,
        data: response.data.sources || [],
        total: response.data.total || 0
      };
    } catch (error) {
      console.error('Failed to get sources:', error);
      return {
        success: false,
        data: [],
        total: 0,
        error: error.message
      };
    }
  },

  // Search - Now using real API endpoint
  async search(query, filters = {}) {
    try {
      const searchRequest = {
        query: query,
        search_type: 'full_text',
        filters: filters,
        page: 1,
        per_page: 20,
        sort_by: 'relevance',
        sort_order: 'desc'
      };
      
      const response = await api.post('/api/search', searchRequest);
      return response;
    } catch (error) {
      console.error('Search failed:', error);
      return {
        results: [],
        total: 0,
        page: 1,
        per_page: 20,
        search_time: 0,
        suggestions: []
      };
    }
  },

  // RAG System APIs
  async getRAGDossiers(filters = {}) {
    try {
      const response = await api.get('/api/rag/dossiers', { params: filters });
      return response;
    } catch (error) {
      console.error('Failed to get RAG dossiers:', error);
      return {
        success: false,
        dossiers: [],
        total: 0,
        page: 1,
        per_page: 20,
        error: error.message
      };
    }
  },

  async getRAGDossier(dossierId) {
    try {
      const response = await api.get(`/api/rag/dossiers/${dossierId}`);
      return response;
    } catch (error) {
      console.error('Failed to get RAG dossier:', error);
      return {
        success: false,
        dossier: null,
        error: error.message
      };
    }
  },

  async createRAGDossier(articleId) {
    try {
      const response = await api.post('/api/rag/dossiers', { article_id: articleId });
      return response;
    } catch (error) {
      console.error('Failed to create RAG dossier:', error);
      return {
        success: false,
        dossier: null,
        error: error.message
      };
    }
  },

  async getRAGStats() {
    try {
      const response = await api.get('/api/rag/stats');
      return response;
    } catch (error) {
      console.error('Failed to get RAG stats:', error);
      return {
        success: false,
        total_dossiers: 0,
        active_dossiers: 0,
        completed_dossiers: 0,
        plateau_dossiers: 0,
        avg_iterations_per_dossier: 0,
        avg_processing_time: 0,
        success_rate: 0,
        recent_dossiers: [],
        error: error.message
      };
    }
  },

  // ML Management APIs
  async getMLStatus() {
    try {
      const response = await api.get('/api/ml-management/status');
      return response;
    } catch (error) {
      console.error('Failed to get ML status:', error);
      return {
        success: false,
        status: 'offline',
        queue_size: 0,
        processing_rate: 0,
        models_status: {},
        last_processed: null,
        total_processed: 0,
        success_rate: 0,
        error: error.message
      };
    }
  },

  async triggerMLProcessing(articleIds, jobType = 'full_processing') {
    try {
      const response = await api.post('/api/ml-management/process', {
        article_ids: articleIds,
        job_type: jobType,
        priority: 1
      });
      return response;
    } catch (error) {
      console.error('Failed to trigger ML processing:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getMLModels() {
    try {
      const response = await api.get('/api/ml-management/models');
      return response;
    } catch (error) {
      console.error('Failed to get ML models:', error);
      return {
        success: false,
        models: {},
        error: error.message
      };
    }
  },

  async getMLPerformance() {
    try {
      const response = await api.get('/api/ml-management/performance');
      return response;
    } catch (error) {
      console.error('Failed to get ML performance:', error);
      return {
        success: false,
        total_processed: 0,
        processing_rate: 0,
        success_rate: 0,
        avg_processing_time: 0,
        queue_size: 0,
        model_performance: {},
        recent_jobs: [],
        error: error.message
      };
    }
  },

  // Search Enhancement APIs
  async getSearchSuggestions(query, limit = 10) {
    try {
      const response = await api.get('/api/search/suggestions', { 
        params: { query, limit } 
      });
      return response;
    } catch (error) {
      console.error('Failed to get search suggestions:', error);
      return {
        success: false,
        suggestions: [],
        error: error.message
      };
    }
  },

  async getTrendingSearches(limit = 10, period = '24h') {
    try {
      const response = await api.get('/api/search/trending', { 
        params: { limit, period } 
      });
      return response;
    } catch (error) {
      console.error('Failed to get trending searches:', error);
      return {
        success: false,
        trending: [],
        period,
        error: error.message
      };
    }
  },

  async getSearchStats() {
    try {
      const response = await api.get('/api/search/stats');
      return response;
    } catch (error) {
      console.error('Failed to get search stats:', error);
      return {
        success: false,
        total_searches: 0,
        popular_queries: [],
        search_trends: [],
        avg_search_time: 0,
        no_results_queries: [],
        error: error.message
      };
    }
  },

  // Automation APIs
  async getLivingNarratorStatus() {
    try {
      const response = await api.get('/api/automation/living-narrator/status');
      return response;
    } catch (error) {
      console.error('Failed to get living narrator status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  async triggerStoryConsolidation() {
    try {
      const response = await api.post('/api/automation/living-narrator/consolidate');
      return response;
    } catch (error) {
      console.error('Failed to trigger story consolidation:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async generateDailyDigest() {
    try {
      const response = await api.post('/api/automation/living-narrator/digest');
      return response;
    } catch (error) {
      console.error('Failed to generate daily digest:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async triggerDatabaseCleanup() {
    try {
      const response = await api.post('/api/automation/living-narrator/cleanup');
      return response;
    } catch (error) {
      console.error('Failed to trigger database cleanup:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getPreprocessingStatus() {
    try {
      const response = await api.get('/api/automation/preprocessing/status');
      return response;
    } catch (error) {
      console.error('Failed to get preprocessing status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  async startPipeline() {
    try {
      const response = await api.post('/api/automation/pipeline/start');
      return response;
    } catch (error) {
      console.error('Failed to start pipeline:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async stopPipeline() {
    try {
      const response = await api.post('/api/automation/pipeline/stop');
      return response;
    } catch (error) {
      console.error('Failed to stop pipeline:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getPipelineStatus() {
    try {
      const response = await api.get('/api/automation/pipeline/status');
      return response;
    } catch (error) {
      console.error('Failed to get pipeline status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  // Pipeline
  async runPipeline() {
    try {
      const response = await api.post('/api/pipeline/run');
      return response;
    } catch (error) {
      console.error('Pipeline execution failed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  // Health check
  async healthCheck() {
    try {
      const response = await api.get('/health');
      return response;
    } catch (error) {
      console.error('Health check failed:', error);
      return {
        success: false,
        status: 'unhealthy',
        error: error.message
      };
    }
  },

  // ML Processing Functions
  async processAllArticles() {
    try {
      const response = await api.post('/api/ml/process-all');
      return response;
    } catch (error) {
      console.error('Failed to process all articles:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getMLProcessingStatus() {
    try {
      const response = await api.get('/api/ml/processing-status');
      return response;
    } catch (error) {
      console.error('Failed to get ML processing status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  async getAllMLProcessingStatus() {
    try {
      const response = await api.get('/api/ml/processing-status');
      return response;
    } catch (error) {
      console.error('Failed to get ML processing status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  async getMLQueueStatus() {
    try {
      const response = await api.get('/api/ml/queue-status');
      return response;
    } catch (error) {
      console.error('Failed to get ML queue status:', error);
      return {
        success: false,
        queue_size: 0,
        error: error.message
      };
    }
  },

  async getMLTimingStats() {
    try {
      const response = await api.get('/api/ml/timing-stats');
      return response;
    } catch (error) {
      console.error('Failed to get ML timing stats:', error);
      return {
        success: false,
        avg_processing_time: 0,
        error: error.message
      };
    }
  },

  // RAG Statistics
  async getRAGStatistics() {
    try {
      const response = await api.get('/api/rag/statistics');
      return response;
    } catch (error) {
      console.error('Failed to get RAG statistics:', error);
      return {
        success: false,
        statistics: {},
        error: error.message
      };
    }
  },

  async getExternalServicesStatus() {
    try {
      const response = await api.get('/api/rag/external-services-status');
      return response;
    } catch (error) {
      console.error('Failed to get external services status:', error);
      return {
        success: false,
        services: {},
        error: error.message
      };
    }
  },

  // RSS Collection
  async collectRSSFeeds() {
    try {
      const response = await api.post('/api/rss/collect-now');
      return response;
    } catch (error) {
      console.error('Failed to collect RSS feeds:', error);
      return {
        success: false,
        error: error.message
      };
    }
  },

  async getAllRSSCollectionProgress() {
    try {
      const response = await api.get('/api/rss/progress');
      return response;
    } catch (error) {
      console.error('Failed to get RSS collection progress:', error);
      return {
        success: false,
        progress: [],
        error: error.message
      };
    }
  },

  // Additional ML Functions for consistency
  async getMLStatus() {
    try {
      const response = await api.get('/api/ml/status');
      return response;
    } catch (error) {
      console.error('Failed to get ML status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  // Additional automation functions
  async getAutomationStatus() {
    try {
      const response = await api.get('/api/automation/pipeline/status');
      return response;
    } catch (error) {
      console.error('Failed to get automation status:', error);
      return {
        success: false,
        status: 'unknown',
        error: error.message
      };
    }
  },

  // Daily digest functions
  async getTodayArticles() {
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await api.get('/api/articles', { 
        params: { 
          date_from: today,
          date_to: today,
          limit: 100
        } 
      });
      return response;
    } catch (error) {
      console.error('Failed to get today articles:', error);
      return {
        success: false,
        articles: [],
        error: error.message
      };
    }
  },

  async getDailyDigests() {
    try {
      const response = await api.get('/api/automation/daily-digests');
      return response;
    } catch (error) {
      console.error('Failed to get daily digests:', error);
      return {
        success: false,
        digests: [],
        error: error.message
      };
    }
  },

  async getMasterArticles() {
    try {
      const response = await api.get('/api/articles/master');
      return response;
    } catch (error) {
      console.error('Failed to get master articles:', error);
      return {
        success: false,
        data: [],
        error: error.message
      };
    }
  },

  async getStoryThreads() {
    try {
      const response = await api.get('/api/stories/threads');
      return response;
    } catch (error) {
      console.error('Failed to get story threads:', error);
      return {
        success: false,
        data: [],
        error: error.message
      };
    }
  }
};

export default newsSystemService;
