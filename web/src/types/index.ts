/**
 * News Intelligence System v3.0 - TypeScript Type Definitions
 * Centralized type definitions for the frontend application
 */

import React from 'react';

export type {
  EditorialDocument,
  StorylineEntity,
  ReportStoryline,
  ReportPayload,
  ReportInvestigation,
  ReportRecentEvent,
} from './editorial';

// ============================================================================
// API Response Types
// ============================================================================

export interface APIResponse<T = any> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: {
    items: T[];
    total: number;
    page: number;
    limit: number;
    total_pages: number;
  };
  message?: string;
}

// ============================================================================
// Article Types
// ============================================================================

/** API returns source_domain / published_at; we also alias source / published_date. Use helpers below for display. */
export interface ArticleLike {
  id: number | string;
  title: string;
  content?: string;
  summary?: string;
  excerpt?: string;
  url?: string;
  /** Display source: prefer source ?? source_domain */
  source?: string;
  source_domain?: string;
  /** Display date: prefer published_date ?? published_at */
  published_date?: string;
  published_at?: string;
  created_at?: string;
  updated_at?: string;
  category?: string;
  tags?: string[];
  sentiment_score?: number;
  quality_score?: number;
  processing_status?: string;
  author?: string;
  language?: string;
  [key: string]: unknown;
}

/** Normalized display values for any article-like object (handles API naming). */
export function articleSource(a: ArticleLike): string {
  return a.source ?? a.source_domain ?? 'Unknown';
}
export function articlePublishedAt(a: ArticleLike): string | undefined {
  return a.published_date ?? a.published_at ?? a.created_at;
}
export function articleBody(a: ArticleLike): string {
  return (a.content ?? a.excerpt ?? a.summary ?? '').trim() || 'No content';
}

export interface Article {
  id: string;
  title: string;
  content: string;
  summary?: string;
  url: string;
  source: string;
  /** API may return published_at; we alias to published_date in responses */
  published_date: string;
  published_at?: string;
  source_domain?: string;
  created_at: string;
  updated_at: string;
  category?: string;
  tags?: string[];
  sentiment_score?: number;
  quality_score?: number;
  is_processed: boolean;
  is_featured: boolean;
  word_count: number;
  reading_time: number;
  author?: string;
  image_url?: string;
  language: string;
  country?: string;
}

export interface ArticleStats {
  total_articles: number;
  articles_today: number;
  articles_this_week: number;
  avg_quality_score: number;
  top_sources: Array<{
    source: string;
    count: number;
  }>;
  sentiment_distribution: {
    positive: number;
    negative: number;
    neutral: number;
  };
}

// ============================================================================
// RSS Feed Types
// ============================================================================

export interface RSSFeed {
  id: string;
  name: string;
  url: string;
  description?: string;
  is_active: boolean;
  last_updated?: string;
  error_count: number;
  last_error?: string;
  article_count: number;
  category?: string;
  language: string;
  country?: string;
  created_at: string;
  updated_at: string;
}

export interface RSSStats {
  total_feeds: number;
  active_feeds: number;
  feeds_with_errors: number;
  last_update?: string;
  total_articles_collected: number;
}

// ============================================================================
// Storyline Types (aligned with backend: storyline_crud, list/detail responses)
// ============================================================================

export interface Storyline {
  id: number;
  title: string;
  description: string | null;
  status: string;
  article_count: number;
  quality_score: number | null;
  analysis_summary: string | null;
  created_at: string;
  updated_at: string;
  last_evolution_at?: string | null;
  evolution_count?: number | null;
  editorial_document?: Record<string, unknown> | null;
  document_version?: number | null;
  document_status?: string | null;
  ml_processing_status?: string;
  top_entities?: Array<{
    name: string;
    type: string;
    description_short?: string;
  }>;
}

export interface StorylineDetail extends Storyline {
  articles: Array<{
    id: number;
    title: string;
    url?: string | null;
    source_domain?: string | null;
    published_at?: string | null;
    summary?: string | null;
  }>;
  background_information?: Record<string, unknown> | null;
  context_last_updated?: string | null;
  last_refinement?: string | null;
  key_entities?: unknown;
  entities: Array<{
    canonical_entity_id: number;
    name: string;
    type: string;
    description: string | null;
    mention_count: number;
    has_profile: boolean;
    has_dossier: boolean;
    profile_id: number | null;
  }>;
  /** ~70B finisher + stored timeline narratives (migration 181) */
  canonical_narrative?: string | null;
  narrative_finisher_model?: string | null;
  narrative_finisher_at?: string | null;
  narrative_finisher_meta?: Record<string, unknown> | null;
  timeline_narrative_chronological?: string | null;
  timeline_narrative_briefing?: string | null;
  timeline_narrative_chronological_at?: string | null;
  timeline_narrative_briefing_at?: string | null;
  refinement_jobs_pending?: string[];
}

export interface StorylineListItem extends Storyline {
  top_entities?: Array<{
    name: string;
    type: string;
    description_short?: string;
  }>;
}

export interface StorylineListResponse {
  data: StorylineListItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
  domain: string;
}

