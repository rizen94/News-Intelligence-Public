/**
 * Poll task status until complete or failed. Used by Finance Analysis flow.
 */
import { useState, useEffect, useCallback } from 'react';
import apiService from '../services/apiService';
import type { TaskStatus } from '../types/finance';

export function useTaskPolling(
  taskId: string | null,
  domain?: string,
  options?: { intervalMs?: number; maxDurationMs?: number }
) {
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const intervalMs = options?.intervalMs ?? 2000;
  const maxDurationMs = options?.maxDurationMs ?? 300000; // 5 min

  const stopPolling = useCallback(() => {
    setIsPolling(false);
  }, []);

  useEffect(() => {
    if (!taskId || !domain) return;

    let abort = false;
    const startTime = Date.now();
    setIsPolling(true);
    setError(null);

    let timeoutId: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (abort) return;
      try {
        const res = await apiService.getFinanceTaskResult(taskId, domain);
        if (abort) return;
        const data = res?.data;
        if (data?.status) {
          setStatus(data.status);
        }
        if (data?.result) {
          setResult(data.result);
        }
        const st = data?.status?.status;
        if (st === 'complete' || st === 'failed') {
          stopPolling();
          return;
        }
      } catch (err: any) {
        if (!abort) {
          setError(err?.message || 'Failed to fetch task');
        }
      }
      if (abort) return;
      if (Date.now() - startTime > maxDurationMs) {
        stopPolling();
        return;
      }
      const delay = Date.now() - startTime > 30000 ? 5000 : intervalMs;
      timeoutId = setTimeout(poll, delay);
    };

    timeoutId = setTimeout(poll, intervalMs);

    return () => {
      abort = true;
      clearTimeout(timeoutId);
    };
  }, [taskId, domain, intervalMs, maxDurationMs, stopPolling]);

  return { status, result, error, isPolling };
}
