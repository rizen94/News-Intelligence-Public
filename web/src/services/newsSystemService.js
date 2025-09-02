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
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('API Response Error:', error);
    if (error.response) {
      // Server responded with error status
      throw new Error(`API Error: ${error.response.status} - ${error.response.data?.message || error.response.statusText}`);
    } else if (error.request) {
      // Request made but no response
      throw new Error('No response from server. Please check your connection.');
    } else {
      // Something else happened
      throw new Error(`Request failed: ${error.message}`);
    }
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
    return api.get(`/api/dashboard/ingestion?period=${period}`);
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
    return api.get(`/api/dashboard/recent-activity?limit=${limit}`);
  },

  // Articles
  async getArticles(params = {}) {
    const queryParams = new URLSearchParams();
    Object.keys(params).forEach(key => {
      if (params[key] !== undefined && params[key] !== null) {
        queryParams.append(key, params[key]);
      }
    });
    return api.get(`/api/articles/?${queryParams.toString()}`);
  },

  async getArticle(id) {
    return api.get(`/api/articles/${id}`);
  },

  async createArticle(article) {
    return api.post('/api/articles/', article);
  },

  async updateArticle(id, updates) {
    return api.put(`/api/articles/${id}`, updates);
  },

  async deleteArticle(id) {
    return api.delete(`/api/articles/${id}`);
  },

  async searchArticles(searchParams) {
    return api.post('/api/articles/search', searchParams);
  },

  async analyzeArticle(id) {
    return api.post(`/api/articles/${id}/analyze`);
  },

  async getRelatedArticles(id, limit = 10) {
    return api.get(`/api/articles/${id}/related?limit=${limit}`);
  },

  async getArticleStats() {
    return api.get('/api/articles/stats/overview');
  },

  // Stories
  async getStories(params = {}) {
    const queryParams = new URLSearchParams();
    Object.keys(params).forEach(key => {
      if (params[key] !== undefined && params[key] !== null) {
        queryParams.append(key, params[key]);
      }
    });
    return api.get(`/api/stories/?${queryParams.toString()}`);
  },

  async getStory(id) {
    return api.get(`/api/stories/${id}`);
  },

  async getStoryDossier(id) {
    return api.get(`/api/stories/${id}/dossier`);
  },

  async getStoryEvolution(id, period = 'week') {
    return api.get(`/api/stories/${id}/evolution?period=${period}`);
  },

  async createStory(story) {
    return api.post('/api/stories/', story);
  },

  async updateStory(id, updates) {
    return api.put(`/api/stories/${id}`, updates);
  },

  async addArticleToStory(storyId, articleId) {
    return api.post(`/api/stories/${storyId}/articles/${articleId}`);
  },

  async removeArticleFromStory(storyId, articleId) {
    return api.delete(`/api/stories/${storyId}/articles/${articleId}`);
  },

  async getStoryStats() {
    return api.get('/api/stories/stats/overview');
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
        isOnline: false,
        lastUpdate: null,
        version: 'v2.7.0',
        status: 'offline',
        error: error.message,
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
      // Return fallback data
      return {
        articleCount: 0,
        clusterCount: 0,
        entityCount: 0,
        sourceCount: 0,
        recentArticles: [],
        topSources: [],
        topEntities: [],
        feedHealth: [],
      };
    }
  },

  // Articles - Use the correct endpoint
  async getArticles(filters = {}) {
    try {
      const response = await api.get('/api/articles', { params: filters });
      
      // Transform the API response to match what the React component expects
      const transformedArticles = (response.data.articles || []).map(article => ({
        id: article.id || Math.random().toString(36).substr(2, 9),
        title: article.title || article.content?.substring(0, 50) + '...',
        content: article.content,
        url: article.url || '#',
        source: article.source || 'Unknown Source',
        publishedDate: article.published_date || article.publishedDate || new Date().toISOString(),
        category: article.category || 'General',
        language: article.language || 'en',
        qualityScore: article.quality_score || article.qualityScore || 0.5,
        processingStatus: article.processing_status || article.processingStatus || 'processed',
        clusterId: article.cluster_id || article.clusterId,
        entities: article.entities || [],
        created_at: article.created_at,
        updated_at: article.updated_at,
        summary: article.summary
      }));
      
      return {
        success: true,
        articles: transformedArticles,
        total: response.data.total || transformedArticles.length,
        page: response.data.page || 1,
        totalPages: response.data.total_pages || 1,
        filters: filters
      };
    } catch (error) {
      console.error('Failed to get articles:', error);
      // Return fallback data
      return {
        list: [],
        total: 0,
        filters: filters,
        status: 'fallback_data'
      };
    }
  },

  // Clusters - Transform API response to match component expectations
  async getClusters() {
    try {
      const response = await api.get('/api/clusters');
      
      // Transform the API response to match what the React component expects
      const transformedClusters = (response.data.clusters || []).map(cluster => ({
        id: cluster.id || Math.random().toString(36).substr(2, 9),
        topic: cluster.topic || cluster.name || 'Untitled Cluster',
        summary: cluster.summary || `Cluster with ${cluster.article_count || cluster.articleCount || 0} articles`,
        articleCount: cluster.article_count || cluster.articleCount || 0,
        cohesionScore: cluster.cohesion_score || cluster.cohesionScore || 0.5,
        trendScore: cluster.trend_score || cluster.trendScore || Math.floor(Math.random() * 100),
        category: cluster.category || 'General',
        lastUpdated: cluster.last_updated || cluster.lastUpdated || cluster.dateRange?.end || new Date().toISOString(),
        createdDate: cluster.created_date || cluster.createdDate || cluster.dateRange?.start || new Date().toISOString(),
        keyEntities: cluster.entities || [],
        articles: cluster.articles || []
      }));
      
      return {
        success: true,
        data: transformedClusters,
        total: response.data.total || transformedClusters.length
      };
    } catch (error) {
      console.error('Failed to get clusters:', error);
      // Return mock data
      return {
        list: [
          { id: 1, topic: 'Technology News', summary: 'Latest tech developments', articleCount: 45, cohesionScore: 0.85 },
          { id: 2, topic: 'Business Updates', summary: 'Business and finance news', articleCount: 32, cohesionScore: 0.78 },
          { id: 3, topic: 'World Events', summary: 'Global political events', articleCount: 28, cohesionScore: 0.72 }
        ],
        total: 3,
        status: 'mock_data'
      };
    }
  },

  // Entities - Transform API response to match component expectations
  async getEntities(type = 'PERSON') {
    try {
      const response = await api.get('/api/entities', { params: { type } });
      
      // Transform the API response to match what the React component expects
      const transformedEntities = (response.data.entities || []).map(entity => ({
        id: entity.id || Math.random().toString(36).substr(2, 9),
        text: entity.name || entity.text || entity.entity_name,
        type: entity.type || entity.entity_type || 'UNKNOWN',
        frequency: entity.frequency || entity.count || 1,
        confidence: entity.confidence || entity.score || 0.5
      }));
      
      return {
        success: true,
        data: transformedEntities,
        total: response.data.total || transformedEntities.length,
        type: type
      };
    } catch (error) {
      console.error('Failed to get entities:', error);
      // Return mock data
      return {
        success: true,
        data: [
          { id: 1, text: 'John Smith', type: 'PERSON', frequency: 15, confidence: 0.95 },
          { id: 2, text: 'Jane Doe', type: 'PERSON', frequency: 12, confidence: 0.92 },
          { id: 3, text: 'Tech Corp', type: 'ORG', frequency: 8, confidence: 0.88 }
        ],
        total: 3,
        status: 'mock_data'
      };
    }
  },

  // Sources - Use mock data for now since endpoint doesn't exist
  async getSources() {
    try {
      const response = await api.get('/api/sources');
      return response;
    } catch (error) {
      console.error('Failed to get sources:', error);
      // Return mock data
      return {
        sources: [
          { id: 1, name: 'BBC News', url: 'https://bbc.com', category: 'General', isActive: true },
          { id: 2, name: 'Reuters', url: 'https://reuters.com', category: 'General', isActive: true },
          { id: 3, name: 'TechCrunch', url: 'https://techcrunch.com', category: 'Technology', isActive: true }
        ],
        total: 3,
        status: 'mock_data'
      };
    }
  },

  // Search - Use mock data for now since endpoint doesn't exist
  async search(query, filters = {}) {
    try {
      const response = await api.get('/api/search', { params: { q: query, ...filters } });
      return response;
    } catch (error) {
      console.error('Search failed:', error);
      // Return mock search results
      return {
        results: [
          { id: 1, title: 'Sample Article', content: 'This is a sample article content...', source: 'Mock Source' }
        ],
        query: query,
        filters: filters,
        status: 'mock_data'
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
      throw error;
    }
  },

  // Health check
  async healthCheck() {
    try {
      const response = await api.get('/health');
      return response;
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  },

  // ML Processing
  async processArticle(articleId) {
    try {
      const response = await api.post(`/api/ml/process-article/${articleId}`);
      return response;
    } catch (error) {
      console.error('Failed to process article:', error);
      throw error;
    }
  },

  async processAllArticles() {
    try {
      const response = await api.post('/api/ml/process-all');
      return response;
    } catch (error) {
      console.error('Failed to process all articles:', error);
      throw error;
    }
  },

  async summarizeContent(content, title) {
    try {
      const response = await api.post('/api/ml/summarize', { content, title });
      return response;
    } catch (error) {
      console.error('Failed to summarize content:', error);
      throw error;
    }
  },

  async analyzeArguments(content, title) {
    try {
      const response = await api.post('/api/ml/analyze-arguments', { content, title });
      return response;
    } catch (error) {
      console.error('Failed to analyze arguments:', error);
      throw error;
    }
  },

  async getMLProcessingStatus() {
    try {
      const response = await api.get('/api/ml/processing-status');
      return response;
    } catch (error) {
      console.error('Failed to get ML processing status:', error);
      throw error;
    }
  },

  // ML Background Processing and Timing
  async queueArticleForMLProcessing(articleId, operationType = 'full_analysis', priority = 0, modelName = null) {
    try {
      const response = await api.post(`/api/ml/queue-article/${articleId}`, {
        operation_type: operationType,
        priority: priority,
        model_name: modelName
      });
      return response;
    } catch (error) {
      console.error('Failed to queue article for ML processing:', error);
      throw error;
    }
  },

  async getArticleMLProcessingStatus(articleId) {
    try {
      const response = await api.get(`/api/ml/processing-status/${articleId}`);
      return response;
    } catch (error) {
      console.error('Failed to get article ML processing status:', error);
      throw error;
    }
  },

  async getAllMLProcessingStatus() {
    try {
      const response = await api.get('/api/ml/processing-status');
      return response;
    } catch (error) {
      console.error('Failed to get all ML processing status:', error);
      throw error;
    }
  },

  async getMLQueueStatus() {
    try {
      const response = await api.get('/api/ml/queue-status');
      return response;
    } catch (error) {
      console.error('Failed to get ML queue status:', error);
      throw error;
    }
  },

  async getMLTimingStats() {
    try {
      const response = await api.get('/api/ml/timing-stats');
      return response;
    } catch (error) {
      console.error('Failed to get ML timing stats:', error);
      throw error;
    }
  },

  // RAG Enhanced Services
  async buildEnhancedRAGContext(query, contextType = 'comprehensive', maxArticles = 25, includeMLAnalysis = true) {
    try {
      const response = await api.post('/api/rag/enhanced-context', {
        query: query,
        context_type: contextType,
        max_articles: maxArticles,
        include_ml_analysis: includeMLAnalysis
      });
      return response;
    } catch (error) {
      console.error('Failed to build enhanced RAG context:', error);
      throw error;
    }
  },

  async buildStoryDossierWithRAG(storyId, storyTitle = null, includeHistorical = true, includeRelated = true, includeAnalysis = true) {
    try {
      const response = await api.post(`/api/rag/story-dossier/${storyId}`, {
        story_title: storyTitle,
        include_historical: includeHistorical,
        include_related: includeRelated,
        include_analysis: includeAnalysis
      });
      return response;
    } catch (error) {
      console.error('Failed to build story dossier with RAG:', error);
      throw error;
    }
  },

  async getRAGStatistics() {
    try {
      const response = await api.get('/api/rag/statistics');
      return response;
    } catch (error) {
      console.error('Failed to get RAG statistics:', error);
      throw error;
    }
  },

  async performRAGSearch(query, searchType = 'comprehensive', maxResults = 20) {
    try {
      const response = await api.post('/api/rag/search', {
        query: query,
        search_type: searchType,
        max_results: maxResults
      });
      return response;
    } catch (error) {
      console.error('Failed to perform RAG search:', error);
      throw error;
    }
  },

  async performComprehensiveResearch(query, storyKeywords = [], includeExternal = true, includeInternal = true) {
    try {
      const response = await api.post('/api/rag/comprehensive-research', {
        query: query,
        story_keywords: storyKeywords,
        include_external: includeExternal,
        include_internal: includeInternal
      });
      return response;
    } catch (error) {
      console.error('Failed to perform comprehensive research:', error);
      throw error;
    }
  },

  async getExternalServicesStatus() {
    try {
      const response = await api.get('/api/rag/external-services-status');
      return response;
    } catch (error) {
      console.error('Failed to get external services status:', error);
      throw error;
    }
  },

  // Storyline Tracking
  async getTopicCloud(days = 1) {
    try {
      const response = await api.get(`/api/storyline/topic-cloud?days=${days}`);
      return response;
    } catch (error) {
      console.error('Failed to get topic cloud:', error);
      throw error;
    }
  },

  async getStoryDossier(storyId, includeRag = true) {
    try {
      const response = await api.get(`/api/storyline/dossier/${storyId}?include_rag=${includeRag}`);
      return response;
    } catch (error) {
      console.error('Failed to get story dossier:', error);
      throw error;
    }
  },

  async getStoryEvolution(storyId, days = 7) {
    try {
      const response = await api.get(`/api/storyline/evolution/${storyId}?days=${days}`);
      return response;
    } catch (error) {
      console.error('Failed to get story evolution:', error);
      throw error;
    }
  },

  // Deduplication
  async detectDuplicates(similarityThreshold = 0.85, maxArticles = 1000) {
    try {
      const response = await api.get(`/api/deduplication/detect?similarity_threshold=${similarityThreshold}&max_articles=${maxArticles}`);
      return response;
    } catch (error) {
      console.error('Failed to detect duplicates:', error);
      throw error;
    }
  },

  async removeDuplicates(autoRemove = false, similarityThreshold = 0.85) {
    try {
      const response = await api.post('/api/deduplication/remove', {
        auto_remove: autoRemove,
        similarity_threshold: similarityThreshold
      });
      return response;
    } catch (error) {
      console.error('Failed to remove duplicates:', error);
      throw error;
    }
  },

  async getDeduplicationStats() {
    try {
      const response = await api.get('/api/deduplication/stats');
      return response;
    } catch (error) {
      console.error('Failed to get deduplication stats:', error);
      throw error;
    }
  },

  // Daily Briefings
  async generateDailyBriefing(date = null, includeDeduplication = true, includeStorylines = true) {
    try {
      let url = `/api/briefing/daily?include_deduplication=${includeDeduplication}&include_storylines=${includeStorylines}`;
      if (date) {
        url += `&date=${date}`;
      }
      const response = await api.get(url);
      return response;
    } catch (error) {
      console.error('Failed to generate daily briefing:', error);
      throw error;
    }
  },

  async generateWeeklyBriefing(weekStart = null) {
    try {
      let url = '/api/briefing/weekly';
      if (weekStart) {
        url += `?week_start=${weekStart}`;
      }
      const response = await api.get(url);
      return response;
    } catch (error) {
      console.error('Failed to generate weekly briefing:', error);
      throw error;
    }
  },

  // Living Story Narrator
  async getLivingNarratorStatus() {
    try {
      const response = await api.get('/api/automation/living-narrator/status');
      return response;
    } catch (error) {
      console.error('Failed to get Living Story Narrator status:', error);
      throw error;
    }
  },

  async triggerStoryConsolidation() {
    try {
      const response = await api.post('/api/automation/living-narrator/consolidate');
      return response;
    } catch (error) {
      console.error('Failed to trigger story consolidation:', error);
      throw error;
    }
  },

  async generateDailyDigest() {
    try {
      const response = await api.post('/api/automation/living-narrator/digest');
      return response;
    } catch (error) {
      console.error('Failed to generate daily digest:', error);
      throw error;
    }
  },

  async triggerDatabaseCleanup() {
    try {
      const response = await api.post('/api/automation/living-narrator/cleanup');
      return response;
    } catch (error) {
      console.error('Failed to trigger database cleanup:', error);
      throw error;
    }
  },

  async getDailyDigests(params = {}) {
    try {
      const response = await api.get('/api/daily-digests', { params });
      return response;
    } catch (error) {
      console.error('Failed to get daily digests:', error);
      throw error;
    }
  },

  // Enhanced Preprocessing
  async getPreprocessingStatus() {
    try {
      const response = await api.get('/api/automation/preprocessing/status');
      return response;
    } catch (error) {
      console.error('Failed to get preprocessing status:', error);
      throw error;
    }
  },

  async runPreprocessing(data = {}) {
    try {
      const response = await api.post('/api/automation/preprocessing/run', data);
      return response;
    } catch (error) {
      console.error('Failed to run preprocessing:', error);
      throw error;
    }
  },

  async getMasterArticles(params = {}) {
    try {
      const response = await api.get('/api/master-articles', { params });
      return response;
    } catch (error) {
      console.error('Failed to get master articles:', error);
      throw error;
    }
  },

  // Pipeline automation functions
  async startPipeline() {
    try {
      const response = await api.post('/api/automation/pipeline/start');
      return response;
    } catch (error) {
      console.error('Failed to start pipeline:', error);
      throw error;
    }
  },

  async stopPipeline() {
    try {
      const response = await api.post('/api/automation/pipeline/stop');
      return response;
    } catch (error) {
      console.error('Failed to stop pipeline:', error);
      throw error;
    }
  },

  async getPipelineStatus() {
    try {
      const response = await api.get('/api/automation/pipeline/status');
      return response;
    } catch (error) {
      console.error('Failed to get pipeline status:', error);
      throw error;
    }
  },

  // Story Threads - Missing function needed by components
  async getStoryThreads(filters = {}) {
    try {
      const response = await api.get('/api/prioritization/story-threads', { params: filters });
      return {
        success: true,
        data: response.data.threads || response.data || [],
        total: response.data.total || 0
      };
    } catch (error) {
      console.error('Failed to get story threads:', error);
      return {
        success: true,
        data: [],
        total: 0,
        status: 'error'
      };
    }
  },

  // RSS Collection - Missing function
  async collectRSSFeeds() {
    try {
      const response = await api.post('/api/rss/collect-now');
      return response;
    } catch (error) {
      console.error('Failed to collect RSS feeds:', error);
      throw error;
    }
  },

  // RSS Collection Progress Tracking
  async getRSSCollectionProgress(collectionId) {
    try {
      const response = await api.get(`/api/rss/progress/${collectionId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get RSS collection progress:', error);
      throw error;
    }
  },

  async getAllRSSCollectionProgress() {
    try {
      const response = await api.get('/api/rss/progress');
      return response.data;
    } catch (error) {
      console.error('Failed to get RSS collection progress:', error);
      throw error;
    }
  },

  async cancelRSSCollection(collectionId) {
    try {
      const response = await api.post(`/api/rss/progress/${collectionId}/cancel`);
      return response.data;
    } catch (error) {
      console.error('Failed to cancel RSS collection:', error);
      throw error;
    }
  },

  // Additional ML Functions for consistency
  async getMLStatus() {
    try {
      const response = await api.get('/api/ml/status');
      return response;
    } catch (error) {
      console.error('Failed to get ML status:', error);
      return { success: false, error: error.message };
    }
  },

  // Additional automation functions
  async getAutomationStatus() {
    try {
      const response = await api.get('/api/automation/pipeline/status');
      return response;
    } catch (error) {
      console.error('Failed to get automation status:', error);
      return { success: false, error: error.message };
    }
  },

  // Daily digest functions
  async getTodayArticles() {
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await this.getArticles({ date: today });
      return response;
    } catch (error) {
      console.error('Failed to get today\'s articles:', error);
      return { success: false, articles: [], error: error.message };
    }
  },
};

export default newsSystemService;
