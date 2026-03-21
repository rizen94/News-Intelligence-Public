/**
 * Editorial and report types — 5W1H editorial documents, storyline entities, report payload.
 * Aligned with backend API responses.
 */

export interface EditorialDocument {
  lede: string;
  who: Array<{ name: string; role?: string; background?: string }>;
  what: string[];
  when: string[];
  where: string[];
  why: string;
  how: string;
  outlook: string;
  key_entities: string[];
  sources: string[];
  generated_at: string | null;
  based_on_articles: number[];
  /** Legacy shape (backend may still return these) */
  developments?: string[];
  analysis?: string;
}

export interface StorylineEntity {
  canonical_entity_id: number;
  name: string;
  type: string;
  description: string;
  mention_count: number;
  has_profile: boolean;
  has_dossier: boolean;
  profile_id: number | null;
}

export interface ReportStoryline {
  id: number;
  title: string;
  editorial_document: EditorialDocument | null;
  key_actors: Array<{
    name: string;
    type: string;
    description: string;
    role_in_story?: string;
    profile_id?: number | null;
    canonical_entity_id: number;
  }>;
  phase: 'Breaking' | 'Developing' | 'Analysis';
  source_count: number;
  updated_at: string;
}

export interface ReportInvestigation {
  id: number;
  name: string;
  type: string;
  status: string;
  briefing: string | null;
}

export interface ReportRecentEvent {
  id: number;
  title: string;
  date: string;
  type: string;
}

export interface ReportPayload {
  lead_storylines: ReportStoryline[];
  investigations: ReportInvestigation[];
  recent_events: ReportRecentEvent[];
  daily_brief: string | null;
  time_of_day: 'morning' | 'midday' | 'evening' | 'weekend';
  domain: string;
}
