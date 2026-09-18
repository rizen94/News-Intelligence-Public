/**
 * Research assemble API — NL idea → interpret → package.
 * Flat routes under /api/research/... and /api/{domain}/daily/intake.
 */
import { getApi } from './client';
import { getApiOrigin } from '../../config/apiConfig';
import { unwrapData } from './editorialUnwrap';

/** Keep base at origin so interceptor does not double-prefix path-only URLs. */
function cfg(extra?: { timeout?: number }): { baseURL?: string; timeout?: number } {
  const origin = getApiOrigin();
  return {
    ...(origin ? { baseURL: origin } : {}),
    ...(extra?.timeout != null ? { timeout: extra.timeout } : {}),
  };
}

export type ResearchInterpretBrief = {
  ok?: boolean;
  working_title: string;
  research_question: string;
  domain_key?: string | null;
  /** API returns objects `{name, entity_type, role}` (not bare strings). */
  entities: Array<string | { name?: string; entity_type?: string; role?: string }>;
  key_assumptions: string[];
  facts_to_verify?: string[];
  search_queries: string[];
  time_scope?: string | null;
  exclusions?: string[];
  open_questions?: string[];
  source?: string;
  error?: string;
};

export type ResearchAssembleResult = {
  ok?: boolean;
  package_id: number | string | null;
  /** Draft news_story seeded with brief_md for the readable reader surface. */
  story_id?: number | string | null;
  created?: boolean;
  domain_key: string;
  target_modal?: string;
  status?: string;
  working_title: string;
  research_question: string;
  interpret?: ResearchInterpretBrief | boolean | null;
  mentions?: string[];
  entities_resolved?: unknown[];
  search_queries?: string[];
  member_count?: number;
  claimish_count?: number;
  spine?: Record<string, unknown> | null;
  draft_sections?: Record<string, string | string[]>;
  brief_md?: string;
  next?: {
    story_url_hint?: string | null;
    package_url_hint?: string;
    research_run?: string;
    get_package?: string;
  };
  error?: string;
};

export type IntakeBriefHighlight = {
  kind?: string;
  id: number | string;
  title?: string;
  domain_key?: string;
  assemble_hint?: string;
  source_name?: string;
  why?: string;
};

export type IntakeBrief = {
  ok?: boolean;
  window_hours: number;
  generated_at: string;
  highlights: IntakeBriefHighlight[];
  totals?: { articles?: number; events?: number; topics?: number };
};

const LONG_TIMEOUT_MS = 180_000;

export const researchAssembleApi = {
  async interpret(params: {
    idea: string;
    domain_key: string;
  }): Promise<ResearchInterpretBrief> {
    const res = await getApi().post(
      '/api/research/interpret',
      {
        idea: params.idea,
        domain_key: params.domain_key,
      },
      cfg({ timeout: LONG_TIMEOUT_MS })
    );
    return unwrapData<ResearchInterpretBrief>(res);
  },

  async assemble(params: {
    idea: string;
    domain_key: string;
    interpret?: boolean;
    run_spine?: boolean;
    dry_run?: boolean;
  }): Promise<ResearchAssembleResult> {
    const res = await getApi().post(
      '/api/research/assemble',
      {
        idea: params.idea,
        domain_key: params.domain_key,
        interpret: params.interpret ?? true,
        run_spine: params.run_spine ?? false,
        dry_run: params.dry_run ?? false,
      },
      cfg({ timeout: LONG_TIMEOUT_MS })
    );
    return unwrapData<ResearchAssembleResult>(res);
  },

  async intakeBrief(params?: {
    domain_key?: string;
    hours?: number;
    limit?: number;
  }): Promise<IntakeBrief> {
    const domain = params?.domain_key || 'all';
    const res = await getApi().get(`/api/${encodeURIComponent(domain)}/daily/intake`, {
      ...cfg({ timeout: 30_000 }),
      params: {
        hours: params?.hours ?? 72,
        limit: Math.max(5, params?.limit ?? 12),
      },
    });
    return unwrapData<IntakeBrief>(res);
  },
};
