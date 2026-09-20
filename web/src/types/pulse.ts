/** Pulse digest card types — mirrors GET /api/pulse response. */

export type PulseMovement = {
  event_id: number;
  title: string;
  event_date?: string | null;
};

export type PulseObjectKind = 'episode' | 'container' | 'package';

export type PulseCard = {
  object_kind: PulseObjectKind;
  domain_key: string;
  id: number;
  title: string;
  story_kind?: string | null;
  episode_state?: string | null;
  velocity: number;
  movement_summary: PulseMovement[];
  cross_domain_count?: number;
  container_kind?: string | null;
  score: number;
  score_breakdown: Record<string, number>;
  published_story_id?: number | null;
  movement_stub?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  episode_state_changed_at?: string | null;
};

export type PulsePayload = {
  ok: boolean;
  window_hours: number;
  limit: number;
  domain_filter?: string | null;
  items: PulseCard[];
  generated_at: string;
};
