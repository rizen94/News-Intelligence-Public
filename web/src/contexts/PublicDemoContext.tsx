/**
 * Public read-only demo mode — mirrors API NEWS_INTEL_DEMO_* for this Host.
 * Build with VITE_PUBLIC_DEMO=true to force readonly without calling the API.
 */
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

type PublicDemoValue = {
  readonly: boolean;
  loading: boolean;
};

const PublicDemoContext = createContext<PublicDemoValue>({
  readonly: false,
  loading: true,
});

export const PublicDemoProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [readonly, setReadonly] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (import.meta.env.VITE_PUBLIC_DEMO === 'true') {
      setReadonly(true);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetch('/api/public/demo_config', { credentials: 'same-origin' })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (cancelled || !data) return;
        const ro = data?.data?.readonly === true;
        setReadonly(ro);
      })
      .catch(() => {
        if (!cancelled) setReadonly(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({ readonly, loading }),
    [readonly, loading]
  );

  return (
    <PublicDemoContext.Provider value={value}>
      {children}
    </PublicDemoContext.Provider>
  );
};

export function usePublicDemoMode(): PublicDemoValue {
  return useContext(PublicDemoContext);
}
