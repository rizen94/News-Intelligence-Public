/**
 * Context-centric API — Phase 4 frontend.
 * Entity profiles, contexts, tracked events, claims, pattern discoveries, status/quality.
 * Backend: api/domains/intelligence_hub/routes/context_centric.py (flat /api/...).
 */
import { getApi } from './client';
import { getApiOrigin } from '../../config/apiConfig';
import Logger from '../../utils/logger';

/** Context-centric routes: always use full path /api/... so the request hits the backend correctly. */
function apiPath(absolutePath: string): string {
  return absolutePath.startsWith('/') ? absolutePath : `/${absolutePath}`;
}

/** Use server origin (no path) so /api/tracked_events/... etc. resolve correctly when API base URL has a path (e.g. /api/v4). */
function contextCentricConfig(): { baseURL?: string } {
  const origin = getApiOrigin();
  return origin ? { baseURL: origin } : {};
}

export interface EntityProfile {
  id: number;
  domain_key: string;
  canonical_entity_id: number | null;
  compilation_date: string | null;
  sections: Record<string, unknown> | null;
  relationships_summary: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Context {
  id: number;
  source_type: string;
  domain_key: string;
  title: string | null;
  content: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TrackedEvent {
  id: number;
  event_type: string | null;
  event_name: string | null;
  start_date: string | null;
  end_date: string | null;
  geographic_scope: string | null;
  key_participant_entity_ids: number[] | null;
  milestones: unknown;
  sub_event_ids: number[] | null;
  created_at: string | null;
  updated_at: string | null;
  domain_keys: string[];
  chronicles?: EventChronicle[];
}

export interface EventChronicle {
  id: number;
  update_date: string | null;
  developments: string | null;
  analysis: string | null;
  predictions: string | null;
  momentum_score: number | null;
  created_at: string | null;
}

export interface ExtractedClaim {
  id: number;
  context_id: number;
  subject_text: string | null;
  predicate_text: string | null;
  object_text: string | null;
  confidence: number | null;
  valid_from: string | null;
  valid_to: string | null;
  created_at: string | null;
}

export interface PatternDiscovery {
  id: number;
  pattern_type: string;
  domain_key: string | null;
  context_ids: number[];
  entity_profile_ids: number[];
  confidence: number | null;
  data: unknown;
  created_at: string | null;
}

export interface ContextCentricStatus {
  contexts: number;
  article_to_context_links: number;
  entity_profiles: number;
  old_entity_to_new_mappings: number;
  context_entity_mentions: number;
  extracted_claims: number;
  tracked_events: number;
  event_chronicles: number;
  pattern_discoveries: number;
}

export interface ContextCentricQualityDomain {
  domain: string;
  rss_feeds_active?: number | null;
  articles: number | null;
  article_entities: number | null;
  entity_canonical: number | null;
  contexts: number | null;
  article_to_context_links: number | null;
  entity_profiles: number | null;
  context_entity_mentions: number | null;
  entity_coverage_pct: number | null;
  context_coverage_pct: number | null;
}

export interface ContextCentricQuality {
  by_domain: Record<string, ContextCentricQualityDomain>;
  summary: string;
}

const handleError = (message: string, error: unknown): never => {
  Logger.apiError(message, error as Error);
  throw error;
};

export const contextCentricApi = {
  async getStatus(): Promise<ContextCentricStatus> {
    try {
      const response = await getApi().get<ContextCentricStatus>(apiPath('/api/context_centric/status'), contextCentricConfig());
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch context-centric status', error);
    }
  },

  async getQuality(): Promise<ContextCentricQuality> {
    try {
      const response = await getApi().get<ContextCentricQuality>(apiPath('/api/context_centric/quality'), contextCentricConfig());
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch context-centric quality', error);
    }
  },

  /** Run entity_profile_sync for a domain (or all). Creates entity_profiles from entity_canonical. */
  async syncEntityProfiles(domain_key?: string): Promise<{ success: boolean; created_by_domain?: Record<string, number>; error?: string }> {
    try {
      const response = await getApi().post<{ success: boolean; created_by_domain?: Record<string, number>; error?: string }>(
        apiPath('/api/context_centric/sync_entity_profiles'),
        {},
        { ...contextCentricConfig(), params: domain_key ? { domain_key } : {} },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to sync entity profiles', error as Error);
      const msg = (error as { response?: { status?: number } })?.response?.status === 404
        ? 'Entity profiles API not found (404). Use the API at the root (no /api suffix in base URL) or ensure backend runs main_v4 with context-centric routes.'
        : (error as Error)?.message ?? 'Request failed';
      return { success: false, error: msg };
    }
  },

  /** Backfill intelligence.contexts from domain articles that don't have a context yet. */
  async syncContexts(domain_key?: string, limit?: number): Promise<{ success: boolean; contexts_created_by_domain?: Record<string, number>; error?: string }> {
    try {
      const params: Record<string, string | number> = {};
      if (domain_key) params.domain_key = domain_key;
      if (limit != null) params.limit = limit;
      const response = await getApi().post<{ success: boolean; contexts_created_by_domain?: Record<string, number> }>(
        apiPath('/api/context_centric/sync_contexts'),
        {},
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to sync contexts', error as Error);
      const msg = (error as Error)?.message ?? 'Request failed';
      return { success: false, error: msg };
    }
  },

  async getEntityProfiles(params?: { domain_key?: string; limit?: number; offset?: number; brief?: boolean }) {
    try {
      const response = await getApi().get<{ items: EntityProfile[]; limit: number; offset: number }>(
        apiPath('/api/entity_profiles'),
        { ...contextCentricConfig(), params: params ?? {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity profiles', error);
    }
  },

  async getEntityProfile(profileId: number): Promise<EntityProfile> {
    try {
      const response = await getApi().get<EntityProfile>(apiPath(`/api/entity_profiles/${profileId}`), contextCentricConfig());
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity profile', error);
    }
  },

  async getContext(contextId: number): Promise<Context & { article?: { id: number; title: string; url: string | null; source: string | null; summary: string | null; published_date: string | null; content: string | null } | null }> {
    try {
      const response = await getApi().get<Context & { article?: { id: number; title: string; url: string | null; source: string | null; summary: string | null; published_date: string | null; content: string | null } | null }>(
        apiPath(`/api/contexts/${contextId}`),
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch context', error);
    }
  },

  /** Update context metadata (e.g. orchestrator_tags for story prioritization). */
  async updateContext(
    contextId: number,
    body: { orchestrator_tags?: string[] },
  ): Promise<Context> {
    try {
      const response = await getApi().patch<Context>(
        apiPath(`/api/contexts/${contextId}`),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to update context', error);
    }
  },

  async getContexts(params?: {
    domain_key?: string;
    source_type?: string;
    limit?: number;
    offset?: number;
    brief?: boolean;
  }) {
    try {
      const response = await getApi().get<{ items: Context[]; limit: number; offset: number }>(
        apiPath('/api/contexts'),
        { ...contextCentricConfig(), params: params ?? {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch contexts', error);
    }
  },

  async getTrackedEvents(params?: { event_type?: string; domain_key?: string; limit?: number; offset?: number }) {
    try {
      const response = await getApi().get<{ items: TrackedEvent[]; limit: number; offset: number }>(
        apiPath('/api/tracked_events'),
        { ...contextCentricConfig(), params: params ?? {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch tracked events', error);
    }
  },

  async getTrackedEvent(eventId: number): Promise<TrackedEvent> {
    try {
      const response = await getApi().get<TrackedEvent>(apiPath(`/api/tracked_events/${eventId}`), contextCentricConfig());
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch tracked event', error);
    }
  },

  async getTrackedEventReport(eventId: number): Promise<{
    event_id: number;
    report_md: string;
    generated_at: string | null;
    context_ids_included: number[];
    chronicle_count: number;
    context_count: number;
  } | null> {
    try {
      const response = await getApi().get(apiPath(`/api/tracked_events/${eventId}/report`), contextCentricConfig());
      return response.data;
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const ax = (error as { response?: { status?: number } }).response;
        if (ax?.status === 404) return null;
      }
      return null;
    }
  },

  async generateTrackedEventReport(eventId: number): Promise<{
    success: boolean;
    event_id?: number;
    event_name?: string;
    report_md?: string;
    generated_at?: string;
    context_ids_included?: number[];
    chronicle_count?: number;
    context_count?: number;
    error?: string;
  }> {
    try {
      const response = await getApi().post(apiPath(`/api/tracked_events/${eventId}/report`), undefined, contextCentricConfig());
      return response.data;
    } catch (error: unknown) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        Logger.apiError('Report endpoint not found (404)', error as Error);
        throw new Error(
          'Report endpoint not found. Use the API server root as base URL (e.g. http://localhost:8000) and ensure context-centric routes are enabled.',
        );
      }
      return handleError('Failed to generate report', error) as never;
    }
  },

  async getClaims(params?: { context_id?: number; limit?: number; offset?: number }) {
    try {
      const response = await getApi().get<{ items: ExtractedClaim[]; limit: number; offset: number }>(
        apiPath('/api/claims'),
        { ...contextCentricConfig(), params: params ?? {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch claims', error);
    }
  },

  async getPatternDiscoveries(params?: {
    pattern_type?: string;
    domain_key?: string;
    limit?: number;
    offset?: number;
  }) {
    try {
      const response = await getApi().get<{
        items: PatternDiscovery[];
        limit: number;
        offset: number;
      }>(apiPath('/api/pattern_discoveries'), { ...contextCentricConfig(), params: params ?? {} });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch pattern discoveries', error);
    }
  },

  /** Phase 4.2: Update entity profile metadata (importance, entity_type, tracking_params, alert_thresholds, orchestrator_tags). */
  async updateEntityProfile(
    profileId: number,
    body: {
      importance?: 'high' | 'medium' | 'low';
      entity_type?: string;
      tracking_params?: Record<string, unknown>;
      alert_thresholds?: Record<string, unknown>;
      orchestrator_tags?: string[];
    },
  ): Promise<EntityProfile> {
    try {
      const response = await getApi().patch<EntityProfile>(apiPath(`/api/entity_profiles/${profileId}`), body, contextCentricConfig());
      return response.data;
    } catch (error) {
      return handleError('Failed to update entity profile', error);
    }
  },

  /** Phase 4.2: Merge source profile into target. Same domain required. */
  async mergeEntityProfiles(targetProfileId: number, sourceProfileId: number): Promise<{ success: boolean; message: string }> {
    try {
      const response = await getApi().post<{ success: boolean; message: string }>(
        apiPath(`/api/entity_profiles/${targetProfileId}/merge`),
        { source_profile_id: sourceProfileId },
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to merge entity profiles', error);
    }
  },

  /** Phase 4.5: Advanced search by claim, entity, pattern, temporal. */
  async search(params: {
    q?: string;
    claim_subject?: string;
    claim_predicate?: string;
    entity_id?: number;
    pattern_type?: string;
    valid_from?: string;
    valid_to?: string;
    domain_key?: string;
    limit?: number;
    offset?: number;
  }) {
    try {
      const response = await getApi().get<{
        claims: Array<{
          id: number;
          context_id: number;
          subject_text: string | null;
          predicate_text: string | null;
          object_text: string | null;
          confidence: number | null;
          valid_from: string | null;
          valid_to: string | null;
          created_at: string | null;
        }>;
        contexts: Array<{
          id: number;
          source_type: string;
          domain_key: string;
          title: string | null;
          content_snippet: string | null;
          metadata: unknown;
          created_at: string | null;
          updated_at: string | null;
        }>;
        pattern_discoveries: PatternDiscovery[];
        limit: number;
        offset: number;
      }>(apiPath('/api/context_centric/search'), { ...contextCentricConfig(), params: params ?? {} });
      return response.data;
    } catch (error) {
      return handleError('Failed to search', error);
    }
  },
};
