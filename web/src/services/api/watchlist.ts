/**
 * Watchlist & monitoring API (v5.0).
 */
import { getApi } from './client';
import Logger from '../../utils/logger';

export const watchlistApi = {
  async getWatchlist() {
    try {
      const response = await getApi().get('/api/watchlist');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch watchlist:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async addToWatchlist(
    storylineId: number,
    options: {
      user_label?: string;
      notes?: string;
      alert_on_reactivation?: boolean;
      weekly_digest?: boolean;
    } = {}
  ) {
    try {
      const response = await getApi().post(
        `/api/watchlist/${storylineId}`,
        options
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to add to watchlist:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async removeFromWatchlist(storylineId: number) {
    try {
      const response = await getApi().delete(`/api/watchlist/${storylineId}`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to remove from watchlist:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async getWatchlistAlerts(unreadOnly = false, limit = 50) {
    try {
      const response = await getApi().get('/api/watchlist/alerts', {
        params: { unread_only: unreadOnly, limit },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch watchlist alerts:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async markAlertRead(alertId: number) {
    try {
      const response = await getApi().post(
        `/api/watchlist/alerts/${alertId}/read`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to mark alert read:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async markAllAlertsRead() {
    try {
      const response = await getApi().post('/api/watchlist/alerts/read-all');
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to mark all alerts read:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async getActivityFeed(limit = 30) {
    try {
      const response = await getApi().get('/api/monitoring/activity-feed', {
        params: { limit },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch activity feed:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async getDormantAlerts(days = 30) {
    try {
      const response = await getApi().get('/api/monitoring/dormant-alerts', {
        params: { days },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch dormant alerts:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async getCoverageGaps(days = 7) {
    try {
      const response = await getApi().get('/api/monitoring/coverage-gaps', {
        params: { days },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch coverage gaps:', error);
      return { success: false, error: (error as any).message };
    }
  },

  async getCrossDomainConnections() {
    try {
      const response = await getApi().get(
        '/api/monitoring/cross-domain-connections'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch cross-domain connections:', error);
      return { success: false, error: (error as any).message };
    }
  },
};
