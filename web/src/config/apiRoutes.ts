/**
 * API route constants — single source for Python + TypeScript paths.
 */
export const API_INVESTIGATION = {
  health: '/api/investigation/health',
  resolvedMentions: '/api/investigation/resolved_mentions',
  parked: '/api/investigation/parked',
  parkedReview: (id: number) => `/api/investigation/parked/${id}`,
  entityBridge: (entityProfileId: number) =>
    `/api/investigation/entity_bridge/${entityProfileId}`,
  bridgeQaAudit: '/api/investigation/bridge_qa/audit',
  entityClaims: '/api/investigation/entity_claims',
  contextIntel: (contextId: number) => `/api/investigation/context_intel/${contextId}`,
  parkedCrossDomain: '/api/investigation/parked_cross_domain',
  hypotheses: '/api/investigation/hypotheses',
  hypothesis: (hypId: string) => `/api/investigation/hypotheses/${hypId}`,
  spineEntities: '/api/investigation/spine/entities',
  spineMatch: '/api/investigation/spine/match',
  resolutionStats: '/api/investigation/resolution_stats',
  loopRuns: '/api/investigation/loop_runs',
  ftmCacheStats: '/api/investigation/ftm_cache_stats',
} as const;
