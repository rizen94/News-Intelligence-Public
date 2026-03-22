/**
 * Articles API — getArticles, getArticle, delete, analyze, events.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

const ARTICLE_LIST_PARAM_KEYS = [
  'search',
  'source_domain',
  'sort',
  'hours',
  'processing_status',
  'quality_first',
  'max_quality_tier',
  'sentiment',
  'min_quality_score',
  'max_quality_score',
] as const;

export const articlesApi = {
  async getArticles(params: Record<string, unknown> = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const limit = Number(params.limit) > 0 ? Number(params.limit) : 50;
      const page = Number(params.page) > 0 ? Number(params.page) : 1;
      const requestParams: Record<string, unknown> = {
        limit,
        offset: (page - 1) * limit,
      };

      for (const key of ARTICLE_LIST_PARAM_KEYS) {
        const v = params[key];
        if (v === undefined || v === null || v === '') continue;
        requestParams[key] = v;
      }

      if (params.unlinked === true) {
        requestParams.unlinked = true;
      }

      const response = await getApi().get(`/api/${domainKey}/articles`, {
        params: requestParams,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getArticleSources(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/articles/source_options`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch article sources', error as Error);
      return {
        success: false,
        data: { sources: [] as string[] },
        error: (error as any).message,
      };
    }
  },

  async getArticle(id: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/articles/${id}`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch article', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async deleteArticle(id: string | number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(
        `/api/${domainKey}/articles/${id}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to delete article', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async deleteArticlesBulk(articleIds: (string | number)[], domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(`/api/${domainKey}/articles`, {
        data: articleIds,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to bulk delete articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async analyzeArticles(params: {
    source?: string;
    limit?: number;
    domains?: string;
    sample_size?: number;
  }) {
    try {
      const response = await getApi().get(
        '/api/system_monitoring/articles/analyze',
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to analyze articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getArticleEvents(articleId: number | string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/events`, {
        params: { article_id: articleId },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch article events', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
