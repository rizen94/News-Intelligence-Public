/**
 * v2 reader API client — additive /api/reader/* endpoints.
 */
import { getApi } from '../../services/api/client';

export type StoryUnit = {
  section_label: string;
  headline: string;
  dek: string;
  domain: string;
  storyline_id: number;
  updated_label: string;
  updated_at?: string | null;
  read_minutes: number;
  badges: string[];
  thumb_url?: string | null;
  article_count?: number;
  announced_on?: string | null;
  expected_on?: string | null;
  date_precision?: string | null;
  surface_kind: string;
  href: string;
  cluster_key?: string;
  hub_id?: number;
  folded_under_hub?: boolean;
  briefing_day?: string;
  vault_path?: string;
  body_md?: string;
  summary_md?: string;
};

export type PaginationMeta = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_prev: boolean;
  has_next: boolean;
};

export type NavId = {
  domain: string;
  storyline_id: number;
  href: string;
};

export type ReaderHomeResponse = {
  domain: string | null;
  generated_at: string;
  news_window_hours: number;
  news?: StoryUnit[];
  current_events?: StoryUnit[];
  one_offs?: StoryUnit[];
  research?: StoryUnit[];
  section?: string;
  pagination?:
    | PaginationMeta
    | {
        news: PaginationMeta;
        current_events: PaginationMeta;
        one_offs: PaginationMeta;
        research?: PaginationMeta;
      };
  nav_ids?: NavId[];
};

export type ReaderPackResponse = {
  domain: string;
  storyline_id: number;
  title: string;
  status?: string;
  summary: string;
  lede?: string;
  durable_brief?: string | null;
  brief_source?: 'pull' | 'vault_expansion' | 'durable' | 'summary' | 'none';
  document_status?: string | null;
  editorial_document?: Record<string, unknown>;
  background_information?: string | null;
  timeline_narrative?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  article_count?: number;
  timeline?: {
    events?: Array<Record<string, unknown>>;
    event_count?: number;
  };
  citations?: Array<{
    id: number;
    title: string;
    url?: string | null;
    source_domain?: string | null;
    published_at?: string | null;
    summary?: string | null;
  }>;
  also_in?: Array<{
    article_id: number;
    article_title?: string | null;
    domain: string;
    storyline_id: number;
    title?: string | null;
    article_count?: number;
    href?: string;
  }>;
  dossier_rail?: {
    entities?: Array<Record<string, unknown>>;
    tree?: Array<Record<string, unknown>>;
    hierarchy?: Record<string, unknown>;
  };
  vault_context_pack?: {
    ok?: boolean;
    note_count?: number;
    actors?: string[];
    tags?: string[];
    notes?: Array<{
      title?: string;
      vault_path?: string;
      significance_excerpt?: string | null;
      tags?: string[];
      is_seed?: boolean;
      note_status?: string;
      lifecycle?: string;
    }>;
    message?: string;
  } | null;
  vault_expansion?: {
    title?: string | null;
    vault_path?: string | null;
    body_md?: string | null;
    summary_md?: string | null;
    updated_at?: string | null;
    source_article_id?: number | null;
  } | null;
};

export async function fetchReaderHome(
  domain?: string | null,
  opts?: { page?: number; pageSize?: number; section?: string | null }
): Promise<ReaderHomeResponse> {
  const api = getApi();
  const params: Record<string, string | number> = {};
  if (domain) params.domain = domain;
  if (opts?.page) params.page = opts.page;
  if (opts?.pageSize) params.page_size = opts.pageSize;
  if (opts?.section) params.section = opts.section;
  const { data } = await api.get<ReaderHomeResponse>('/api/reader/home', { params });
  return data;
}

export async function fetchReaderStoryline(
  storylineId: number | string,
  domain: string
): Promise<ReaderPackResponse> {
  const api = getApi();
  const { data } = await api.get<ReaderPackResponse>(
    `/api/reader/storylines/${storylineId}`,
    { params: { domain } }
  );
  return data;
}

export type VaultHubPackResponse = {
  ok: boolean;
  hub: {
    id: number;
    cluster_key?: string;
    title?: string;
    domain_key: string;
    vault_path?: string;
    member_storyline_ids?: number[];
    seed_entity_ids?: number[];
    href?: string;
    tags?: string[];
    updated_at?: string | null;
    current_brief?: string | null;
    brief_updated_at?: string | null;
    brief_fingerprint?: string | null;
    brief_refreshed?: boolean;
    surface_kind?: string;
  };
  current_brief?: string | null;
  brief_updated_at?: string | null;
  note?: Record<string, unknown>;
  vault_context_pack?: ReaderPackResponse['vault_context_pack'];
  members?: Array<{
    storyline_id: number;
    domain: string;
    headline: string;
    dek?: string;
    article_count?: number;
    updated_at?: string | null;
    href?: string;
    surface_kind?: string;
  }>;
  timeline?: Array<{
    published_at?: string | null;
    title: string;
    article_id: number;
    storyline_id: number;
    url?: string | null;
  }>;
  sibling_hubs?: Array<{
    id: number;
    cluster_key?: string;
    title?: string;
    href?: string;
    member_count?: number;
    current_brief?: string | null;
  }>;
};

export async function fetchVaultHubs(domain?: string | null): Promise<{
  ok: boolean;
  hubs: Array<Record<string, unknown>>;
  count: number;
}> {
  const api = getApi();
  const params: Record<string, string> = {};
  if (domain) params.domain = domain;
  const { data } = await api.get('/api/reader/vault-hubs', { params });
  return data;
}

export async function fetchVaultHub(
  idOrSlug: string,
  domain?: string | null
): Promise<VaultHubPackResponse> {
  const api = getApi();
  const params: Record<string, string> = {};
  if (domain) params.domain = domain;
  const { data } = await api.get<VaultHubPackResponse>(
    `/api/reader/vault-hubs/${encodeURIComponent(idOrSlug)}`,
    { params }
  );
  return data;
}
