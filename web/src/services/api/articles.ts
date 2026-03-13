/**
 * Articles API — getArticles, getArticle, delete, analyze, events.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

export const articlesApi = {
  async getArticles(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const requestParams: any = { ...params };
      if (params.page !== undefined && params.limit !== undefined) {
        requestParams.offset = (params.page - 1) * params.limit;
        delete requestParams.page;
      }
      if (params.hours !== undefined) requestParams.hours = params.hours;
      const response = await getApi().get(`/api/${domainKey}/articles`, { params: requestParams });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch articles', error as Error);
      return { success: false, error: (error as any).message };
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
      const response = await getApi().delete(`/api/${domainKey}/articles/${id}`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to delete article', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async deleteArticlesBulk(articleIds: (string | number)[], domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(`/api/${domainKey}/articles`, { data: articleIds });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to bulk delete articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async analyzeArticles(params: { source?: string; limit?: number; domains?: string; sample_size?: number }) {
    try {
      const response = await getApi().get('/api/system_monitoring/articles/analyze', { params });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to analyze articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getArticleEvents(articleId: number | string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/events`, { params: { article_id: articleId } });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch article events', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
