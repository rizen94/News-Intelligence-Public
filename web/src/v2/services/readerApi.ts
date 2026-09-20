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
};

export type ReaderHomeResponse = {
  domain: string | null;
  generated_at: string;
  news_window_hours: number;
  news: StoryUnit[];
  current_events: StoryUnit[];
  one_offs: StoryUnit[];
};

export type ReaderPackResponse = {
  domain: string;
  storyline_id: number;
  title: string;
  status?: string;
  summary: string;
  lede?: string;
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
  dossier_rail?: {
    entities?: Array<Record<string, unknown>>;
    tree?: Array<Record<string, unknown>>;
    hierarchy?: Record<string, unknown>;
  };
};

export async function fetchReaderHome(domain?: string | null): Promise<ReaderHomeResponse> {
  const api = getApi();
  const params = domain ? { domain } : {};
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