export interface TimelineEvent {
  id: string;
  storyline_id: string;
  title: string;
  description: string;
  event_date: string;
  event_type: 'article' | 'milestone' | 'analysis' | 'alert';
  source?: string;
  url?: string;
  importance: 'low' | 'medium' | 'high';
  created_at: string;
}

export interface StorylineStats {
  total_storylines: number;
  active_storylines: number;
  trending_storylines: number;
  featured_storylines: number;
  avg_sentiment_score: number;
  avg_impact_score: number;
}

// ============================================================================
// Dashboard Types
// ============================================================================

export interface DashboardData {
  system_health: {
    status: 'healthy' | 'degraded' | 'error';
    message?: string;
    last_check: string;
  };
  article_stats: {
    total: number;
    today: number;
    this_week: number;
    avg_quality: number;
  };
  rss_stats: {
    total_feeds: number;
    active_feeds: number;
    error_feeds: number;
  };
  storyline_stats: {
    total: number;
    active: number;
    trending: number;
  };
  recent_activity: ActivityItem[];
}

export interface ActivityItem {
  id: string;
  type: 'article' | 'storyline' | 'rss_feed' | 'system';
  title: string;
  description: string;
  timestamp: string;
  status: 'success' | 'warning' | 'error';
  url?: string;
}

// ============================================================================
// Pipeline Monitoring Types
// ============================================================================

export interface PipelineStatus {
  active_traces_count: number;
  active_traces: PipelineTrace[];
  system_status: 'healthy' | 'degraded' | 'error';
  timestamp: string;
}

export interface PipelineTrace {
  id: string;
  trace_id: string;
  operation: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  error_message?: string;
  metadata?: Record<string, any>;
}

export interface PipelinePerformance {
  total_traces: number;
  successful_traces: number;
  failed_traces: number;
  success_rate: number;
  average_duration_ms: number;
  total_articles_processed: number;
  total_feeds_processed: number;
  error_count: number;
  bottlenecks: string[];
  stage_performance: Record<string, number>;
}

// ============================================================================
// Intelligence Types
// ============================================================================

export interface IntelligenceInsight {
  id: string;
  type: 'trend' | 'anomaly' | 'prediction' | 'recommendation';
  title: string;
  description: string;
  confidence: number;
  impact: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  created_at: string;
  expires_at?: string;
  related_entities: string[];
  metadata?: Record<string, any>;
}

export interface MLProcessingStatus {
  pipeline_name: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  processed_items: number;
  total_items: number;
  error_message?: string;
}

// ============================================================================
// Component Props Types
// ============================================================================

export interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
}

export interface ArticleReaderProps extends BaseComponentProps {
  article: Article;
  onClose: () => void;
  onAddToStoryline: (storylineId: string) => void;
}

export interface StorylineCreationDialogProps extends BaseComponentProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (storyline: Storyline) => void;
}

export interface StorylineConfirmationDialogProps extends BaseComponentProps {
  open: boolean;
  storyline: Storyline;
  onConfirm: () => void;
  onCancel: () => void;
  action: 'delete' | 'archive' | 'activate';
}

// ============================================================================
// API Service Types
// ============================================================================

export interface APIConfig {
  baseURL: string;
  timeout: number;
  headers: Record<string, string>;
}

export interface APIError {
  message: string;
  status?: number;
  data?: any;
  url?: string;
}

// ============================================================================
// Search Types
// ============================================================================

export interface SearchParams {
  q: string;
  category?: string;
  source?: string;
  date_from?: string;
  date_to?: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  page?: number;
  limit?: number;
  sort_by?: 'date' | 'relevance' | 'quality' | 'sentiment';
  sort_order?: 'asc' | 'desc';
}

export interface SearchResult {
  id: string;
  title: string;
  content: string;
  url: string;
  source: string;
  published_date: string;
  relevance_score: number;
  snippet: string;
}

export interface SearchResponse {
  success: boolean;
  data: {
    results: SearchResult[];
    total: number;
    query: string;
    facets?: Record<string, any>;
  };
}

// ============================================================================
// Utility Types
// ============================================================================

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface LoadingProps {
  loading: boolean;
  error?: string | null;
  children: React.ReactNode;
}

export type SortDirection = 'asc' | 'desc';

export interface SortConfig {
  key: string;
  direction: SortDirection;
}

export interface FilterConfig {
  key: string;
  value: any;
  operator:
    | 'equals'
    | 'contains'
    | 'startsWith'
    | 'endsWith'
    | 'gt'
    | 'lt'
    | 'gte'
    | 'lte';
}

// ============================================================================
// Event Types
// ============================================================================

export interface UserAction {
  type: string;
  payload: any;
  timestamp: string;
  userId?: string;
}

export interface SystemEvent {
  type: 'info' | 'warning' | 'error' | 'success';
  message: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

// ============================================================================
// Theme Types
// ============================================================================

export interface ThemeConfig {
  mode: 'light' | 'dark';
  primaryColor: string;
  secondaryColor: string;
  fontFamily: string;
}

// ============================================================================
// Export all types
// ============================================================================

export * from './api';
export * from './components';
export * from './utils';
