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

/** Use server origin (no path) so /api/tracked_events/... etc. resolve correctly when API base URL has a path. */
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

/** Topics and storylines that share the context's linked article (cross-entity audit). */
export interface ContextRelated {
  topics: { id: number; name: string | null }[];
  storylines: { id: number; title: string | null }[];
}

export type ContextDetailResponse = Context & {
  article?: {
    id: number;
    title: string;
    url: string | null;
    source: string | null;
    summary: string | null;
    published_date: string | null;
    content: string | null;
  } | null;
  related?: ContextRelated;
};

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

export interface ContextGroupingFeedbackItem {
  id: number;
  context_id: number;
  grouping_type: string;
  grouping_id: number | null;
  grouping_label: string | null;
  judgment: string;
  notes: string | null;
  judged_by: string | null;
  judged_at: string | null;
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

/** Phase 3 T3.1: Processed document (list row). */
export interface ProcessedDocument {
  id: number;
  source_type: string | null;
  source_name: string | null;
  source_url: string | null;
  title: string | null;
  publication_date: string | null;
  document_type: string | null;
  created_at: string | null;
}

/** Phase 3 T3.3: Narrative thread (list row). */
export interface NarrativeThread {
  id: number;
  domain_key: string;
  storyline_id: number;
  summary_snippet: string | null;
  linked_article_ids: number[];
  created_at: string | null;
}

/** T1.2: Canonical entity from entity_canonical table. */
export interface CanonicalEntity {
  canonical_entity_id: number;
  canonical_name: string;
  entity_type: string;
  aliases: string[];
  mention_count?: number;
  confidence?: number;
  match_reason?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Entity position / stance on a topic. */
export interface EntityPosition {
  id: number;
  topic: string;
  position: string;
  confidence: number | null;
  evidence_refs: unknown[];
  date_range?: string | null;
  created_at: string | null;
}

/** Entity dossier — compiled from articles, storylines, relationships. */
export interface EntityDossier {
  id: number;
  domain_key: string;
  entity_id: number;
  compilation_date: string | null;
  chronicle_data: { article_id: number; title: string; url: string; published_at: string | null; source_domain: string; snippet: string }[];
  relationships: { source_domain: string; source_entity_id: number; target_domain: string; target_entity_id: number; relationship_type: string; confidence: number | null }[];
  positions: EntityPosition[];
  patterns: { count?: number; discoveries?: { id: number; pattern_type: string; confidence: number | null; data: Record<string, unknown>; created_at: string | null }[] } | Record<string, never>;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

/** Full entity synthesis context (from /api/synthesis/entity/{id}). */
export interface EntitySynthesis {
  success: boolean;
  domain_key: string;
  entity: { id: number; canonical_name: string; entity_type: string; aliases: string[] };
  articles: { id: number; title: string; content_excerpt: string; published_at: string | null; summary: string }[];
  dossier: EntityDossier | null;
  positions: { topic: string; position: string; confidence: number | null; evidence_refs: unknown[] }[];
  relationships: { source_domain: string; source_entity_id: number; target_domain: string; target_entity_id: number; relationship_type: string; confidence: number | null }[];
  statistics: { article_count: number; position_count: number; relationship_count: number; has_dossier: boolean };
}

/** T1.2: Merge candidate — pair of canonical entities that likely refer to the same real-world entity. */
export interface MergeCandidate {
  source_id: number;
  source_name: string;
  target_id: number;
  target_name: string;
  entity_type: string;
  confidence: number;
  reason: string;
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
      const response = await getApi().get<{
        items: EntityProfile[];
        limit: number;
        offset: number;
        total?: number;
      }>(apiPath('/api/entity_profiles'), { ...contextCentricConfig(), params: params ?? {} });
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

