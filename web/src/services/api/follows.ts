import { getApi } from './client';
import type { FollowItem, FollowMovementItem } from '@/types/follows';

export const followsApi = {
  async follow(body: {
    object_kind: string;
    domain_key?: string | null;
    object_id: number;
    tier?: string;
    notify_on?: string;
    user_key?: string;
  }) {
    const res = await getApi().post<{ success: boolean; data: FollowItem }>('/api/follows', body);
    return res.data;
  },

  async list(params?: { tier?: string; include_archived?: boolean; user_key?: string }) {
    const res = await getApi().get<{ success: boolean; data: FollowItem[] }>('/api/follows', {
      params,
    });
    return res.data;
  },

  async movement(params?: { window_hours?: number; user_key?: string }) {
    const res = await getApi().get<{ success: boolean; data: FollowMovementItem[] }>(
      '/api/follows/movement',
      { params }
    );
    return res.data;
  },

  async markRead(followId: number, userKey = 'operator') {
    const res = await getApi().post<{ success: boolean; data: FollowItem }>(
      `/api/follows/${followId}/read`,
      null,
      { params: { user_key: userKey } }
    );
    return res.data;
  },

  async unfollow(followId: number, userKey = 'operator') {
    const res = await getApi().delete<{ success: boolean; data: FollowItem }>(
      `/api/follows/${followId}`,
      { params: { user_key: userKey } }
    );
    return res.data;
  },

  async patch(
    followId: number,
    body: {
      tier?: string;
      notify_on?: string;
      status?: string;
      promote_living?: boolean;
      demote_quiet?: boolean;
    },
    userKey = 'operator'
  ) {
    const res = await getApi().patch<{ success: boolean; data: FollowItem | Record<string, unknown> }>(
      `/api/follows/${followId}`,
      body,
      { params: { user_key: userKey } }
    );
    return res.data;
  },
};
