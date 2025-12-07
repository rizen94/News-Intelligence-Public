import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  config => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  error => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  },
);

// Response interceptor
api.interceptors.response.use(
  response => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  error => {
    console.error(
      'API Response Error:',
      error.response?.status,
      error.response?.data,
    );
    return Promise.reject(error);
  },
);

export { api };

export const apiService = {
  // Articles
  getArticles: async(params: any = {}) => {
    try {
      // Don't set default hours - let the API return all articles by default
      // Only include hours if explicitly provided
      const requestParams: any = { ...params };
      if (params.hours !== undefined) {
        requestParams.hours = params.hours;
      }
      // Otherwise, don't include hours parameter so API returns all articles
      const response = await api.get(
        '/api/v4/news-aggregation/articles/recent',
        { params: requestParams },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch articles:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getArticle: async(id: string) => {
    try {
      const response = await api.get(`/api/v4/news-aggregation/articles/${id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // RSS Feeds
  getRSSFeeds: async(params: any = {}) => {
    try {
      const response = await api.get('/api/v4/news-aggregation/rss-feeds', {
        params,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch RSS feeds:', error);
      return { success: false, error: (error as any).message };
    }
  },

  updateRSSFeeds: async() => {
    try {
      const response = await api.post(
        '/api/v4/news-aggregation/rss/collect-now',
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update RSS feeds:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // Storylines
  getStorylines: async(params: any = {}) => {
    try {
      const response = await api.get(
        '/api/v4/storyline-management/storylines',
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storylines:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getStoryline: async(id: string) => {
    try {
      const response = await api.get(
        `/api/v4/storyline-management/storylines/${id}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storyline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getStorylineTimeline: async(id: string | number) => {
    try {
      const response = await api.get(
        `/api/v4/storyline-management/storylines/${id}/timeline`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storyline timeline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  createStoryline: async(storylineData: {
    title: string;
    description?: string;
  }) => {
    try {
      const response = await api.post(
        '/api/v4/storyline-management/storylines',
        storylineData,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to create storyline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  updateStoryline: async(
    id: string | number,
    storylineData: { title: string; description?: string; status?: string },
  ) => {
    try {
      const response = await api.put(
        `/api/v4/storyline-management/storylines/${id}`,
        storylineData,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update storyline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  deleteStoryline: async(id: string | number) => {
    try {
      const response = await api.delete(
        `/api/v4/storyline-management/storylines/${id}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to delete storyline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  convertTopicToStoryline: async(
    topicName: string,
    storylineTitle?: string,
  ) => {
    try {
      const response = await api.post(
        `/api/v4/content-analysis/topics/${encodeURIComponent(
          topicName,
        )}/convert-to-storyline`,
        {
          storyline_title: storylineTitle || `Storyline: ${topicName}`,
        },
      );
      return response.data;
    } catch (error) {
      console.error(
        `Failed to convert topic ${topicName} to storyline:`,
        error,
      );
      return { success: false, error: (error as any).message };
    }
  },

  // Automation endpoints
  getAutomationSettings: async(storylineId: string | number) => {
    try {
      const response = await api.get(
        `/api/v4/storyline-management/storylines/${storylineId}/automation/settings`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get automation settings:', error);
      return { success: false, error: (error as any).message };
    }
  },

  updateAutomationSettings: async(storylineId: string | number, settings: any) => {
    try {
      const response = await api.put(
        `/api/v4/storyline-management/storylines/${storylineId}/automation/settings`,
        settings,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update automation settings:', error);
      return { success: false, error: (error as any).message };
    }
  },

  discoverArticles: async(storylineId: string | number, forceRefresh: boolean = false) => {
    try {
      const response = await api.post(
        `/api/v4/storyline-management/storylines/${storylineId}/automation/discover?force_refresh=${forceRefresh}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to discover articles:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getArticleSuggestions: async(storylineId: string | number, status?: string) => {
    try {
      const params: any = {};
      if (status) {
        params.status = status;
      }
      const response = await api.get(
        `/api/v4/storyline-management/storylines/${storylineId}/automation/suggestions`,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get article suggestions:', error);
      return { success: false, error: (error as any).message };
    }
  },

  approveSuggestion: async(storylineId: string | number, suggestionId: number) => {
    try {
      const response = await api.post(
        `/api/v4/storyline-management/storylines/${storylineId}/automation/suggestions/${suggestionId}/approve`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to approve suggestion:', error);
      return { success: false, error: (error as any).message };
    }
  },

  rejectSuggestion: async(storylineId: string | number, suggestionId: number, reason?: string) => {
    try {
      const params: any = {};
      if (reason) {
        params.reason = reason;
      }
      const response = await api.post(
        `/api/v4/storyline-management/storylines/${storylineId}/automation/suggestions/${suggestionId}/reject`,
        null,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to reject suggestion:', error);
      return { success: false, error: (error as any).message };
    }
  },

  analyzeStoryline: async(id: string | number) => {
    try {
      const response = await api.post(
        `/api/v4/storyline-management/storylines/${id}/analyze`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to analyze storyline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getAvailableArticlesForStoryline: async(
    storylineId: string | number,
    limit: number = 50,
    search?: string,
  ) => {
    try {
      const params: any = { limit };
      if (search) {
        params.search = search;
      }
      const response = await api.get(
        `/api/v4/storyline-management/storylines/${storylineId}/available-articles`,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch available articles:', error);
      return { success: false, error: (error as any).message };
    }
  },

  addArticleToStoryline: async(
    storylineId: string | number,
    articleId: string | number,
  ) => {
    try {
      const response = await api.post(
        `/api/v4/storyline-management/storylines/${storylineId}/articles/${articleId}`,
      );
      return response.data;
    } catch (error: any) {
      console.error('Failed to add article to storyline:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to add article to storyline';
      return { success: false, error: errorMessage, message: errorMessage };
    }
  },

  removeArticleFromStoryline: async(
    storylineId: string | number,
    articleId: string | number,
  ) => {
    try {
      const response = await api.delete(
        `/api/v4/storyline-management/storylines/${storylineId}/articles/${articleId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to remove article from storyline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // System Monitoring
  getHealth: async() => {
    try {
      const response = await api.get('/api/v4/system-monitoring/health');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch health:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getMonitoringDashboard: async() => {
    try {
      const response = await api.get('/api/v4/system-monitoring/status');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch monitoring dashboard:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getPipelineStatus: async() => {
    try {
      const response = await api.get('/api/v4/system-monitoring/pipeline-status');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch pipeline status:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // Content Analysis
  getTopics: async(params: any = {}) => {
    try {
      const response = await api.get('/api/v4/content-analysis/topics', {
        params,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topics:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getCategoryStats: async() => {
    try {
      const response = await api.get(
        '/api/v4/content-analysis/topics/categories/stats',
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch category stats:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getTopicArticles: async(
    topicName: string,
    limit: number = 20,
    offset: number = 0,
  ) => {
    try {
      const response = await api.get(
        `/api/v4/content-analysis/topics/${encodeURIComponent(
          topicName,
        )}/articles`,
        {
          params: { limit, offset },
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic articles:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getTopicSummary: async(topicName: string) => {
    try {
      const response = await api.get(
        `/api/v4/content-analysis/topics/${encodeURIComponent(
          topicName,
        )}/summary`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic summary:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getWordCloud: async(
    timePeriodHours: number = 24,
    minFrequency: number = 1,
  ) => {
    try {
      const response = await api.get(
        '/api/v4/content-analysis/topics/word-cloud',
        {
          params: {
            time_period_hours: timePeriodHours,
            min_frequency: minFrequency,
          },
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch word cloud:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getBigPicture: async(timePeriodHours: number = 24) => {
    try {
      const response = await api.get(
        '/api/v4/content-analysis/topics/big-picture',
        {
          params: { time_period_hours: timePeriodHours },
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch big picture:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getTrendingTopics: async(
    timePeriodHours: number = 24,
    limit: number = 10,
  ) => {
    try {
      const response = await api.get(
        '/api/v4/content-analysis/topics/trending',
        {
          params: { time_period_hours: timePeriodHours, limit },
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch trending topics:', error);
      return { success: false, error: (error as any).message };
    }
  },

  clusterArticles: async(params: { limit?: number } = {}) => {
    try {
      const response = await api.post(
        '/api/v4/content-analysis/topics/cluster',
        {
          limit: params.limit ?? 100,
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to start article clustering:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // Pipeline Performance (placeholder)
  getPipelinePerformance: async() => {
    try {
      console.warn(
        'Pipeline performance endpoint not implemented, returning default data',
      );
      return {
        success: true,
        data: {
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
        },
      };
    } catch (error) {
      console.error('Failed to fetch pipeline performance:', error);
      return {
        success: false,
        error: 'Pipeline performance endpoint not available',
        data: {
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
        },
      };
    }
  },

  // Article Deduplication methods
  getArticleDeduplicationStats: async() => {
    try {
      const response = await api.get('/api/v4/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article deduplication stats:', error);
      return { success: false, error: (error as any).message };
    }
  },

  detectArticleDuplicates: async(timePeriodHours: number = 24) => {
    try {
      const response = await api.get('/api/v4/articles/duplicates/detect', {
        params: { time_period_hours: timePeriodHours },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to detect article duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getURLDuplicates: async(timePeriodHours: number = 24) => {
    try {
      const response = await api.get('/api/v4/articles/duplicates/url', {
        params: { time_period_hours: timePeriodHours },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch URL duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getContentDuplicates: async(timePeriodHours: number = 24) => {
    try {
      const response = await api.get('/api/v4/articles/duplicates/content', {
        params: { time_period_hours: timePeriodHours },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch content duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getSimilarArticles: async(
    timePeriodHours: number = 24,
    similarityThreshold: number = 0.85,
  ) => {
    try {
      const response = await api.get('/api/v4/articles/duplicates/similar', {
        params: {
          time_period_hours: timePeriodHours,
          similarity_threshold: similarityThreshold,
        },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch similar articles:', error);
      return { success: false, error: (error as any).message };
    }
  },

  autoMergeDuplicates: async(dryRun: boolean = true) => {
    try {
      const response = await api.post(
        '/api/v4/articles/duplicates/auto-merge',
        { dry_run: dryRun },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to auto-merge duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  },

  addDeduplicationPrevention: async() => {
    try {
      const response = await api.post('/api/v4/articles/duplicates/prevent');
      return response.data;
    } catch (error) {
      console.error('Failed to add deduplication prevention:', error);
      return { success: false, error: (error as any).message };
    }
  },

  analyzeArticleSimilarity: async(articleId1: string, articleId2: string) => {
    try {
      const response = await api.post(
        '/api/v4/articles/duplicates/analyze-similarity',
        {
          article_id1: articleId1,
          article_id2: articleId2,
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to analyze article similarity:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // Pipeline orchestration
  runAllPipelineProcesses: async() => {
    try {
      const response = await api.post(
        '/api/v4/system-monitoring/pipeline/run-all',
      );
      return response.data;
    } catch (error) {
      console.error('Failed to run all pipeline processes:', error);
      return { success: false, error: (error as any).message };
    }
  },

  triggerPipeline: async() => {
    try {
      // Trigger clustering which can act as pipeline trigger
      const response = await api.post(
        '/api/v4/content-analysis/topics/cluster',
        { limit: 100 },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to trigger pipeline:', error);
      return { success: false, error: (error as any).message };
    }
  },

  runAIAnalysis: async() => {
    try {
      // Trigger AI analysis via content analysis endpoint
      const response = await api.post(
        '/api/v4/content-analysis/sentiment/analyze',
        {
          content: 'Batch analysis trigger',
        },
      );
      return {
        success: true,
        message: 'AI analysis started',
        data: response.data,
      };
    } catch (error) {
      console.error('Failed to run AI analysis:', error);
      return { success: false, error: (error as any).message };
    }
  },

  // Topic Management Methods (for topic-management domain)
  getManagedTopics: async(params: any = {}) => {
    try {
      const { limit = 50, offset = 0, category, status, search, sort_by = 'accuracy_score' } = params;
      const queryParams = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        sort_by,
      });
      if (category) queryParams.append('category', category);
      if (status) queryParams.append('status', status);
      if (search) queryParams.append('search', search);

      const response = await api.get(`/api/v4/topic-management/topics?${queryParams}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topics:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getManagedTopic: async(topicId: number) => {
    try {
      const response = await api.get(`/api/v4/topic-management/topics/${topicId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getManagedTopicArticles: async(topicId: number, params: any = {}) => {
    try {
      const { limit = 20, offset = 0 } = params;
      const queryParams = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
      });

      const response = await api.get(`/api/v4/topic-management/topics/${topicId}/articles?${queryParams}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic articles:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getArticleTopics: async(articleId: number) => {
    try {
      const response = await api.get(`/api/v4/topic-management/articles/${articleId}/topics`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article topics:', error);
      return { success: false, error: (error as any).message };
    }
  },

  processArticleTopics: async(articleId: number) => {
    try {
      const response = await api.post(`/api/v4/topic-management/articles/${articleId}/process-topics`);
      return response.data;
    } catch (error) {
      console.error('Failed to process article topics:', error);
      return { success: false, error: (error as any).message };
    }
  },

  submitTopicFeedback: async(assignmentId: number, feedback: { is_correct: boolean; feedback_notes?: string; validated_by?: string }) => {
    try {
      const response = await api.post(`/api/v4/topic-management/assignments/${assignmentId}/feedback`, feedback);
      return response.data;
    } catch (error) {
      console.error('Failed to submit topic feedback:', error);
      return { success: false, error: (error as any).message };
    }
  },

  getTopicsNeedingReview: async(threshold: number = 0.6, limit: number = 50) => {
    try {
      const response = await api.get(`/api/v4/topic-management/topics/needing-review?threshold=${threshold}&limit=${limit}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topics needing review:', error);
      return { success: false, error: (error as any).message };
    }
  },

  createTopic: async(topic: { name: string; description?: string; category?: string; keywords?: string[] }) => {
    try {
      const response = await api.post('/api/v4/topic-management/topics', topic);
      return response.data;
    } catch (error) {
      console.error('Failed to create topic:', error);
      return { success: false, error: (error as any).message };
    }
  },

  updateTopic: async(topicId: number, updates: { description?: string; category?: string; keywords?: string[]; status?: string }) => {
    try {
      const response = await api.put(`/api/v4/topic-management/topics/${topicId}`, updates);
      return response.data;
    } catch (error) {
      console.error('Failed to update topic:', error);
      return { success: false, error: (error as any).message };
    }
  },
};

export default apiService;
