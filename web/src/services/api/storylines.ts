/**
 * Storylines API — CRUD, timeline, narrative, discovery, consolidation, automation.
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';
import type { StorylineListResponse, StorylineDetail } from '../../types';

export interface GetStorylinesParams {
  page?: number;
  page_size?: number;
  limit?: number;
  status?: string;
}

export interface DomainStoryKindInfo {
  domain: string;
  story_kind: string;
  is_chemistry_kind: boolean;
  display_label: string;
  link_score_profile?: {
    relevance_weight?: number;
    semantic_weight?: number;
    keyword_weight?: number;
    quality_weight?: number;
    auto_approve_combined?: number;
    aggressive_membership?: boolean;
    allow_storyline_merge?: boolean;
  };
}

export const storylinesApi = {
  async getDomainStoryKind(
    domain?: string
  ): Promise<{ success: boolean; data?: DomainStoryKindInfo; message?: string }> {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get<{
        success: boolean;
        data?: DomainStoryKindInfo;
        message?: string;
      }>(`/api/${domainKey}/storylines/story_kind`, { timeout: 30000 });
      return response.data;
    } catch (e) {
      Logger.warn('getDomainStoryKind failed', e);
      return { success: false, message: String(e) };
    }
  },

  async getStorylines(
    params: GetStorylinesParams = {},
    domain?: string
  ): Promise<StorylineListResponse | { success: false; error: string }> {
    try {
      const domainKey = domain || getCurrentDomain();
      const apiParams: Record<string, number | string> = {};
      if (params.page !== undefined) apiParams.page = params.page;
      if (params.page_size !== undefined)
        apiParams.page_size = params.page_size;
      else if (params.limit !== undefined) apiParams.page_size = params.limit;
      if (params.status) apiParams.status = params.status;

      const response = await getApi().get<StorylineListResponse>(
        `/api/${domainKey}/storylines`,
        {
          params: {
            ...apiParams,
            include_top_entities: false,
          },
          timeout: 120000,
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch storylines', error as Error);
      return { success: false, error: (error as Error).message };
    }
  },

  async getStoryline(
    id: string,
    domain?: string
  ): Promise<
    | StorylineDetail
    | { success: false; error: string; statusCode?: number | null }
  > {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get<StorylineDetail>(
        `/api/${domainKey}/storylines/${id}`
      );
      return response.data;
    } catch (error: unknown) {
      Logger.apiError('Failed to fetch storyline', error as Error);
      let errorMessage = 'Unknown error';
      let statusCode: number | null = null;
      const err = error as {
        response?: {
          status: number;
          data?: { detail?: string; message?: string };
        };
        request?: unknown;
        message?: string;
      };
      if (err.response) {
        statusCode = err.response.status;
        errorMessage =
          err.response.data?.detail ||
          err.response.data?.message ||
          `HTTP ${statusCode}`;
      } else if (err.request) {
        errorMessage =
          'No response from server. The API may be down or unreachable.';
      } else {
        errorMessage = err.message || 'Unknown error';
      }
      return { success: false, error: errorMessage, statusCode };
    }
  },

  async getStorylineTimeline(id: string | number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${id}/timeline`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch storyline timeline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineAudit(id: string | number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get<{
        success: boolean;
        data?: Record<string, unknown>;
      }>(`/api/${domainKey}/storylines/${id}/audit`);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch storyline audit', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineNarrative(
    id: string | number,
    mode: 'chronological' | 'briefing' = 'chronological',
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${id}/narrative`,
        { params: { mode } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch storyline narrative', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  /**
   * Queue storyline refinement (RAG analysis, ~70B finisher, ~70B headline_refiner, timeline narrative). Workers drain the DB queue.
   */
  async enqueueStorylineRefinement(
    id: string | number,
    jobType:
      | 'comprehensive_rag'
      | 'narrative_finisher'
      | 'headline_refiner'
      | 'timeline_narrative_chronological'
      | 'timeline_narrative_briefing',
    domain?: string,
    priority: 'high' | 'medium' | 'low' = 'medium'
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/storylines/${id}/refinement_jobs`,
        { job_type: jobType, priority }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to enqueue storyline refinement', error as Error);
      return {
        success: false,
        error:
          (error as any)?.response?.data?.detail || (error as Error).message,
      };
    }
  },

  async createStoryline(
    storylineData: {
      title: string;
      description?: string;
      status?: string;
      article_ids?: number[];
    },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/storylines`,
        storylineData
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to create storyline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async updateStoryline(
    id: string | number,
    data: { title: string; description?: string; status?: string },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().put(
        `/api/${domainKey}/storylines/${id}`,
        data
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to update storyline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async deleteStoryline(id: string | number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(
        `/api/${domainKey}/storylines/${id}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to delete storyline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async discoverStorylines(
    params: {
      hours?: number;
      save?: boolean;
      minSimilarity?: number;
      minArticles?: number;
      /** Full historical backlog — use async kickoff (sync exceeds proxy/client timeouts). */
      async?: boolean;
    } = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const queryParams: Record<string, string | number | boolean> = {};
      if (params.hours != null) queryParams.hours = params.hours;
      if (params.save != null) queryParams.save = params.save;
      if (params.minSimilarity != null)
        queryParams.min_similarity = params.minSimilarity;
      if (params.minArticles != null)
        queryParams.min_cluster_size = params.minArticles;

      if (params.async) {
        const response = await getApi().post(
          `/api/${domainKey}/storylines/discover_async`,
          {},
          { params: queryParams, timeout: 30000 }
        );
        return { ...response.data, async: true };
      }

      // Bounded windows can still take 1–2 min (embeddings + cluster).
      // Keep under nginx proxy_read_timeout (120s) for general /api.
      const response = await getApi().post(
        `/api/${domainKey}/storylines/discover`,
        {},
        { params: queryParams, timeout: 110000 }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to discover storylines', error as Error);
      const msg = (error as any)?.message || String(error);
      const timedOut =
        /timeout/i.test(msg) || (error as any)?.code === 'ECONNABORTED';
      return {
        success: false,
        error: timedOut
          ? 'Discovery timed out. Use a shorter time window, or enable Full backlog (runs in the background).'
          : msg,
      };
    }
  },

  async getBreakingNews(hours: number = 24, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/breaking_news`,
        { params: { hours } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get breaking news', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async compareStorylines(domain?: string, minSimilarity: number = 0.4) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/compare`,
        { params: { min_similarity: minSimilarity } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to compare storylines', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineEvolution(hours: number = 168, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/evolution`,
        { params: { hours } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get storyline evolution', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async checkStorylineMerge(
    storylineId1: string | number,
    storylineId2: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/merge_check`,
        {
          params: {
            storyline_id_1: storylineId1,
            storyline_id_2: storylineId2,
          },
        }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to check storyline merge', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getConsolidationStatus() {
    try {
      const response = await getApi().get(
        '/api/storylines/consolidation/status'
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get consolidation status', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async runConsolidation(domain?: string) {
    try {
      const url = domain
        ? `/api/${domain}/storylines/consolidation/run`
        : '/api/storylines/consolidation/run';
      const response = await getApi().post(url);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to run consolidation', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineHierarchy(domain?: string, megaOnly: boolean = false) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/hierarchy`,
        { params: { mega_only: megaOnly } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get storyline hierarchy', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMegaStorylines(limit: number = 20, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(`/api/${domainKey}/storylines/mega`, {
        params: { limit },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get mega storylines', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async mergeStorylines(
    primaryId: string | number,
    secondaryId: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/storylines/merge/${primaryId}/${secondaryId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to merge storylines', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getRelatedStorylines(
    storylineId: string | number,
    limit: number = 10,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${storylineId}/related`,
        { params: { limit } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get related storylines', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getRelatedCrossDomainStorylines(
    storylineId: string | number,
    limit: number = 8,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${storylineId}/related_cross_domain`,
        { params: { limit } }
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to get cross-domain related storylines',
        error as Error
      );
      return { success: false, data: { storylines: [] }, error: (error as any).message };
    }
  },

  async analyzeStoryline(id: string | number, domain?: string) {
    const domainKey = domain || getCurrentDomain();
    try {
      const response = await getApi().post(
        `/api/${domainKey}/storylines/${id}/analyze`
      );
      return response?.data || { success: true, message: 'Analysis started' };
    } catch (error: any) {
      Logger.apiError('Failed to analyze storyline', error);
      if (
        error?.response?.status === 404 ||
        error?.code === 'ERR_BAD_REQUEST'
      ) {
        try {
          const fallback = await getApi().post(
            `/api/${domainKey}/storylines/${id}/analyze`
          );
          return (
            fallback?.data || { success: true, message: 'Analysis started' }
          );
        } catch {
          // fall through to error return
        }
      }
      const msg =
        error?.response?.data?.detail ||
        error?.message ||
        'Failed to start analysis';
      return { success: false, error: msg };
    }
  },

  async getAvailableArticles(
    storylineId: string | number,
    params: any = {},
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${storylineId}/available_articles`,
        { params }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get available articles', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async addArticleToStoryline(
    storylineId: string | number,
    articleId: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/storylines/${storylineId}/articles/${articleId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to add article to storyline', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async removeArticleFromStoryline(
    storylineId: string | number,
    articleId: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().delete(
        `/api/${domainKey}/storylines/${storylineId}/articles/${articleId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError(
        'Failed to remove article from storyline',
        error as Error
      );
      return { success: false, error: (error as any).message };
    }
  },

  async getStorylineAutomationSettings(
    storylineId: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${storylineId}/automation/settings`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get automation settings', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async updateStorylineAutomationSettings(
    storylineId: string | number,
    settings: any,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().put(
        `/api/${domainKey}/storylines/${storylineId}/automation/settings`,
        settings
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to update automation settings', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerStorylineDiscovery(
    storylineId: string | number,
    forceRefresh: boolean = false,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/storylines/${storylineId}/automation/discover?force_refresh=${forceRefresh}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger discovery', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getAutomationSuggestions(
    storylineId: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/${storylineId}/automation/suggestions`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get automation suggestions', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async approveSuggestion(
    storylineId: string | number,
    suggestionId: string | number,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/storylines/${storylineId}/automation/suggestions/${suggestionId}/approve`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to approve suggestion', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async rejectSuggestion(
    storylineId: string | number,
    suggestionId: string | number,
    reason?: string,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
      const response = await getApi().post(
        `/api/${domainKey}/storylines/${storylineId}/automation/suggestions/${suggestionId}/reject${params}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to reject suggestion', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getReviewQueue(
    options: {
      domain?: string;
      status?: string;
      limit?: number;
      offset?: number;
      storylineId?: number;
    } = {}
  ) {
    try {
      const domainKey = options.domain || getCurrentDomain();
      const params = new URLSearchParams();
      if (options.status) params.set('status', options.status);
      if (options.limit != null) params.set('limit', String(options.limit));
      if (options.offset != null) params.set('offset', String(options.offset));
      if (options.storylineId != null) {
        params.set('storyline_id', String(options.storylineId));
      }
      const qs = params.toString();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/review-queue${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get review queue', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getReviewQueueCount(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/review-queue/count`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get review queue count', error as Error);
      return { success: false, data: { count: 0 }, error: (error as any).message };
    }
  },

  async bulkApproveSuggestions(
    domain: string,
    body: { suggestion_ids?: number[]; all?: boolean; storyline_id?: number }
  ) {
    try {
      const response = await getApi().post(
        `/api/${domain}/storylines/review-queue/bulk-approve`,
        body
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to bulk approve', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async bulkRejectSuggestions(
    domain: string,
    body: {
      suggestion_ids?: number[];
      all?: boolean;
      storyline_id?: number;
      reason_code?: string;
      review_notes?: string;
    }
  ) {
    try {
      const response = await getApi().post(
        `/api/${domain}/storylines/review-queue/bulk-reject`,
        body
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to bulk reject', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async getMembershipActions(
    options: {
      domain?: string;
      status?: string;
      limit?: number;
      offset?: number;
    } = {}
  ) {
    try {
      const domainKey = options.domain || getCurrentDomain();
      const params = new URLSearchParams();
      if (options.status) params.set('status', options.status);
      if (options.limit != null) params.set('limit', String(options.limit));
      if (options.offset != null) params.set('offset', String(options.offset));
      const qs = params.toString();
      const response = await getApi().get(
        `/api/${domainKey}/storylines/membership-actions${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get membership actions', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async resolveMembershipAction(
    domain: string,
    actionId: number,
    approve: boolean
  ) {
    try {
      const response = await getApi().post(
        `/api/${domain}/storylines/membership-actions/${actionId}/resolve`,
        { approve }
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to resolve membership action', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async runMembershipReview(
    domain: string,
    options: { limit?: number; dry_run?: boolean } = {}
  ) {
    try {
      const params = new URLSearchParams();
      if (options.limit != null) params.set('limit', String(options.limit));
      if (options.dry_run != null) params.set('dry_run', String(options.dry_run));
      const qs = params.toString();
      const response = await getApi().post(
        `/api/${domain}/storylines/membership-review/run${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to run membership review', error as Error);
      return { success: false, error: (error as any).message };
    }
  },

  async triggerDomainAutomationDiscovery(
    domain: string,
    options: { force_refresh?: boolean; limit?: number } = {}
  ) {
    try {
      const params = new URLSearchParams();
      if (options.force_refresh) params.set('force_refresh', 'true');
      if (options.limit != null) params.set('limit', String(options.limit));
      const qs = params.toString();
      const response = await getApi().post(
        `/api/${domain}/storylines/automation/discover${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to trigger domain discovery', error as Error);
      return { success: false, error: (error as any).message };
    }
  },
};
