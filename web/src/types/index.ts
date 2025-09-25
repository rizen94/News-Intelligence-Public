/**
 * News Intelligence System v3.0 - TypeScript Type Definitions
 * Centralized type definitions for the frontend application
 */

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

export interface Article {
  id: string;
  title: string;
  content: string;
  summary?: string;
  url: string;
  source: string;
  published_date: string;
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
// Storyline Types
// ============================================================================

export interface Storyline {
  id: string;
  title: string;
  description: string;
  summary?: string;
  status: 'active' | 'inactive' | 'archived';
  priority: 'low' | 'medium' | 'high' | 'critical';
  created_at: string;
  updated_at: string;
  last_activity?: string;
  article_count: number;
  tags: string[];
  category?: string;
  sentiment_score?: number;
  impact_score?: number;
  is_trending: boolean;
  is_featured: boolean;
  related_storylines?: string[];
  timeline_events?: TimelineEvent[];
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
  operator: 'equals' | 'contains' | 'startsWith' | 'endsWith' | 'gt' | 'lt' | 'gte' | 'lte';
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
