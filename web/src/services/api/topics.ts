/**
 * Topics API — content analysis topics, word cloud, big picture, trending.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

export const topicsApi = {
  async getTopics(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicCategoriesStats(domain?: string) {
    try {
      const response = await getApi().get('/api/topics/categories/stats');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topic categories stats', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopic(topicName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/${encodeURIComponent(topicName)}`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topic', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async updateTopic(
    topicName: string,
    data: { description?: string; category?: string; keywords?: string[] },
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().put(
        `/api/${domainKey}/content_analysis/topics/${encodeURIComponent(topicName)}`,
        data,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to update topic', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicWordCloud(topicName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/word_cloud`,
        { params: { topic_name: topicName } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topic word cloud', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getWordCloud(hours: number = 24, limit: number = 50, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/word_cloud`,
        { params: { time_period_hours: hours, limit, min_frequency: 1 } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch word cloud', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getBannedTopics(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/banned`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch banned topics', error as Error);
      return { success: false, error: (error as any).message, data: [] };
    }
  },

  async banTopic(topicName: string, reason?: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/content_analysis/topics/banned`,
        { topic_name: topicName, reason },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to ban topic', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async unbanTopic(topicName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(
        `/api/${domainKey}/content_analysis/topics/banned/${encodeURIComponent(topicName)}`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to unban topic', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getBigPicture(timePeriod: number = 24, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/big_picture`,
        { params: { hours: timePeriod } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch big picture', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getArticleTopics(articleId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/articles/${articleId}/topics`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch article topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicBigPicture(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/big_picture`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topic big picture', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTrendingTopics(timePeriod: number = 24, limit: number = 20, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/trending`,
        { params: { hours: timePeriod, limit } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch trending topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicArticles(
    clusterName: string,
    limit: number = 20,
    offset: number = 0,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/${encodeURIComponent(clusterName)}/articles`,
        { params: { limit, offset } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topic articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicSummary(clusterName: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/${encodeURIComponent(clusterName)}/summary`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topic summary', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMergeSuggestions(
    minScore: number = 0.35,
    limit: number = 50,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/merge_suggestions`,
        { params: { min_score: minScore, limit } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch merge suggestions', error as Error);
      return { success: false, error: (error as any).message, data: { suggestions: [] } };
    }
  },

  async mergeClusters(
    primaryCluster: string,
    secondaryCluster: string,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/content_analysis/topics/merge_clusters`,
        { primary_cluster: primaryCluster, secondary_cluster: secondaryCluster },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to merge clusters', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async clusterTopics(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const requestBody: any = { limit: params.limit || 100 };
      if (params.time_period_hours !== undefined) {
        requestBody.time_period_hours = params.time_period_hours;
      }
      const response = await getApi().post(
        `/api/${domainKey}/content_analysis/topics/cluster`,
        requestBody,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to cluster topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async convertTopicToStoryline(
    clusterName: string,
    storylineTitle?: string,
    domain?: string,
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/content_analysis/topics/${encodeURIComponent(clusterName)}/convert_to_storyline`,
        { storyline_title: storylineTitle },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to convert topic to storyline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async mergeTopics(
    primaryTopic: string,
    secondaryTopic: string,
    domain?: string,
  ) {
    try {
      const response = await getApi().post('/api/topics/merge', {
        topic_ids: [primaryTopic, secondaryTopic],
        keep_primary: true,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to merge topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getManagedTopics(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/topics`, { params });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch managed topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicsNeedingReview(threshold: number = 0.6, limit: number = 50) {
    try {
      const response = await getApi().get(
        '/api/topics/needing_review',
        { params: { threshold, limit } },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch topics needing review', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getManagedTopic(topicId: number) {
    try {
      const response = await getApi().get(`/api/topics/${topicId}`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch managed topic', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getManagedTopicArticles(topicId: number, params: any = {}) {
    try {
      const response = await getApi().get(
        `/api/topics/${topicId}/articles`,
        { params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch managed topic articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async processArticleTopics(articleId: number) {
    try {
      const response = await getApi().post(
        `/api/articles/${articleId}/process_topics`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to process article topics', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async submitTopicFeedback(
    assignmentId: number,
    feedback: { is_correct: boolean; feedback_notes?: string; validated_by?: string },
  ) {
    try {
      const response = await getApi().post(
        `/api/assignments/${assignmentId}/feedback`,
        feedback,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to submit topic feedback', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
