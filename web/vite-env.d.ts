/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** When true at build time, SPA hides mutation UI without calling /api/public/demo_config */
  readonly VITE_PUBLIC_DEMO?: string;
  /** Homelab Grafana deep link for Monitor "Open Grafana" (NI Ops dashboard). */
  readonly VITE_NEWS_INTEL_GRAFANA_URL?: string;
  readonly MODE: string;
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly SSR: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

