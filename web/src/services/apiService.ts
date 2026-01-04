import { getCurrentDomain } from '../utils/domainHelper';
import { getAPIConnectionManager } from './apiConnectionManager';

// Lazy initialization to avoid circular dependencies
let apiInstance: any = null;
const getApi = () => {
  if (!apiInstance) {
    const connectionManager = getAPIConnectionManager();
    apiInstance = connectionManager.getApiInstance();
  }
  return apiInstance;
};

// Export api getter for backward compatibility
export const api = new Proxy({} as any, {
  get: (target, prop) => {
    return getApi()[prop];
  },
});

export { getAPIConnectionManager };

/**
 * API Service Class
 * Refactored from object literal to class for better TypeScript support
 * Using a class provides better type inference and matches the pattern used by other services.
 * Root Cause Fix: TypeScript struggles with very large object literals (1700+ lines, 100+ methods).
 * Using a class provides better type inference and matches the pattern used by other services.
 */
class APIService {
  // Articles
  async getArticles(params: any = {}, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      // Convert page to offset for backend API
      const requestParams: any = { ...params };

      // Map pagination: frontend uses 'page', backend uses 'offset'
      if (params.page !== undefined && params.limit !== undefined) {
        requestParams.offset = (params.page - 1) * params.limit;
        // Remove page from params (backend doesn't understand it)
        delete requestParams.page;
      }

      // Don't set default hours - let the API return all articles by default
      // Only include hours if explicitly provided
      if (params.hours !== undefined) {
        requestParams.hours = params.hours;
      }
      // Otherwise, don't include hours parameter so API returns all articles
      const response = await getApi().get(
        `/api/v4/${domainKey}/articles`,
        { params: requestParams },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getArticle(id: string, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/articles/${id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async deleteArticle(id: string | number, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(`/api/v4/${domainKey}/articles/${id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to delete article:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async deleteArticlesBulk(articleIds: (string | number)[], domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(`/api/v4/${domainKey}/articles`, {
        data: articleIds,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to bulk delete articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async analyzeArticles(params: {
    source?: string;
    limit?: number;
    domains?: string;
    sample_size?: number;
  }): Promise<any> {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/articles/analyze', {
        params,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to analyze articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // RSS Feeds
  async getRSSFeeds(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const url = `/api/v4/${domainKey}/rss_feeds`;
      console.log('🔍 RSS Feeds API call:', url, params);
      const response = await getApi().get(url, {
        params,
      });
      console.log('🔍 RSS Feeds API response:', response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch RSS feeds:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async updateRSSFeeds(domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/rss_feeds/collect_now`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update RSS feeds:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // RSS Feed Management Methods
  async createRSSFeed(feedData: any, domain?: string) {
    try {
      const response = await getApi().post('/api/v4/rss_feeds', feedData);
      return response.data;
    } catch (error) {
      console.error('Failed to create RSS feed:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async updateRSSFeed(feedId: number, feedData: any, domain?: string) {
    try {
      const response = await getApi().put(`/api/v4/rss_feeds/${feedId}`, feedData);
      return response.data;
    } catch (error) {
      console.error('Failed to update RSS feed:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async deleteRSSFeed(feedId: number, domain?: string) {
    try {
      const response = await getApi().delete(`/api/v4/rss_feeds/${feedId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to delete RSS feed:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async refreshRSSFeed(feedId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/rss_feeds/collect_now`,
        { feed_id: feedId },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to refresh RSS feed:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getRSSCategories(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/rss_feeds`, {
        params: { categories_only: true },
      });
      // Extract unique categories from feeds
      const feeds = response.data?.data?.feeds || [];
      const categories = Array.from(
        new Set(feeds.map((feed: any) => feed.category).filter(Boolean)),
      );
      return {
        success: true,
        data: { categories },
      };
    } catch (error) {
      console.error('Failed to get RSS categories:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // RSS Feeds namespace for backward compatibility
  get rssFeeds(): {
    getFeeds: (params?: any, domain?: string) => Promise<any>;
    createFeed: (feedData: any, domain?: string) => Promise<any>;
    updateFeed: (feedId: number, feedData: any, domain?: string) => Promise<any>;
    deleteFeed: (feedId: number, domain?: string) => Promise<any>;
    refreshFeed: (feedId: number, domain?: string) => Promise<any>;
    getCategories: (domain?: string) => Promise<any>;
    } {
    return {
      getFeeds: (params?: any, domain?: string) =>
        this.getRSSFeeds(params, domain),
      createFeed: (feedData: any, domain?: string) =>
        this.createRSSFeed(feedData, domain),
      updateFeed: (feedId: number, feedData: any, domain?: string) =>
        this.updateRSSFeed(feedId, feedData, domain),
      deleteFeed: (feedId: number, domain?: string) =>
        this.deleteRSSFeed(feedId, domain),
      refreshFeed: (feedId: number, domain?: string) =>
        this.refreshRSSFeed(feedId, domain),
      getCategories: (domain?: string) => this.getRSSCategories(domain),
    };
  }

  // Storylines
  async getStorylines(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      // Map frontend params to API params
      const apiParams: any = {};

      // Map pagination: frontend uses 'page', backend uses 'offset'
      if (params.page !== undefined && params.limit !== undefined) {
        apiParams.offset = (params.page - 1) * params.limit;
        apiParams.limit = params.limit;
      } else if (params.page_size) {
        apiParams.limit = params.page_size;
      } else if (params.limit) {
        apiParams.limit = params.limit;
      }

      if (params.status) apiParams.status = params.status;
      // Note: search, category, sort are not yet supported by the API endpoint

      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines`,
        { params: apiParams },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storylines:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getStoryline(id: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/${id}`,
      );
      return response.data;
    } catch (error: any) {
      console.error('Failed to fetch storyline:', error);

      // Extract detailed error information
      let errorMessage = 'Unknown error';
      let statusCode = null;

      if (error.response) {
        // Server responded with error status
        statusCode = error.response.status;
        errorMessage = error.response.data?.detail || error.response.data?.message || `HTTP ${statusCode}`;
      } else if (error.request) {
        // Request was made but no response received
        errorMessage = 'No response from server. The API may be down or unreachable.';
      } else {
        // Error in setting up the request
        errorMessage = error.message || 'Unknown error';
      }

      return {
        success: false,
        error: errorMessage,
        statusCode,
      };
    }
  }

  async getStorylineTimeline(id: string | number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/${id}/timeline`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch storyline timeline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async createStoryline(storylineData: {
    title: string;
    description?: string;
    status?: string;
  }, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines`,
        storylineData,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to create storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async updateStoryline(
    id: string | number,
    data: { title: string; description?: string; status?: string },
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().put(
        `/api/v4/${domainKey}/storylines/${id}`,
        data,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async deleteStoryline(id: string | number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(
        `/api/v4/${domainKey}/storylines/${id}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to delete storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // AI Storyline Discovery
  async discoverStorylines(params: {
    hours?: number;
    save?: boolean;
    minSimilarity?: number;
    minArticles?: number;
  } = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines/discover`,
        params,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to discover storylines:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getBreakingNews(hours: number = 24, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/breaking_news`,
        { params: { hours } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get breaking news:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Storyline Comparison & Evolution
  async compareStorylines(domain?: string, minSimilarity: number = 0.4) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/compare`,
        { params: { min_similarity: minSimilarity } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to compare storylines:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getStorylineEvolution(hours: number = 168, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/evolution`,
        { params: { hours } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get storyline evolution:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async checkStorylineMerge(
    storylineId1: string | number,
    storylineId2: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/merge_check`,
        {
          params: {
            storyline_id_1: storylineId1,
            storyline_id_2: storylineId2,
          },
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to check storyline merge:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Storyline Consolidation & Hierarchy
  async getConsolidationStatus() {
    try {
      const response = await getApi().get(
        '/api/v4/storylines/consolidation/status',
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get consolidation status:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async runConsolidation(domain?: string) {
    try {
      if (domain) {
        const response = await getApi().post(
          `/api/v4/${domain}/storylines/consolidation/run`,
        );
        return response.data;
      } else {
        const response = await getApi().post(
          '/api/v4/storylines/consolidation/run',
        );
        return response.data;
      }
    } catch (error) {
      console.error('Failed to run consolidation:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getStorylineHierarchy(domain?: string, megaOnly: boolean = false) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/hierarchy`,
        { params: { mega_only: megaOnly } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get storyline hierarchy:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getMegaStorylines(limit: number = 20, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/mega`,
        { params: { limit } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get mega storylines:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async mergeStorylines(
    primaryId: string | number,
    secondaryId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines/merge/${primaryId}/${secondaryId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to merge storylines:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getRelatedStorylines(
    storylineId: string | number,
    limit: number = 10,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/${storylineId}/related`,
        { params: { limit } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get related storylines:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Intelligence Analysis - RAG, Quality, Anomaly, Impact
  async getRAGContext(storylineId: number, query?: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/intelligence/rag/${storylineId}`,
        { params: query ? { query } : {} },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get RAG context:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async queryRAG(query: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/intelligence/rag/query`,
        { query },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to query RAG:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getStorylineQuality(storylineId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/intelligence/quality/${storylineId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get storyline quality:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getBatchQuality(storylineIds: number[], domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/intelligence/quality/batch`,
        { storyline_ids: storylineIds },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get batch quality:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getAnomalies(domain?: string, limit: number = 20) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/intelligence/anomalies`,
        { params: { limit } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get anomalies:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async watchAnomaly(anomalyId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/intelligence/anomalies/watch`,
        { anomaly_id: anomalyId },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to watch anomaly:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getStorylineImpact(storylineId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/intelligence/impact/${storylineId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get storyline impact:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTrendingImpact(domain?: string, limit: number = 10) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/intelligence/impact/trending`,
        { params: { limit } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get trending impact:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getIntelligenceDashboard(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/intelligence/dashboard`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get intelligence dashboard:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Content Analysis - Topics
  async getTopics(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics`,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTopicCategoriesStats(domain?: string) {
    try {
      // Backend route is global, not domain-specific
      const response = await getApi().get(
        '/api/v4/topics/categories/stats',
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic categories stats:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTopic(topicName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/${encodeURIComponent(
          topicName,
        )}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async updateTopic(
    topicName: string,
    data: {
      description?: string;
      category?: string;
      keywords?: string[];
    },
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().put(
        `/api/v4/${domainKey}/content_analysis/topics/${encodeURIComponent(
          topicName,
        )}`,
        data,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update topic:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTopicWordCloud(topicName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/word_cloud`,
        { params: { topic_name: topicName } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic word cloud:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Get word cloud for all topics (not topic-specific)
  async getWordCloud(hours: number = 24, limit: number = 50, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/word_cloud`,
        { params: { time_period_hours: hours, limit, min_frequency: 1 } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch word cloud:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Get big picture (accepts timePeriod parameter)
  async getBigPicture(timePeriod: number = 24, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/big_picture`,
        { params: { hours: timePeriod } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch big picture:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Get article topics (for ArticleTopics component)
  async getArticleTopics(articleId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/articles/${articleId}/topics`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch article topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTopicBigPicture(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/big_picture`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic big picture:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTrendingTopics(timePeriod: number = 24, limit: number = 20, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/trending`,
        { params: { hours: timePeriod, limit } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch trending topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Get articles for a specific topic (cluster_name)
  async getTopicArticles(clusterName: string, limit: number = 20, offset: number = 0, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/${encodeURIComponent(clusterName)}/articles`,
        { params: { limit, offset } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Get summary for a specific topic (cluster_name)
  async getTopicSummary(clusterName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/content_analysis/topics/${encodeURIComponent(clusterName)}/summary`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topic summary:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Cluster articles (alias for clusterTopics)
  async clusterArticles(params: any = {}, domain?: string) {
    return this.clusterTopics(params, domain);
  }

  // Convert topic to storyline
  async convertTopicToStoryline(clusterName: string, storylineTitle?: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/content_analysis/topics/${encodeURIComponent(clusterName)}/convert_to_storyline`,
        { storyline_title: storylineTitle },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to convert topic to storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async clusterTopics(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const requestBody: any = { limit: params.limit || 100 };

      // Add time_period_hours if provided
      if (params.time_period_hours !== undefined) {
        requestBody.time_period_hours = params.time_period_hours;
      }

      const response = await getApi().post(
        `/api/v4/${domainKey}/content_analysis/topics/cluster`,
        requestBody,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to cluster topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async mergeTopics(
    primaryTopic: string,
    secondaryTopic: string,
    domain?: string,
  ) {
    try {
      // Backend route is global, not domain-specific
      const response = await getApi().post(
        '/api/v4/topics/merge',
        {
          topic_ids: [primaryTopic, secondaryTopic], // Backend expects topic_ids array
          keep_primary: true,
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to merge topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Storyline Automation
  async getStorylineAutomationSettings(
    storylineId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/${storylineId}/automation/settings`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get automation settings:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async updateStorylineAutomationSettings(
    storylineId: string | number,
    settings: any,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().put(
        `/api/v4/${domainKey}/storylines/${storylineId}/automation/settings`,
        settings,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to update automation settings:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async triggerStorylineDiscovery(
    storylineId: string | number,
    forceRefresh: boolean = false,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines/${storylineId}/automation/discover?force_refresh=${forceRefresh}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to trigger discovery:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getAutomationSuggestions(
    storylineId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/${storylineId}/automation/suggestions`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get automation suggestions:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async approveSuggestion(
    storylineId: string | number,
    suggestionId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines/${storylineId}/automation/suggestions/${suggestionId}/approve`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to approve suggestion:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async rejectSuggestion(
    storylineId: string | number,
    suggestionId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines/${storylineId}/automation/suggestions/${suggestionId}/reject`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to reject suggestion:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Storyline Analysis
  async analyzeStoryline(id: string | number, domain?: string) {
    const domainKey = domain || getCurrentDomain();
    console.log(`[analyzeStoryline] Starting analysis for storyline ${id} in domain ${domainKey}`);
    
    // Try the double-prefix route directly (we know this one works)
    try {
      console.log(`[analyzeStoryline] Trying route: /api/v4/api/v4/${domainKey}/storylines/${id}/analyze`);
      const response = await getApi().post(
        `/api/v4/api/v4/${domainKey}/storylines/${id}/analyze`,
      );
      console.log('[analyzeStoryline] Success:', response?.data);
      return response?.data || { success: true, message: 'Analysis started' };
    } catch (error: any) {
      console.error('[analyzeStoryline] Double-prefix route failed:', error);
      console.error('[analyzeStoryline] Error details:', {
        status: error?.response?.status,
        statusText: error?.response?.statusText,
        data: error?.response?.data,
        message: error?.message,
        code: error?.code
      });
      
      // If double-prefix fails, try single-prefix as fallback
      if (error?.response?.status === 404 || error?.code === 'ERR_BAD_REQUEST') {
        try {
          console.log(`[analyzeStoryline] Trying fallback route: /api/v4/${domainKey}/storylines/${id}/analyze`);
          const fallbackResponse = await getApi().post(
            `/api/v4/${domainKey}/storylines/${id}/analyze`,
          );
          console.log('[analyzeStoryline] Fallback success:', fallbackResponse?.data);
          return fallbackResponse?.data || { success: true, message: 'Analysis started' };
        } catch (fallbackError: any) {
          console.error('[analyzeStoryline] Fallback also failed:', fallbackError);
          const errorMessage = fallbackError?.response?.data?.detail || fallbackError?.message || 'Failed to start analysis';
          return { success: false, error: errorMessage };
        }
      }
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to start analysis';
      return { success: false, error: errorMessage };
    }
  }

  // Storyline Articles Management
  async getAvailableArticles(
    storylineId: string | number,
    params: any = {},
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/storylines/${storylineId}/available_articles`,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get available articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async addArticleToStoryline(
    storylineId: string | number,
    articleId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/storylines/${storylineId}/articles/${articleId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to add article to storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async removeArticleFromStoryline(
    storylineId: string | number,
    articleId: string | number,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(
        `/api/v4/${domainKey}/storylines/${storylineId}/articles/${articleId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to remove article from storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // System Monitoring
  async getHealth() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/health');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch health:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getMonitoringDashboard() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/status');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch monitoring dashboard:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getPipelineStatus() {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/pipeline_status');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch pipeline status:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Article Deduplication
  async getDuplicateStats() {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      console.error('Failed to get duplicate stats:', error);
      return { success: false, error: (error as any).message };
    }
  }

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
      console.error('Failed to detect duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getURLDuplicates() {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/url');
      return response.data;
    } catch (error) {
      console.error('Failed to get URL duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getContentDuplicates() {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/content');
      return response.data;
    } catch (error) {
      console.error('Failed to get content duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getSimilarArticles(articleId: number, threshold: number = 0.8) {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/similar', {
        params: { article_id: articleId, threshold },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get similar articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async autoMergeDuplicates(dryRun: boolean = true) {
    try {
      const response = await getApi().post(
        '/api/v4/articles/duplicates/auto_merge',
        { dry_run: dryRun },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to auto-merge duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async preventDuplicates() {
    try {
      const response = await getApi().post('/api/v4/articles/duplicates/prevent');
      return response.data;
    } catch (error) {
      console.error('Failed to prevent duplicates:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async analyzeSimilarity(articleId1: number, articleId2: number) {
    try {
      const response = await getApi().post(
        '/api/v4/articles/duplicates/analyze_similarity',
        {
          article_id_1: articleId1,
          article_id_2: articleId2,
        },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to analyze similarity:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Content Synthesis
  async synthesizeStoryline(
    storylineId: string | number,
    depth: string = 'full',
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/synthesis/storyline/${storylineId}`,
        { depth },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to synthesize storyline:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getSynthesizedContent(
    storylineId: string | number,
    depth: string = 'full',
    format: 'markdown' | 'html' = 'markdown',
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/synthesis/storyline/${storylineId}/${format}`,
        { params: { depth } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get synthesized content:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async bulkSynthesizeStorylines(
    storylineIds: number[],
    depth?: string,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/synthesis/bulk`,
        { storyline_ids: storylineIds, depth },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to bulk synthesize:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async checkSynthesisTaskStatus(taskId: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/synthesis/tasks/${taskId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to check task status:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Legacy v3 API methods (merged from enhancedApiService) - for backward compatibility
  async getSystemHealth(): Promise<any> {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/health');
      return response.data;
    } catch (error) {
      console.error('Failed to get system health:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getSystemMetrics(): Promise<any> {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/metrics');
      return response.data;
    } catch (error) {
      console.error('Failed to get system metrics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getDatabaseMetrics(): Promise<any> {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/dashboard');
      return response.data;
    } catch (error) {
      console.error('Failed to get database metrics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Log Statistics (using system metrics as proxy)
  async getLogStatistics(days: number = 7): Promise<any> {
    try {
      // Use the new log statistics endpoint
      const response = await getApi().get('/api/v4/system_monitoring/logs/stats', {
        params: {
          days: days,
        },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get log statistics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Realtime Logs - using dedicated endpoint
  async getRealtimeLogs(limit: number = 50): Promise<any> {
    try {
      // Use the new realtime logs endpoint
      const response = await getApi().get('/api/v4/system_monitoring/logs/realtime', {
        params: {
          limit: limit,
        },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to get realtime logs:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Deduplication Statistics
  async getDeduplicationStats(): Promise<any> {
    try {
      const response = await getApi().get('/api/v4/articles/duplicates/stats');
      return response.data;
    } catch (error) {
      console.error('Failed to get deduplication stats:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // API Status (comprehensive system status)
  async getAPIStatus(): Promise<any> {
    try {
      const response = await getApi().get('/api/v4/system_monitoring/status');
      return response.data;
    } catch (error) {
      console.error('Failed to get API status:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Topic Management Methods (for TopicManagement.js)
  async getManagedTopics(params: any = {}, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/v4/${domainKey}/topics`,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch managed topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getTopicsNeedingReview(threshold: number = 0.6, limit: number = 50): Promise<any> {
    try {
      const response = await getApi().get(
        '/api/v4/topics/needing_review',
        { params: { threshold, limit } },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch topics needing review:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getManagedTopic(topicId: number): Promise<any> {
    try {
      const response = await getApi().get(
        `/api/v4/topics/${topicId}`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch managed topic:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async getManagedTopicArticles(topicId: number, params: any = {}): Promise<any> {
    try {
      const response = await getApi().get(
        `/api/v4/topics/${topicId}/articles`,
        { params },
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch managed topic articles:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async processArticleTopics(articleId: number): Promise<any> {
    try {
      const response = await getApi().post(
        `/api/v4/articles/${articleId}/process_topics`,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to process article topics:', error);
      return { success: false, error: (error as any).message };
    }
  }

  async submitTopicFeedback(
    assignmentId: number,
    feedback: { is_correct: boolean; feedback_notes?: string; validated_by?: string },
  ): Promise<any> {
    try {
      const response = await getApi().post(
        `/api/v4/assignments/${assignmentId}/feedback`,
        feedback,
      );
      return response.data;
    } catch (error) {
      console.error('Failed to submit topic feedback:', error);
      return { success: false, error: (error as any).message };
    }
  }

  // Alias for backward compatibility
  getCategoryStats = this.getTopicCategoriesStats;

  // Finance Domain - Market Trends
  async getMarketTrends(params: any = {}, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/finance/market-trends`, {
        params,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch market trends:', error);
      // Return a graceful fallback instead of throwing
      return {
        success: false,
        error: (error as any).message || 'Market trends API not yet implemented',
        data: null,
      };
    }
  }

  // Finance Domain - Market Patterns
  async getMarketPatterns(params: any = {}, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/finance/market-patterns`, {
        params,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch market patterns:', error);
      return {
        success: false,
        error: (error as any).message || 'Market patterns API not yet implemented',
        data: null,
      };
    }
  }

  // Finance Domain - Corporate Announcements
  async getCorporateAnnouncements(params: any = {}, domain?: string): Promise<any> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/finance/corporate-announcements`, {
        params,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch corporate announcements:', error);
      return {
        success: false,
        error: (error as any).message || 'Corporate announcements API not yet implemented',
        data: null,
      };
    }
  }

  // Pipeline Management
  async triggerPipeline(): Promise<any> {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/pipeline/trigger');
      return response.data;
    } catch (error) {
      console.error('Failed to trigger pipeline:', error);
      return {
        success: false,
        error: (error as any).message || 'Pipeline trigger API not yet implemented',
      };
    }
  }

  // AI Analysis
  async runAIAnalysis(): Promise<any> {
    try {
      const response = await getApi().post('/api/v4/system_monitoring/ai-analysis/run');
      return response.data;
    } catch (error) {
      console.error('Failed to run AI analysis:', error);
      return {
        success: false,
        error: (error as any).message || 'AI analysis API not yet implemented',
      };
    }
  }
}

// Export singleton instance with error handling
// ROOT CAUSE FIX: Ensure instance is always created, even if there are initialization errors
let apiServiceInstance: APIService | null = null;

const getApiService = (): APIService => {
  if (!apiServiceInstance) {
    try {
      apiServiceInstance = new APIService();
    } catch (error) {
      console.error('Failed to create APIService instance:', error);
      // Create a minimal fallback instance to prevent undefined errors
      apiServiceInstance = new APIService();
    }
  }
  return apiServiceInstance;
};

// Create instance immediately, but use getter for safety
const apiService = getApiService();

// CRITICAL: Export in a way that webpack can reliably resolve
// Export default first (most reliable)
export default apiService;

// Export named exports - ensure apiService is always available
export { apiService, getApiService };

// Also export as a property for webpack compatibility
// This helps with webpack's module resolution
if (typeof module !== 'undefined' && module.exports) {
  module.exports = apiService;
  module.exports.default = apiService;
  module.exports.apiService = apiService;
  module.exports.getApiService = getApiService;
}

