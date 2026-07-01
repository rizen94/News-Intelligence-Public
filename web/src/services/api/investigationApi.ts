/**
 * Investigation product API client (/api/investigation/*).
 */
import { getApi } from './client';
import { API_INVESTIGATION } from '../../config/apiRoutes';
import type {
  ExtractedClaim,
  NriContextIntelMention,
  NriEntityBridge,
  NriEntityClaimRow,
  NriHypothesis,
  NriHypothesisDetail,
  NriLoopRun,
  NriParkedCrossDomain,
  NriParkedResolution,
  NriResolutionStats,
  NriResolvedMention,
  NriSpineEntity,
} from './contextCentric';
import { getApiOrigin } from '../../config/apiConfig';

function apiPath(absolutePath: string): string {
  return absolutePath.startsWith('/') ? absolutePath : `/${absolutePath}`;
}

function investigationConfig(): { baseURL?: string } {
  const origin = getApiOrigin();
  return origin ? { baseURL: origin } : {};
}

function handleError(message: string, error: unknown): never {
  console.error(message, error);
  throw error;
}

export const investigationApi = {
  async getHealth(): Promise<Record<string, unknown>> {
    try {
      const response = await getApi().get<Record<string, unknown>>(
        apiPath(API_INVESTIGATION.health),
        investigationConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch investigation health', error);
    }
  },

  async getResolvedMentions(params?: {
    domain_key?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ success: boolean; items: NriResolvedMention[]; limit: number; offset: number }> {
    try {
      const response = await getApi().get<{
        success: boolean;
        items: NriResolvedMention[];
        limit: number;
        offset: number;
      }>(apiPath(API_INVESTIGATION.resolvedMentions), {
        ...investigationConfig(),
        params: params ?? {},
      });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch resolved mentions', error);
    }
  },

  async getParked(params?: {
    domain_key?: string;
    review_status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ success: boolean; items: NriParkedResolution[]; limit: number; offset: number }> {
    try {
      const response = await getApi().get<{
        success: boolean;
        items: NriParkedResolution[];
        limit: number;
        offset: number;
      }>(apiPath(API_INVESTIGATION.parked), { ...investigationConfig(), params: params ?? {} });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch parked mentions', error);
    }
  },

  async reviewParked(
    parkedId: number,
    body: { review_status: string; candidate_ftm_id?: string },
  ): Promise<Record<string, unknown>> {
    try {
      const response = await getApi().patch<Record<string, unknown>>(
        apiPath(API_INVESTIGATION.parkedReview(parkedId)),
        body,
        investigationConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to review parked mention', error);
    }
  },

  async getEntityBridge(
    entityProfileId: number,
  ): Promise<{ success: boolean; bridge: NriEntityBridge | null }> {
    try {
      const response = await getApi().get<{ success: boolean; bridge: NriEntityBridge | null }>(
        apiPath(API_INVESTIGATION.entityBridge(entityProfileId)),
        investigationConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity bridge', error);
    }
  },

  async getBridgeQaAudit(params?: {
    domain_key?: string;
    qa_status?: 'suspect' | 'mismatch';
    limit?: number;
    offset?: number;
  }): Promise<{ success: boolean; items: NriEntityBridge[]; total_filtered?: number }> {
    try {
      const response = await getApi().get<{
        success: boolean;
        items: NriEntityBridge[];
        total_filtered?: number;
      }>(apiPath(API_INVESTIGATION.bridgeQaAudit), {
        ...investigationConfig(),
        params: params ?? {},
      });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch bridge QA audit', error);
    }
  },

  async getEntityClaims(params: {
    entity_profile_id: number;
    context_id?: number;
    limit?: number;
  }): Promise<{ success: boolean; items: NriEntityClaimRow[] }> {
    try {
      const response = await getApi().get<{ success: boolean; items: NriEntityClaimRow[] }>(
        apiPath(API_INVESTIGATION.entityClaims),
        { ...investigationConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity claims', error);
    }
  },

  async getContextIntel(
    contextId: number,
    claimsLimit = 100,
  ): Promise<{
    success: boolean;
    context_id: number;
    mentions: NriContextIntelMention[];
    claims: ExtractedClaim[];
    status_counts: Record<string, number>;
  }> {
    try {
      const response = await getApi().get<{
        success: boolean;
        context_id: number;
        mentions: NriContextIntelMention[];
        claims: ExtractedClaim[];
        status_counts: Record<string, number>;
      }>(apiPath(API_INVESTIGATION.contextIntel(contextId)), {
        ...investigationConfig(),
        params: { claims_limit: claimsLimit },
      });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch context intel', error);
    }
  },

  async getResolutionStats(domainKey?: string): Promise<NriResolutionStats> {
    try {
      const response = await getApi().get<NriResolutionStats>(
        apiPath(API_INVESTIGATION.resolutionStats),
        { ...investigationConfig(), params: domainKey ? { domain_key: domainKey } : {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch resolution stats', error);
    }
  },

  async getLoopRuns(limit = 20): Promise<{ success?: boolean; items: NriLoopRun[] }> {
    try {
      const response = await getApi().get<{
        success?: boolean;
        items: Array<
          NriLoopRun & {
            killed?: number;
            demoted?: number;
            dormant?: number;
            added?: number;
            started_at?: string | null;
            finished_at?: string | null;
          }
        >;
      }>(apiPath(API_INVESTIGATION.loopRuns), {
        ...investigationConfig(),
        params: { limit },
      });
      const items = (response.data.items ?? []).map(row => ({
        id: row.id,
        iteration: row.iteration ?? null,
        shadow_branch: row.shadow_branch ?? null,
        killed_count: row.killed_count ?? row.killed ?? 0,
        demoted_count: row.demoted_count ?? row.demoted ?? 0,
        dormant_count: row.dormant_count ?? row.dormant ?? 0,
        added_count: row.added_count ?? row.added ?? 0,
        ran_at: row.ran_at ?? row.started_at ?? row.finished_at ?? null,
      }));
      return { success: response.data.success, items };
    } catch (error) {
      return handleError('Failed to fetch loop runs', error);
    }
  },

  async getFtMCacheStats(): Promise<{ success?: boolean; bridged_by_dataset?: Record<string, number> }> {
    try {
      const response = await getApi().get<{
        success?: boolean;
        bridged_by_dataset?: Record<string, number>;
      }>(apiPath(API_INVESTIGATION.ftmCacheStats), investigationConfig());
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch FtM cache stats', error);
    }
  },

  async getParkedCrossDomain(params?: {
    exclude_generic?: boolean;
    min_domains?: number;
    limit?: number;
    offset?: number;
  }): Promise<{ success: boolean; items: NriParkedCrossDomain[]; total_filtered?: number }> {
    try {
      const response = await getApi().get<{
        success: boolean;
        items: NriParkedCrossDomain[];
        total_filtered?: number;
      }>(apiPath(API_INVESTIGATION.parkedCrossDomain), {
        ...investigationConfig(),
        params: params ?? {},
      });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch cross-domain parked mentions', error);
    }
  },

  async getHypotheses(params?: {
    status?: string;
    ftm_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: NriHypothesis[]; total: number; limit: number; offset: number }> {
    try {
      const response = await getApi().get<{
        items: NriHypothesis[];
        total: number;
        limit: number;
        offset: number;
      }>(apiPath(API_INVESTIGATION.hypotheses), { ...investigationConfig(), params: params ?? {} });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch hypotheses', error);
    }
  },

  async getHypothesis(hypId: string): Promise<NriHypothesisDetail> {
    try {
      const response = await getApi().get<NriHypothesisDetail>(
        apiPath(API_INVESTIGATION.hypothesis(hypId)),
        investigationConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch hypothesis', error);
    }
  },

  async matchSpine(text: string, schemaName?: string): Promise<Record<string, unknown>> {
    try {
      const response = await getApi().post<Record<string, unknown>>(
        apiPath(API_INVESTIGATION.spineMatch),
        { text, schema_name: schemaName },
        investigationConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to match spine entity', error);
    }
  },

  async getSpineEntities(params?: {
    dataset?: string;
    limit?: number;
  }): Promise<{ success?: boolean; items: NriSpineEntity[] }> {
    try {
      const response = await getApi().get<{ success?: boolean; items: NriSpineEntity[] }>(
        apiPath(API_INVESTIGATION.spineEntities),
        { ...investigationConfig(), params: params ?? {} },
      );
      const data = response.data;
      if (Array.isArray(data)) {
        return { success: true, items: data as NriSpineEntity[] };
      }
      return { success: data?.success, items: data?.items ?? [] };
    } catch (error) {
      return handleError('Failed to fetch spine entities', error);
    }
  },
};
