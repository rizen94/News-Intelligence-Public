/**
 * Editorial package / modal / news story API client (v11).
 * Flat routes under /api/editorial/...
 *
 * Do not confuse with `web/src/types/legacyDeskEditorial.ts` (storyline 5W1H desk types).
 */
import { getApi } from './client';
import { getApiOrigin } from '../../config/apiConfig';

function cfg(): { baseURL?: string } {
  const origin = getApiOrigin();
  return origin ? { baseURL: origin } : {};
}

export type ModalKey = 'research' | 'narrative' | 'reduction' | 'editor';

export const editorialApi = {
  listModals: () => getApi().get('/api/editorial/modals', cfg()),
  listPackages: (params?: { status?: string; domain_key?: string; limit?: number }) =>
    getApi().get('/api/editorial/packages', { ...cfg(), params }),
  getPackage: (id: number) => getApi().get(`/api/editorial/packages/${id}`, cfg()),
  createPackage: (body: Record<string, unknown>) =>
    getApi().post('/api/editorial/packages', body, cfg()),
  fromSelection: (body: Record<string, unknown>) =>
    getApi().post('/api/editorial/packages/from_selection', body, cfg()),
  fromStoryline: (body: {
    domain_key: string;
    storyline_id: number;
    target_modal?: ModalKey;
    actor?: string;
    refresh_members?: boolean;
  }) => getApi().post('/api/editorial/packages/from_storyline', body, cfg()),
  byLegacySeed: (seed: string) =>
    getApi().get('/api/editorial/packages/by_legacy_seed', {
      ...cfg(),
      params: { seed },
    }),
  patchPackage: (id: number, body: Record<string, unknown>) =>
    getApi().patch(`/api/editorial/packages/${id}`, body, cfg()),
  addMember: (id: number, body: Record<string, unknown>) =>
    getApi().post(`/api/editorial/packages/${id}/members`, body, cfg()),
  setMemberStatus: (
    packageId: number,
    memberRowId: number,
    body: { status: string; rationale?: string; modal?: string }
  ) =>
    getApi().patch(
      `/api/editorial/packages/${packageId}/members/${memberRowId}`,
      body,
      cfg()
    ),
  addLink: (id: number, body: Record<string, unknown>) =>
    getApi().post(`/api/editorial/packages/${id}/links`, body, cfg()),
  setLinkStatus: (
    packageId: number,
    linkId: number,
    body: { status: string; rationale?: string; modal?: string }
  ) =>
    getApi().patch(
      `/api/editorial/packages/${packageId}/links/${linkId}`,
      body,
      cfg()
    ),
  markReady: (id: number, body?: Record<string, unknown>) =>
    getApi().post(`/api/editorial/packages/${id}/ready`, body || {}, cfg()),
  reduction: (id: number, body: { clear: boolean; rationale?: string }) =>
    getApi().post(`/api/editorial/packages/${id}/reduction`, body, cfg()),
  runReduction: (id: number, body?: { dry_run?: boolean; force?: boolean }) =>
    getApi().post(`/api/editorial/packages/${id}/reduction/run`, body || {}, cfg()),
  runNarrative: (id: number, body?: { dry_run?: boolean; force?: boolean }) =>
    getApi().post(`/api/editorial/packages/${id}/narrative/run`, body || {}, cfg()),
  runResearch: (id: number, body?: { dry_run?: boolean; force?: boolean }) =>
    getApi().post(`/api/editorial/packages/${id}/research/run`, body || {}, cfg()),
  rework: (id: number, body: { target_modal: string; note?: string }) =>
    getApi().post(`/api/editorial/packages/${id}/rework`, body, cfg()),
  audit: (id: number) => getApi().get(`/api/editorial/packages/${id}/audit`, cfg()),
  search: (params: { modal: ModalKey; q: string; domains?: string[]; limit?: number }) =>
    getApi().get('/api/editorial/search', { ...cfg(), params }),
  attach: (id: number, body: { modal: ModalKey; hits: Record<string, unknown>[] }) =>
    getApi().post(`/api/editorial/packages/${id}/attach`, body, cfg()),
  editorAlerts: () => getApi().get('/api/editorial/editor/alerts', cfg()),
  listHandoffs: (params?: { target_modal?: string; status?: string }) =>
    getApi().get('/api/editorial/handoffs', { ...cfg(), params }),
  createHandoff: (body: Record<string, unknown>) =>
    getApi().post('/api/editorial/handoffs', body, cfg()),
  patchHandoff: (id: number, body: { status: string }) =>
    getApi().patch(`/api/editorial/handoffs/${id}`, body, cfg()),
  listStories: (params?: { status?: string; package_id?: number; limit?: number }) =>
    getApi().get('/api/editorial/stories', { ...cfg(), params }),
  draftStory: (body: Record<string, unknown>) =>
    getApi().post('/api/editorial/stories', body, cfg()),
  publishStory: (storyId: number, opts?: { assemble?: boolean }) =>
    getApi().post(
      `/api/editorial/stories/${storyId}/publish`,
      { actor: 'operator', assemble: opts?.assemble !== false },
      { ...cfg(), timeout: 180_000 }
    ),
  getStory: (id: number) => getApi().get(`/api/editorial/stories/${id}`, cfg()),
  storyAudit: (id: number) => getApi().get(`/api/editorial/stories/${id}/audit`, cfg()),

  fromEntity: (body: {
    domain_key: string;
    canonical_entity_id: number;
    actor?: string;
    refresh_members?: boolean;
  }) => getApi().post('/api/editorial/packages/from_entity', body, cfg()),

  listKnowledgeProfiles: (params?: {
    domain_key?: string;
    status?: string;
    limit?: number;
  }) => getApi().get('/api/editorial/knowledge_profiles', { ...cfg(), params }),
  getKnowledgeProfile: (id: number) =>
    getApi().get(`/api/editorial/knowledge_profiles/${id}`, cfg()),
  getKnowledgeProfileByEntity: (domain_key: string, canonical_entity_id: number) =>
    getApi().get('/api/editorial/knowledge_profiles/by_entity', {
      ...cfg(),
      params: { domain_key, canonical_entity_id },
    }),
  ensureKnowledgeProfile: (body: {
    domain_key: string;
    canonical_entity_id: number;
    actor?: string;
    refresh_package?: boolean;
  }) => getApi().post('/api/editorial/knowledge_profiles/ensure', body, cfg()),
  publishKnowledgeProfile: (profileId: number) =>
    getApi().post(
      `/api/editorial/knowledge_profiles/${profileId}/publish`,
      { actor: 'operator' },
      cfg()
    ),
  regenerateKnowledgeProfile: (profileId: number, use_llm = false) =>
    getApi().post(
      `/api/editorial/knowledge_profiles/${profileId}/regenerate`,
      { use_llm },
      cfg()
    ),
  mergeKnowledgeProfileFromPackage: (body: {
    package_id: number;
    actor?: string;
    publish?: boolean;
  }) => getApi().post('/api/editorial/knowledge_profiles/merge_from_package', body, cfg()),
};