  async getContext(contextId: number): Promise<ContextDetailResponse> {
    try {
      const response = await getApi().get<ContextDetailResponse>(
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
      const response = await getApi().get<{
        items: Context[];
        limit: number;
        offset: number;
        total?: number;
      }>(apiPath('/api/contexts'), { ...contextCentricConfig(), params: params ?? {} });
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch contexts', error);
    }
  },

  async postContextGroupingFeedback(
    contextId: number,
    body: {
      grouping_type: 'topic' | 'storyline' | 'pattern' | 'other';
      judgment: 'belongs' | 'does_not_belong' | 'unsure';
      grouping_id?: number | null;
      grouping_label?: string | null;
      notes?: string | null;
      judged_by?: string | null;
    },
  ): Promise<{ success: boolean; data?: { id: number; judged_at: string }; message?: string | null }> {
    try {
      const response = await getApi().post<{
        success: boolean;
        data?: { id: number; judged_at: string };
        message?: string | null;
      }>(apiPath(`/api/contexts/${contextId}/grouping_feedback`), body, contextCentricConfig());
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to submit context grouping feedback', error as Error);
      throw error;
    }
  },

  async getContextGroupingFeedback(
    contextId: number,
    limit = 50,
  ): Promise<{ success: boolean; data?: { items: ContextGroupingFeedbackItem[] }; message?: string | null }> {
    try {
      const response = await getApi().get<{
        success: boolean;
        data?: { items: ContextGroupingFeedbackItem[] };
        message?: string | null;
      }>(apiPath(`/api/contexts/${contextId}/grouping_feedback`), {
        ...contextCentricConfig(),
        params: { limit },
      });
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to fetch context grouping feedback', error as Error);
      throw error;
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

  /** Phase 1: Create tracked event. */
  async createTrackedEvent(body: {
    event_type: string;
    event_name: string;
    start_date?: string | null;
    end_date?: string | null;
    geographic_scope?: string | null;
    key_participant_entity_ids?: unknown[];
    milestones?: unknown[];
    sub_event_ids?: number[] | null;
    domain_keys?: string[];
  }): Promise<TrackedEvent & { id: number }> {
    try {
      const response = await getApi().post<TrackedEvent & { id: number }>(
        apiPath('/api/tracked_events'),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to create tracked event', error);
    }
  },

  /** Phase 2 T2.1: Trigger chronicle update for event (build developments, momentum_score). */
  async triggerEventChronicleUpdate(
    eventId: number,
    body?: { update_date?: string; developments_days?: number },
  ): Promise<{ success: boolean; chronicle_id?: number; developments_count?: number; momentum_score?: number; error?: string }> {
    try {
      const response = await getApi().post<{ success: boolean; chronicle_id?: number; developments_count?: number; momentum_score?: number; error?: string }>(
        apiPath(`/api/tracked_events/${eventId}/chronicles/update`),
        body ?? {},
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to refresh chronicles', error);
    }
  },

  /** Phase 1: Update tracked event. */
  async updateTrackedEvent(
    eventId: number,
    body: Partial<{
      event_type: string;
      event_name: string;
      start_date: string | null;
      end_date: string | null;
      geographic_scope: string | null;
      key_participant_entity_ids: unknown[];
      milestones: unknown[];
      sub_event_ids: number[] | null;
      domain_keys: string[];
    }>,
  ): Promise<TrackedEvent> {
    try {
      const response = await getApi().put<TrackedEvent>(
        apiPath(`/api/tracked_events/${eventId}`),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to update tracked event', error);
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

  // Phase 3 T3.1: Processed documents
  async getProcessedDocuments(params?: { source_type?: string; limit?: number; offset?: number }) {
    try {
      const response = await getApi().get<{ items: ProcessedDocument[]; limit: number; offset: number }>(
        apiPath('/api/processed_documents'),
        { ...contextCentricConfig(), params: params ?? {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch processed documents', error);
    }
  },

  async getProcessedDocument(documentId: number) {
    try {
      const response = await getApi().get<ProcessedDocument & { authors?: string[]; extracted_sections?: unknown; key_findings?: unknown; entities_mentioned?: unknown; citations?: unknown; metadata?: unknown; updated_at?: string | null }>(
        apiPath(`/api/processed_documents/${documentId}`),
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch processed document', error);
    }
  },

  async createProcessedDocument(body: { source_url: string; title?: string; source_type?: string; source_name?: string; document_type?: string; publication_date?: string; authors?: string[]; metadata?: Record<string, unknown> }) {
    try {
      const response = await getApi().post<{ success: boolean; document_id?: number; error?: string }>(
        apiPath('/api/processed_documents'),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to create processed document', error);
    }
  },

  async batchProcessDocuments(limit = 10): Promise<{ processed: number; errors?: string[] }> {
    try {
      const response = await getApi().post<{ processed: number; errors?: string[] }>(
        apiPath('/api/processed_documents/batch_process'),
        {},
        { ...contextCentricConfig(), params: { limit } },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to process documents', error);
    }
  },

  async ingestProcessedDocumentsFromConfig(): Promise<{ inserted: number; errors: string[] }> {
    try {
      const response = await getApi().post<{ inserted: number; errors: string[] }>(
        apiPath('/api/processed_documents/ingest_from_config'),
        {},
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to ingest from config', error);
    }
  },

  // Phase 3 T3.3: Narrative threads
  async getNarrativeThreads(params?: { domain_key?: string; limit?: number; offset?: number }) {
    try {
      const response = await getApi().get<{ items: NarrativeThread[]; limit: number; offset: number }>(
        apiPath('/api/narrative_threads'),
        { ...contextCentricConfig(), params: params ?? {} },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch narrative threads', error);
    }
  },

  async buildNarrativeThreads(body: { domain_key: string; limit?: number }): Promise<{ success: boolean; built: number; errors: string[] }> {
    try {
      const response = await getApi().post<{ success: boolean; built: number; errors: string[] }>(
        apiPath('/api/narrative_threads/build'),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to build narrative threads', error);
    }
  },

  async synthesizeNarrativeThreads(body?: { domain_key?: string; thread_ids?: number[] }): Promise<{ success: boolean; synthesis?: string; thread_count?: number; threads?: NarrativeThread[]; error?: string }> {
    try {
      const response = await getApi().post<{ success: boolean; synthesis?: string; thread_count?: number; threads?: NarrativeThread[]; error?: string }>(
        apiPath('/api/narrative_threads/synthesize'),
        body ?? {},
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to synthesize narrative threads', error);
    }
  },

  // Entity resolution (T1.2)

  async getCanonicalEntities(params: {
    domain_key: string;
    entity_type?: string;
    search?: string;
    min_mentions?: number;
    limit?: number;
    offset?: number;
  }): Promise<{ success: boolean; entities: CanonicalEntity[]; domain_key: string }> {
    try {
      const response = await getApi().get<{ success: boolean; entities: CanonicalEntity[]; domain_key: string }>(
        apiPath('/api/entities/canonical'),
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch canonical entities', error);
    }
  },

  async resolveEntity(body: {
    domain_key: string;
    entity_name: string;
    entity_type?: string;
  }): Promise<{ success: boolean; match: CanonicalEntity | null; candidates: CanonicalEntity[] }> {
    try {
      const response = await getApi().post<{ success: boolean; match: CanonicalEntity | null; candidates: CanonicalEntity[] }>(
        apiPath('/api/entities/resolve'),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to resolve entity', error);
    }
  },

  async getMergeCandidates(params: {
    domain_key: string;
    min_confidence?: number;
    limit?: number;
  }): Promise<{ success: boolean; candidates: MergeCandidate[] }> {
    try {
      const response = await getApi().get<{ success: boolean; candidates: MergeCandidate[] }>(
        apiPath('/api/entities/merge_candidates'),
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch merge candidates', error);
    }
  },

  async mergeCanonicalEntities(body: {
    domain_key: string;
    keep_id: number;
    merge_id: number;
  }): Promise<{ success: boolean; keep_id?: number; merged_id?: number; articles_reassigned?: number; aliases_added?: number; error?: string }> {
    try {
      const response = await getApi().post<{ success: boolean; keep_id?: number; merged_id?: number; articles_reassigned?: number; aliases_added?: number; error?: string }>(
        apiPath('/api/entities/merge'),
        body,
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to merge entities', error);
    }
  },

  async populateAliases(domain_key?: string, min_mentions?: number): Promise<{ success: boolean; results: Record<string, { updated: number; new_aliases: number }> }> {
    try {
      const params: Record<string, string | number> = {};
      if (domain_key) params.domain_key = domain_key;
      if (min_mentions != null) params.min_mentions = min_mentions;
      const response = await getApi().post<{ success: boolean; results: Record<string, { updated: number; new_aliases: number }> }>(
        apiPath('/api/entities/populate_aliases'),
        {},
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to populate aliases', error);
    }
  },

  async autoMergeEntities(domain_key?: string, min_confidence?: number): Promise<{ success: boolean; results: Record<string, { merges_performed: number }> }> {
    try {
      const params: Record<string, string | number> = {};
      if (domain_key) params.domain_key = domain_key;
      if (min_confidence != null) params.min_confidence = min_confidence;
      const response = await getApi().post<{ success: boolean; results: Record<string, { merges_performed: number }> }>(
        apiPath('/api/entities/auto_merge'),
        {},
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to auto-merge entities', error);
    }
  },

  async crossDomainLinkEntities(min_confidence?: number): Promise<{ success: boolean; linked: number; relationships_created: number }> {
    try {
      const params: Record<string, number> = {};
      if (min_confidence != null) params.min_confidence = min_confidence;
      const response = await getApi().post<{ success: boolean; linked: number; relationships_created: number }>(
        apiPath('/api/entities/cross_domain_link'),
        {},
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to cross-domain link entities', error);
    }
  },

  async runResolutionBatch(autoMergeConfidence?: number, crossDomainConfidence?: number): Promise<Record<string, unknown>> {
    try {
      const params: Record<string, number> = {};
      if (autoMergeConfidence != null) params.auto_merge_confidence = autoMergeConfidence;
      if (crossDomainConfidence != null) params.cross_domain_confidence = crossDomainConfidence;
      const response = await getApi().post<Record<string, unknown>>(
        apiPath('/api/entities/run_resolution_batch'),
        {},
        { ...contextCentricConfig(), params },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to run resolution batch', error);
    }
  },

  // Entity synthesis (full dossier context)
  async getEntitySynthesis(entityId: number, domainKey: string): Promise<EntitySynthesis> {
    try {
      const response = await getApi().get<EntitySynthesis>(
        apiPath(`/api/synthesis/entity/${entityId}`),
        { ...contextCentricConfig(), params: { domain_key: domainKey } },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity synthesis', error);
    }
  },

  async getEntityDossier(domainKey: string, entityId: number): Promise<EntityDossier> {
    try {
      const response = await getApi().get<EntityDossier>(
        apiPath('/api/entity_dossiers'),
        { ...contextCentricConfig(), params: { domain_key: domainKey, entity_id: entityId } },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity dossier', error);
    }
  },

  async compileEntityDossier(domainKey: string, entityId: number): Promise<{ success: boolean; dossier?: EntityDossier; error?: string }> {
    try {
      const response = await getApi().post<{ success: boolean; dossier?: EntityDossier; error?: string }>(
        apiPath('/api/entity_dossiers/compile'),
        { domain_key: domainKey, entity_id: entityId },
        contextCentricConfig(),
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to compile entity dossier', error);
    }
  },

  async getEntityPositions(domainKey: string, entityId: number, limit = 50): Promise<{ success: boolean; positions: EntityPosition[] }> {
    try {
      const response = await getApi().get<{ success: boolean; positions: EntityPosition[] }>(
        apiPath('/api/entity_positions'),
        { ...contextCentricConfig(), params: { domain_key: domainKey, entity_id: entityId, limit } },
      );
      return response.data;
    } catch (error) {
      return handleError('Failed to fetch entity positions', error);
    }
  },
};
