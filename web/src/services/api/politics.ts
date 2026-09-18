/**
 * Politics API — congressional trading data from Quiver Quantitative.
 */
import { getApi } from './client';
import Logger from '../../utils/logger';

export const politicsApi = {
  async getCongressTrades(params: {
    days?: number;
    politician?: string;
    ticker?: string;
    chamber?: string;
    party?: string;
    transaction_type?: string;
    min_amount?: string;
    limit?: number;
    offset?: number;
  } = {}) {
    try {
      const response = await getApi().get('/api/politics/congress/trades', {
        params,
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch congress trades', error as Error);
      return {
        success: false,
        error: `politics/congress/trades: ${(error as Error).message}`,
      };
    }
  },

  async getCongressTradeSummary(days = 30) {
    try {
      const response = await getApi().get('/api/politics/congress/trades/summary', {
        params: { days },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch congress trade summary', error as Error);
      return {
        success: false,
        error: `politics/congress/trades/summary: ${(error as Error).message}`,
      };
    }
  },

  async getPoliticianTrades(politicianName: string, days = 365, limit = 200) {
    try {
      const response = await getApi().get(`/api/politics/congress/trades/politician/${encodeURIComponent(politicianName)}`, {
        params: { days, limit },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch politician trades', error as Error);
      return {
        success: false,
        error: `politics/congress/trades/politician: ${(error as Error).message}`,
      };
    }
  },

  async getTickerCongressActivity(ticker: string, days = 365, limit = 100) {
    try {
      const response = await getApi().get(`/api/politics/congress/trades/ticker/${ticker.toUpperCase()}`, {
        params: { days, limit },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch ticker congress activity', error as Error);
      return {
        success: false,
        error: `politics/congress/trades/ticker: ${(error as Error).message}`,
      };
    }
  },

  async getTopPoliticians(days = 30, limit = 20) {
    try {
      const response = await getApi().get('/api/politics/congress/politicians/top', {
        params: { days, limit },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch top politicians', error as Error);
      return {
        success: false,
        error: `politics/congress/politicians/top: ${(error as Error).message}`,
      };
    }
  },

  async getTopTickers(days = 30, limit = 20) {
    try {
      const response = await getApi().get('/api/politics/congress/tickers/top', {
        params: { days, limit },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch top tickers', error as Error);
      return {
        success: false,
        error: `politics/congress/tickers/top: ${(error as Error).message}`,
      };
    }
  },
};