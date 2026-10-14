/**
 * Reader research subject board API.
 */
import { getApi } from './client';
import Logger from '../../utils/logger';

export type ResearchSubjectSummary = {
  domain_key: string;
  canonical_entity_id: number;
  profile_id: number | null;
  title: string;
  status?: string;
  material_updated_at?: string;
  assertion_counts?: { is: number; is_not: number; open: number };
  href?: string;
};

export type ResearchDomainBlock = {
  domain_key: string;
  label: string;
  keywords: string[];
  subjects?: string[];
};

export type ResearchClaim = {
  id?: number;
  claim_text?: string;
  text?: string;
  verdict?: string;
  evidence_strength?: string;
  evidence_grade?: string;
  source_url?: string;
  quote?: string;
  updated_at?: string;
};

export type ResearchCitation = {
  source_url?: string;
  url?: string;
  title?: string;
  quote?: string;
  article_id?: number;
  document_id?: number;
  label?: string;
};

export type ResearchSubjectBoard = {
  ok: boolean;
  error?: string;
  domain_key?: string;
  domain_label?: string;
  domain_keywords?: string[];
  title?: string;
  entity?: { id?: number; canonical_name?: string; entity_type?: string };
  knowledge_profile_id?: number;
  status?: string;
  material_updated_at?: string;
  supported?: unknown[];
  not_supported?: unknown[];
  open?: unknown[];
  assertion_counts?: { is: number; is_not: number; open: number };
  claims?: ResearchClaim[];
  claim_verdict_counts?: Record<string, number>;
  citations?: ResearchCitation[];
  vault_path?: string | null;
  vault_title?: string | null;
  body_md?: string | null;
};

export const readerApi = {
  async listResearchSubjects(domain?: string, limit = 50) {
    try {
      const params: Record<string, string | number> = { limit };
      if (domain) params.domain = domain;
      const response = await getApi().get('/api/reader/research/subjects', {
        params,
      });
      return response.data as {
        ok: boolean;
        subjects: ResearchSubjectSummary[];
        domains: ResearchDomainBlock[];
        count: number;
      };
    } catch (error) {
      Logger.apiError('Failed to list research subjects', error as Error);
      return { ok: false, subjects: [], domains: [], count: 0 };
    }
  },

  async getResearchSubject(domainKey: string, entityId: number) {
    try {
      const response = await getApi().get(
        `/api/reader/research/subjects/${encodeURIComponent(domainKey)}/${entityId}`
      );
      return response.data as ResearchSubjectBoard;
    } catch (error) {
      Logger.apiError('Failed to fetch research subject', error as Error);
      return {
        ok: false,
        error: (error as Error).message || 'failed',
      } as ResearchSubjectBoard;
    }
  },
};
