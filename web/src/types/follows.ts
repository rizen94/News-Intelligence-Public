/** Follow registry types — mirrors /api/follows responses. */

export type FollowTier = 'quiet' | 'living';
export type FollowStatus = 'active' | 'paused' | 'archived';
export type FollowNotifyOn = 'any_movement' | 'state_change' | 'republish';

export type FollowItem = {
  id: number;
  object_kind: 'episode' | 'container' | 'package';
  domain_key?: string | null;
  object_id: number;
  tier: FollowTier;
  user_key: string;
  notify_on: FollowNotifyOn;
  status: FollowStatus;
  last_surfaced_at?: string | null;
  last_read_at?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

export type FollowMovementItem = FollowItem & {
  follow_id: number;
  title: string;
  score?: number;
  velocity?: number;
  movement_summary?: { event_id: number; title: string; event_date?: string | null }[];
  published_story_id?: number | null;
};
