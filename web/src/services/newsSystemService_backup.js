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

  // Intelligence
  async getIntelligenceInsights(category, limit) {
    try {
      const response = await api.get('/api/intelligence/insights', {
        params: { category, limit }
      });
      return response;
    } catch (error) {
      console.error('Failed to get intelligence insights:', error);
      // Return mock data for development
      return {
        insights: [
          {
            id: 'insight_1',
            title: 'Rising Security Concerns in Tech Sector',
            description: 'Analysis shows increasing mentions of security vulnerabilities in technology news over the past 24 hours.',
            category: 'security',
            confidence: 0.85,
            created_at: new Date().toISOString(),
            data: {
              mentions: 45,
              sources: 12,
              trend: '+23%'
            }
          },
          {
            id: 'insight_2',
            title: 'Business Market Sentiment Shift',
            description: 'Recent business news indicates a shift towards more positive sentiment in market analysis.',
            category: 'business',
            confidence: 0.72,
            created_at: new Date(Date.now() - 3600000).toISOString(),
            data: {
              sentiment_score: 0.65,
              articles_analyzed: 89,
              change: '+15%'
            }
          },
          {
            id: 'insight_3',
            title: 'Political Policy Changes',
            description: 'Significant coverage of new policy announcements across multiple political news sources.',
            category: 'politics',
            confidence: 0.91,
            created_at: new Date(Date.now() - 7200000).toISOString(),
            data: {
              policy_mentions: 67,
              coverage_sources: 18,
              impact_score: 0.78
            }
          },
          {
            id: 'insight_4',
            title: 'Technology Innovation Trends',
            description: 'Emerging technology trends showing increased innovation coverage in tech sector.',
            category: 'technology',
            confidence: 0.68,
            created_at: new Date(Date.now() - 10800000).toISOString(),
            data: {
              innovation_mentions: 34,
              patent_discussions: 12,
              trend_direction: 'up'
            }
          }
        ],
        total: 4
      };
    }
  },

  async getIntelligenceTrends() {
    try {
      const response = await api.get('/api/intelligence/trends');
      return response;
    } catch (error) {
      console.error('Failed to get intelligence trends:', error);
      // Return mock data for development
      return {
        trends: [
          {
            id: 'trend_1',
            name: 'AI Regulation Discussions',
            description: 'Increasing coverage of AI regulation and policy discussions across multiple news sources.',
            direction: 'up',
            change: 34,
            updated_at: new Date().toISOString()
          },
          {
            id: 'trend_2',
            name: 'Climate Change Policy',
            description: 'Sustained coverage of climate change policy developments and international agreements.',
            direction: 'flat',
            change: 2,
            updated_at: new Date(Date.now() - 7200000).toISOString()
          },
          {
            id: 'trend_3',
            name: 'Cryptocurrency Market',
            description: 'Volatile coverage of cryptocurrency market movements and regulatory developments.',
            direction: 'down',
            change: -18,
            updated_at: new Date(Date.now() - 14400000).toISOString()
          }
        ]
      };
    }
  },

  async getIntelligenceAlerts() {
    try {
      const response = await api.get('/api/intelligence/alerts');
      return response;
    } catch (error) {
      console.error('Failed to get intelligence alerts:', error);
      // Return mock data for development
      return {
        alerts: [
          {
            id: 'alert_1',
            title: 'High Volume Security Breach Coverage',
            description: 'Unusual spike in security breach coverage detected across multiple sources.',
            severity: 'critical',
            category: 'security',
            source: 'AI Analysis',
            timestamp: new Date().toISOString()
          },
          {
            id: 'alert_2',
            title: 'Market Volatility Indicators',
            description: 'Multiple indicators suggest increased market volatility in financial news.',
            severity: 'high',
            category: 'business',
            source: 'Trend Analysis',
            timestamp: new Date(Date.now() - 1800000).toISOString()
          },
          {
            id: 'alert_3',
            title: 'Policy Change Detection',
            description: 'New policy announcements detected across multiple government news sources.',
            severity: 'medium',
            category: 'politics',
            source: 'Policy Monitor',
            timestamp: new Date(Date.now() - 3600000).toISOString()
          }
        ]
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
      // Return mock data for development
      return {
        feeds: [
          {
            id: 'feed_1',
            name: 'TechCrunch',
            url: 'https://techcrunch.com/feed/',
            description: 'Technology news and startup coverage',
            category: 'technology',
            language: 'en',
            status: 'active',
            is_active: true,
            update_frequency: 30,
            max_articles_per_update: 50,
            articles_count: 1247,
            articles_today: 23,
            last_updated: new Date().toISOString(),
            success_rate: 95,
            avg_response_time: 1200,
            tags: ['tech', 'startups', 'innovation'],
            custom_headers: {},
            filters: {
              keywords: ['AI', 'startup', 'funding'],
              exclude_keywords: ['advertisement'],
              min_length: 100,
              max_length: 10000
            }
          },
          {
            id: 'feed_2',
            name: 'BBC News',
            url: 'http://feeds.bbci.co.uk/news/rss.xml',
            description: 'Latest news from BBC',
            category: 'news',
            language: 'en',
            status: 'active',
            is_active: true,
            update_frequency: 15,
            max_articles_per_update: 100,
            articles_count: 3421,
            articles_today: 45,
            last_updated: new Date(Date.now() - 300000).toISOString(),
            success_rate: 98,
            avg_response_time: 800,
            tags: ['news', 'world', 'politics'],
            custom_headers: {},
            filters: {
              keywords: ['breaking', 'news', 'update'],
              exclude_keywords: ['sport', 'weather'],
              min_length: 150,
              max_length: 15000
            }
          },
          {
            id: 'feed_3',
            name: 'Reuters Business',
            url: 'https://feeds.reuters.com/reuters/businessNews',
            description: 'Business and financial news',
            category: 'business',
            language: 'en',
            status: 'warning',
            is_active: true,
            update_frequency: 60,
            max_articles_per_update: 75,
            articles_count: 2156,
            articles_today: 12,
            last_updated: new Date(Date.now() - 1800000).toISOString(),
            success_rate: 87,
            avg_response_time: 2100,
            tags: ['business', 'finance', 'markets'],
            custom_headers: {},
            filters: {
              keywords: ['market', 'business', 'finance'],
              exclude_keywords: ['personal finance'],
              min_length: 200,
              max_length: 12000
            },
            warning_message: 'High response time detected'
          },
          {
            id: 'feed_4',
            name: 'Ars Technica',
            url: 'https://feeds.arstechnica.com/arstechnica/index/',
            description: 'Technology and science news',
            category: 'technology',
            language: 'en',
            status: 'error',
            is_active: false,
            update_frequency: 120,
            max_articles_per_update: 40,
            articles_count: 892,
            articles_today: 0,
            last_updated: new Date(Date.now() - 3600000).toISOString(),
            success_rate: 0,
            avg_response_time: 0,
            tags: ['tech', 'science', 'gadgets'],
            custom_headers: {},
            filters: {
              keywords: ['technology', 'science', 'review'],
              exclude_keywords: ['advertisement'],
              min_length: 100,
              max_length: 8000
            },
            last_error: 'Connection timeout after 30 seconds'
          }
        ],
        total: 4
      };
    }
  },

  async getRSSStats() {
    try {
      const response = await api.get('/api/rss/stats');
      return response;
    } catch (error) {
      console.error('Failed to get RSS stats:', error);
      // Return mock data for development
      return {
        total_feeds: 4,
        active_feeds: 3,
        articles_today: 80,
        articles_this_hour: 12,
        articles_last_24h: 156,
        articles_last_7d: 1089,
        success_rate: 92,
        avg_response_time: 1350,
        overall_health: 88,
        most_active_feed: {
          name: 'BBC News',
          articles_today: 45
        },
        fastest_feed: {
          name: 'BBC News',
          avg_response_time: 800
        },
        most_reliable_feed: {
          name: 'BBC News',
          success_rate: 98
        },
        avg_articles_per_feed: 20
      };
    }
  },

  async addRSSFeed(feedData) {
    try {
      const response = await api.post('/api/rss/feeds', feedData);
      return response;
    } catch (error) {
      console.error('Failed to add RSS feed:', error);
      throw error;
    }
  },

  async updateRSSFeed(feedId, feedData) {
    try {
      const response = await api.put(`/api/rss/feeds/${feedId}`, feedData);
      return response;
    } catch (error) {
      console.error('Failed to update RSS feed:', error);
      throw error;
    }
  },

  async deleteRSSFeed(feedId) {
    try {
      const response = await api.delete(`/api/rss/feeds/${feedId}`);
      return response;
    } catch (error) {
      console.error('Failed to delete RSS feed:', error);
      throw error;
    }
  },

  async testRSSFeed(feedId) {
    try {
      const response = await api.post(`/api/rss/feeds/${feedId}/test`);
      return response;
    } catch (error) {
      console.error('Failed to test RSS feed:', error);
      throw error;
    }
  },

  async refreshRSSFeed(feedId) {
    try {
      const response = await api.post(`/api/rss/feeds/${feedId}/refresh`);
      return response;
    } catch (error) {
      console.error('Failed to refresh RSS feed:', error);
      throw error;
    }
  },

  async toggleRSSFeed(feedId, isActive) {
    try {
      const response = await api.patch(`/api/rss/feeds/${feedId}/toggle`, { is_active: isActive });
      return response;
    } catch (error) {
      console.error('Failed to toggle RSS feed:', error);
      throw error;
    }
  },

  // Deduplication Management
  async getDuplicates() {
    try {
      const response = await api.get('/api/deduplication/duplicates');
      return response;
    } catch (error) {
      console.error('Failed to get duplicates:', error);
      // Return mock data for development
      return {
        duplicates: [
          {
            id: 'dup_1',
            article1: {
              id: 'art_1',
              title: 'AI Revolution Transforms Healthcare Industry',
              content: 'Artificial intelligence is revolutionizing healthcare with new diagnostic tools and treatment methods...',
              source: 'TechCrunch',
              published_at: new Date().toISOString(),
              word_count: 450
            },
            article2: {
              id: 'art_2',
              title: 'Healthcare Industry Transformed by AI Revolution',
              content: 'The healthcare sector is being revolutionized by artificial intelligence, introducing innovative diagnostic tools and treatment approaches...',
              source: 'BBC News',
              published_at: new Date(Date.now() - 3600000).toISOString(),
              word_count: 420
            },
            similarity_score: 0.92,
            title_similarity: 0.88,
            content_similarity: 0.95,
            algorithm: 'content_similarity',
            status: 'pending',
            detected_at: new Date().toISOString()
          },
          {
            id: 'dup_2',
            article1: {
              id: 'art_3',
              title: 'Stock Market Reaches New All-Time High',
              content: 'The stock market has reached unprecedented heights today, with major indices showing strong gains...',
              source: 'Reuters Business',
              published_at: new Date(Date.now() - 7200000).toISOString(),
              word_count: 380
            },
            article2: {
              id: 'art_4',
              title: 'Markets Hit Record Highs in Trading Session',
              content: 'Financial markets achieved record-breaking levels during today\'s trading session, with significant gains across major indices...',
              source: 'BBC News',
              published_at: new Date(Date.now() - 7500000).toISOString(),
              word_count: 395
            },
            similarity_score: 0.87,
            title_similarity: 0.82,
            content_similarity: 0.91,
            algorithm: 'content_similarity',
            status: 'confirmed',
            detected_at: new Date(Date.now() - 1800000).toISOString()
          },
          {
            id: 'dup_3',
            article1: {
              id: 'art_5',
              title: 'Climate Change Summit Reaches Historic Agreement',
              content: 'World leaders have reached a historic agreement on climate change measures at the international summit...',
              source: 'BBC News',
              published_at: new Date(Date.now() - 14400000).toISOString(),
              word_count: 520
            },
            article2: {
              id: 'art_6',
              title: 'Historic Climate Agreement Reached at Summit',
              content: 'An unprecedented climate change agreement has been achieved by global leaders during the international summit...',
              source: 'Reuters Business',
              published_at: new Date(Date.now() - 15000000).toISOString(),
              word_count: 485
            },
            similarity_score: 0.79,
            title_similarity: 0.85,
            content_similarity: 0.76,
            algorithm: 'title_similarity',
            status: 'rejected',
            detected_at: new Date(Date.now() - 3600000).toISOString()
          }
        ],
        total: 3
      };
    }
  },

  async getDeduplicationStats() {
    try {
      const response = await api.get('/api/deduplication/stats');
      return response;
    } catch (error) {
      console.error('Failed to get deduplication stats:', error);
      // Return mock data for development
      return {
        total_duplicates: 3,
        pending_review: 1,
        high_similarity: 2,
        very_high_similarity: 1,
        medium_similarity: 1,
        low_similarity: 0,
        removed_today: 5,
        removed_this_week: 23,
        accuracy_rate: 94,
        algorithm_performance: [
          {
            name: 'Content Similarity',
            detections: 2,
            accuracy: 95
          },
          {
            name: 'Title Similarity',
            detections: 1,
            accuracy: 88
          },
          {
            name: 'URL Similarity',
            detections: 0,
            accuracy: 92
          }
        ],
        recent_actions: [
          {
            type: 'detection',
            description: 'Duplicate detection run completed',
            timestamp: new Date().toISOString(),
            count: 3
          },
          {
            type: 'removal',
            description: 'High similarity duplicates removed',
            timestamp: new Date(Date.now() - 3600000).toISOString(),
            count: 2
          },
          {
            type: 'rejection',
            description: 'False positives marked as not duplicates',
            timestamp: new Date(Date.now() - 7200000).toISOString(),
            count: 1
          }
        ]
      };
    }
  },

  async getDeduplicationSettings() {
    try {
      const response = await api.get('/api/deduplication/settings');
      return response;
    } catch (error) {
      console.error('Failed to get deduplication settings:', error);
      // Return mock data for development
      return {
        settings: {
          similarity_threshold: 0.85,
          auto_remove: false,
          min_article_length: 100,
          max_articles_to_process: 1000,
          enabled_algorithms: ['content_similarity', 'title_similarity', 'url_similarity'],
          exclude_sources: [],
          include_sources: [],
          time_window_hours: 24
        }
      };
    }
  },

  async detectDuplicates(settings) {
    try {
      const response = await api.post('/api/deduplication/detect', settings);
      return response;
    } catch (error) {
      console.error('Failed to detect duplicates:', error);
      throw error;
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
      throw error;
    }
  },

  async markAsNotDuplicate(duplicateId) {
    try {
      const response = await api.post(`/api/deduplication/${duplicateId}/reject`);
      return response;
    } catch (error) {
      console.error('Failed to mark as not duplicate:', error);
      throw error;
    }
  },

  async updateDeduplicationSettings(settings) {
    try {
      const response = await api.put('/api/deduplication/settings', settings);
      return response;
    } catch (error) {
      console.error('Failed to update deduplication settings:', error);
      throw error;
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

  // Clusters - Now using real API endpoint
  async getClusters(filters = {}) {
    try {
      const response = await api.get('/api/clusters', { params: filters });
      
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

  // Entities - Now using real API endpoint
  async getEntities(filters = {}) {
    try {
      const response = await api.get('/api/entities', { params: filters });
      
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

  // Sources - Now using real API endpoint
  async getSources(filters = {}) {
    try {
      const response = await api.get('/api/sources', { params: filters });
      return response;
    } catch (error) {
      console.error('Failed to get sources:', error);
      // Return fallback data
      return {
        sources: [],
        total: 0,
        page: 1,
        per_page: 20
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
      // Return fallback data
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
        dossiers: [],
        total: 0,
        page: 1,
        per_page: 20
      };
    }
  },

  async getRAGDossier(dossierId) {
    try {
      const response = await api.get(`/api/rag/dossiers/${dossierId}`);
      return response;
    } catch (error) {
      console.error('Failed to get RAG dossier:', error);
      return null;
    }
  },

  async createRAGDossier(articleId) {
    try {
      const response = await api.post('/api/rag/dossiers', { article_id: articleId });
      return response;
    } catch (error) {
      console.error('Failed to create RAG dossier:', error);
      return null;
    }
  },

  async getRAGStats() {
    try {
      const response = await api.get('/api/rag/stats');
      return response;
    } catch (error) {
      console.error('Failed to get RAG stats:', error);
      return {
        total_dossiers: 0,
        active_dossiers: 0,
        completed_dossiers: 0,
        plateau_dossiers: 0,
        avg_iterations_per_dossier: 0,
        avg_processing_time: 0,
        success_rate: 0,
        recent_dossiers: []
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
        status: 'offline',
        queue_size: 0,
        processing_rate: 0,
        models_status: {},
        last_processed: null,
        total_processed: 0,
        success_rate: 0
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
      return null;
    }
  },

  async getMLModels() {
    try {
      const response = await api.get('/api/ml-management/models');
      return response;
    } catch (error) {
      console.error('Failed to get ML models:', error);
      return {};
    }
  },

  async getMLPerformance() {
    try {
      const response = await api.get('/api/ml-management/performance');
      return response;
    } catch (error) {
      console.error('Failed to get ML performance:', error);
      return {
        total_processed: 0,
        processing_rate: 0,
        success_rate: 0,
        avg_processing_time: 0,
        queue_size: 0,
        model_performance: {},
        recent_jobs: []
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
      return { suggestions: [] };
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
      return { trending: [], period };
    }
  },

  async getSearchStats() {
    try {
      const response = await api.get('/api/search/stats');
      return response;
    } catch (error) {
      console.error('Failed to get search stats:', error);
      return {
        total_searches: 0,
        popular_queries: [],
        search_trends: [],
        avg_search_time: 0,
        no_results_queries: []
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
