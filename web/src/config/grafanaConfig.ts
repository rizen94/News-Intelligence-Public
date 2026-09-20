/**
 * Homelab Grafana deep-link for Monitor "Open Grafana".
 *
 * Prefer build-time VITE_NEWS_INTEL_GRAFANA_URL. Optional localStorage override
 * for operators without a rebuild. Documented as NEWS_INTEL_GRAFANA_URL in env
 * examples (set the same value into Vite at build, or paste into localStorage).
 */
const STORAGE_KEY = 'news_intel_grafana_url';

/** Default Homelab NI Ops dashboard path (UID from committed JSON). Override via env. */
export const DEFAULT_GRAFANA_OPS_PATH =
  '/d/ni-ops/news-intelligence-ops';

export function getGrafanaOpsUrl(): string | null {
  if (typeof window !== 'undefined') {
    try {
      const stored = (localStorage.getItem(STORAGE_KEY) || '').trim();
      if (stored) return stored;
    } catch {
      /* private mode */
    }
  }
  const fromEnv = (import.meta.env.VITE_NEWS_INTEL_GRAFANA_URL || '').trim();
  return fromEnv || null;
}
