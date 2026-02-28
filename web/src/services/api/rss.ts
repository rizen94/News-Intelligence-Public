/**
 * RSS feeds API — list, create, update, delete, refresh, categories.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

export const rssApi = {
  async getRSSFeeds(params: any = {}, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      Logger.debug('RSS Feeds API call', { url: `/api/v4/${domainKey}/rss_feeds`, params });
      const response = await getApi().get(`/api/v4/${domainKey}/rss_feeds`, { params });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch RSS feeds', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async updateRSSFeeds(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/rss_feeds/collect_now`,
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to update RSS feeds', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async createRSSFeed(feedData: any, domain?: string) {
    try {
      const response = await getApi().post('/api/v4/rss_feeds', feedData);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to create RSS feed', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async updateRSSFeed(feedId: number, feedData: any, domain?: string) {
    try {
      const response = await getApi().put(`/api/v4/rss_feeds/${feedId}`, feedData);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to update RSS feed', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async deleteRSSFeed(feedId: number, domain?: string) {
    try {
      const response = await getApi().delete(`/api/v4/rss_feeds/${feedId}`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to delete RSS feed', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async refreshRSSFeed(feedId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/v4/${domainKey}/rss_feeds/collect_now`,
        { feed_id: feedId },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to refresh RSS feed', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getRSSCategories(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/v4/${domainKey}/rss_feeds`, {
        params: { categories_only: true },
      });
      const feeds = response.data?.data?.feeds || [];
      const categories = Array.from(
        new Set(feeds.map((f: any) => f.category).filter(Boolean)),
      );
      return { success: true, data: { categories } };
    } catch (error) {
      Logger.apiError('Failed to get RSS categories', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
