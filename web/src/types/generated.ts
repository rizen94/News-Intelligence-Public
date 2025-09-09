/*
 * Generated TypeScript Types from Unified Schema
 * Version: 3.1.0
 * Generated: 2025-09-09T15:15:21.750484
 */

export interface Article {
  id: number;
  title: string;
  content: string?;
  url: string?;
  published_at: string?;
  source: string?;
  category: string?;
  status: string;
  tags: string[]?;
  created_at: string;
  updated_at: string;
  sentiment_score: number?;
  entities: Record<string, any>?;
  readability_score: number?;
  quality_score: number?;
  summary: string?;
  ml_data: Record<string, any>?;
  language: string?;
  word_count: number?;
  reading_time: number?;
  feed_id: number?;
}
export interface RSSFeed {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
  last_fetched: string?;
  fetch_interval: number?;
  created_at: string;
  updated_at: string;
  error_count: number?;
  last_error: string?;
}