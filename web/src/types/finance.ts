/**
 * Finance Analysis types — orchestrator tasks, evidence, verification
 */

export interface FinancialAnalysisRequest {
  query: string;
  date_range?: { start: string; end: string };
  sources?: ('fred' | 'edgar' | 'gold_price')[];
  context?: string;
}

export interface EvidenceIndexEntry {
  ref_id: string;
  source: string;
  identifier?: string;
  series_id?: string;
  filing_id?: string;
  value: string | number;
  unit?: string;
  date: string;
  context?: string;
  task_id?: string;
}

export interface ClaimVerification {
  claim_text: string;
  status: 'verified' | 'unsupported' | 'contradicted' | 'fabricated';
  evidence_refs: string[];
  reasoning?: string;
  ref_id?: string | null;
  verdict?: string;
}

export interface VerificationResult {
  overall_verdict?: 'pass' | 'partial' | 'fail';
  total_claims: number;
  verified_count?: number;
  verified: number;
  unsupported_count?: number;
  unsupported: number;
  fabricated: number;
  contradicted_count?: number;
  claims?: ClaimVerification[];
  details?: ClaimVerification[];
}

export interface FinancialAnalysisResult {
  task_id: string;
  status:
    | 'queued'
    | 'planning'
    | 'executing'
    | 'evaluating'
    | 'revising'
    | 'complete'
    | 'failed';
  phase?:
    | 'planning'
    | 'fetching'
    | 'synthesizing'
    | 'verifying'
    | 'revising'
    | 'complete'
    | 'failed';
  analysis_text?: string;
  confidence_score?: number;
  confidence?: number;
  evidence_index?: EvidenceIndexEntry[];
  provenance?: EvidenceIndexEntry[];
  verification_result?: VerificationResult;
  verification?: { verified: number; unsupported: number; fabricated: number };
  output?: { response?: string; query?: string; verification?: object };
  provenance_list?: EvidenceIndexEntry[];
  warnings?: string[];
  errors?: string[];
  sources_consulted?: string[];
  sources_succeeded?: string[];
  sources_failed?: string[];
  created_at?: string;
  completed_at?: string;
  updated_at?: string;
  iterations_used?: number;
}

export interface SourceStatus {
  source_id: string;
  name: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  last_success?: string;
  last_failure?: string;
  last_error?: string;
  data_freshness: string;
  next_scheduled_refresh?: string;
}

export interface TaskStatus {
  task_id: string;
  task_type: string;
  priority: string;
  status: string;
  phase: string;
  current_iteration: number;
  iteration_budget: number;
  created_at: string;
  updated_at: string;
}
