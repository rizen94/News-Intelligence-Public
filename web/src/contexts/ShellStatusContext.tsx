/**
 * Single shell-level poller for health, orchestrator status, and context-centric counts.
 * Hero, APIConnectionStatus, and Monitor reuse this instead of duplicate 60s intervals.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import {
  contextCentricApi,
  type ContextCentricStatus,
} from '../services/api/contextCentric';
import apiService from '../services/apiService';

export type ShellHealth = {
  status?: string;
  services?: Record<string, string>;
};

export type ShellOrchStatus = {
  running?: boolean;
  last_collection_times?: Record<string, string>;
  collection_sources?: string[];
};

type ShellStatusContextValue = {
  health: ShellHealth | null;
  orchStatus: ShellOrchStatus | null;
  ctxStatus: ContextCentricStatus | null;
  lastFetch: Date | null;
  apiConnected: boolean;
  refresh: () => Promise<void>;
};

const ShellStatusContext = createContext<ShellStatusContextValue | undefined>(
  undefined
);

const POLL_MS = 60_000;

export const ShellStatusProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [health, setHealth] = useState<ShellHealth | null>(null);
  const [orchStatus, setOrchStatus] = useState<ShellOrchStatus | null>(null);
  const [ctxStatus, setCtxStatus] = useState<ContextCentricStatus | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const [apiConnected, setApiConnected] = useState(false);

  const refresh = useCallback(async () => {
    const orchPromise = (async () => {
      try {
        const fn = apiService.getOrchestratorDashboard;
        if (typeof fn !== 'function') return null;
        const d = await fn.call(apiService, { decision_log_limit: 1 });
        return (d as { status?: ShellOrchStatus } | null)?.status ?? null;
      } catch {
        return null;
      }
    })();

    const [h, o, c] = await Promise.all([
      apiService.getHealth().catch(() => null),
      orchPromise,
      contextCentricApi.getStatus(null).catch(() => null),
    ]);

    if (h && typeof h === 'object') {
      setHealth(h as ShellHealth);
      setApiConnected(true);
    } else {
      setApiConnected(false);
    }
    if (o && typeof o === 'object') setOrchStatus(o);
    if (c && typeof c === 'object') setCtxStatus(c);
    setLastFetch(new Date());
  }, []);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!cancelled) await refresh();
    };
    void run();
    const t = setInterval(() => {
      void run();
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [refresh]);

  return (
    <ShellStatusContext.Provider
      value={{
        health,
        orchStatus,
        ctxStatus,
        lastFetch,
        apiConnected,
        refresh,
      }}
    >
      {children}
    </ShellStatusContext.Provider>
  );
};

export function useShellStatus(): ShellStatusContextValue {
  const ctx = useContext(ShellStatusContext);
  if (!ctx) {
    throw new Error('useShellStatus must be used within ShellStatusProvider');
  }
  return ctx;
}

/** Optional hook for components outside MainLayout (e.g. login) — returns null when absent. */
export function useShellStatusOptional(): ShellStatusContextValue | null {
  return useContext(ShellStatusContext) ?? null;
}
