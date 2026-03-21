/**
 * Intelligence hub API — RAG, quality, anomalies, impact, synthesis, events.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

export const intelligenceApi = {
  async getRAGContext(storylineId: number, query?: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/rag/${storylineId}`,
        { params: query ? { query } : {} }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get RAG context', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async queryRAG(query: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/rag/query`,
        { query }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to query RAG', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineQuality(storylineId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/quality/${storylineId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get storyline quality', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getBatchQuality(storylineIds: number[], domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/quality/batch`,
        { storyline_ids: storylineIds }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get batch quality', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getAnomalies(domain?: string, limit: number = 20) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/anomalies`,
        { params: { limit } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get anomalies', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async watchAnomaly(anomalyId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/anomalies/watch`,
        { anomaly_id: anomalyId }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to watch anomaly', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineImpact(storylineId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/impact/${storylineId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get storyline impact', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTrendingImpact(domain?: string, limit: number = 10) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/impact/trending`,
        { params: { limit } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get trending impact', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getIntelligenceDashboard(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/dashboard`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get intelligence dashboard', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getEventStorylineClaimConsistency(
    params: { limit_events?: number; min_claim_confidence?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/consistency`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get consistency assembly', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getParticipantPositionDeltas(
    params: { days?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/participant_deltas`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get participant deltas', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getCausalChains(
    params: { days?: number; min_strength?: number; limit?: number } = {}
  ) {
    try {
      const response = await getApi().get('/api/intelligence/causal_chains', {
        params,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get causal chains', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getNarrativeDivergenceMap(
    eventId: number,
    params: { min_contexts_per_cluster?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/narrative_divergence/${eventId}`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get narrative divergence map', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async runWatchlistThemeBridge(
    params: { create_alerts?: boolean; max_items?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/watchlist_theme_bridge`,
        null,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to run watchlist-theme bridge', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async runDocumentIntelligenceIntegration(
    params: { days?: number; persist_links?: boolean; limit?: number } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/document_integration`,
        null,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to run document intelligence integration',
        error as Error
      );
      return { success: false, error: (error as any).message };
    }
  },

  async getDomainEvents(
    params: {
      limit?: number;
      offset?: number;
      event_type?: string;
      ongoing_only?: boolean;
    } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/events`, {
        params,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch domain events', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async synthesizeStoryline(
    storylineId: string | number,
    depth: string = 'full',
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/synthesis/storyline/${storylineId}`,
        { depth }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to synthesize storyline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getSynthesizedContent(
    storylineId: string | number,
    depth: string = 'full',
    format: 'markdown' | 'html' = 'markdown',
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/synthesis/storyline/${storylineId}/${format}`,
        { params: { depth } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get synthesized content', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async bulkSynthesizeStorylines(
    storylineIds: number[],
    depth?: string,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(`/api/${domainKey}/synthesis/bulk`, {
        storyline_ids: storylineIds,
        depth,
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to bulk synthesize', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async checkSynthesisTaskStatus(taskId: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/synthesis/tasks/${taskId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to check task status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getRecentDigests(count: number = 5, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/digests`,
        { params: { limit: count } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get recent digests', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async generateWeeklyDigest(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/digests/weekly`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to generate weekly digest', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async generateDailyBriefing(date?: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/briefings/daily`,
        { date }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to generate daily briefing', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getTopicCloud(days: number = 7, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/content_analysis/topics/trending`,
        { params: { hours: days * 24, limit: 50 } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get topic cloud', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStoryDossier(
    storyId: string,
    includeRag: boolean = false,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/rag/query`,
        {
          query: `Generate a comprehensive dossier for story: ${storyId}`,
          include_rag: includeRag,
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get story dossier', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  /** Report assembly: lead storylines (5W1H + key_actors), investigations, recent events, daily brief. */
  async getReport(domain?: string, leadLimit: number = 10) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get<{
        success: boolean;
        data: import('../../types').ReportPayload | null;
        message: string | null;
      }>(`/api/${domainKey}/report`, { params: { lead_limit: leadLimit } });
      if (response.data.success && response.data.data) {
        return { success: true as const, data: response.data.data };
      }
      return {
        success: false as const,
        data: null,
        message: response.data.message || 'No data',
      };
    } catch (error) {
      Logger.apiError('Failed to get report', error as Error);
      return {
        success: false as const,
        data: null,
        message: (error as Error).message,
      };
    }
  },

  /** Briefing feed: articles and storylines reordered (not interested excluded, sports/celebrity demoted). */
  async getBriefingFeed(
    domain?: string,
    articlesLimit: number = 10,
    storylinesLimit: number = 6
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/intelligence/briefing_feed`,
        {
          params: {
            articles_limit: articlesLimit,
            storylines_limit: storylinesLimit,
          },
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get briefing feed', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  /** Submit usefulness (1-5) or not interested for an article, storyline, or whole briefing. */
  async submitContentFeedback(
    payload: {
      item_type: 'article' | 'storyline' | 'briefing';
      item_id?: number;
      rating?: number;
      not_interested?: boolean;
    },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/intelligence/feedback`,
        payload
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to submit content feedback', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
