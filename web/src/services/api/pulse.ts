import { getApi } from './client';
import type { PulsePayload } from '@/types/pulse';

export const pulseApi = {
  async getPulse(params?: { window_hours?: number; limit?: number; domain?: string }) {
    const res = await getApi().get<{ success: boolean; data: PulsePayload; message?: string }>(
      '/api/pulse',
      { params }
    );
    return res.data;
  },
};
