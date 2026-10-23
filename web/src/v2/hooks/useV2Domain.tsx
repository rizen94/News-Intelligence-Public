/**
 * Domain filter for News — query param ?domain=, not URL spine.
 * Default (no param) = politics — same as former /v2?domain=politics home.
 * Use domain=all for cross-domain feeds.
 */
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { getDefaultDomainKey } from '../../utils/domainHelper';

const DOMAINS = [
  { value: 'all', label: 'All domains' },
  { value: 'politics', label: 'Politics' },
  { value: 'finance', label: 'Finance' },
  { value: 'legal', label: 'Legal' },
  { value: 'medicine', label: 'Medicine' },
  { value: 'artificial-intelligence', label: 'AI' },
];

/** Active domain for reader APIs. Null = all domains. */
export function useV2Domain(): string | null {
  const [params] = useSearchParams();
  if (!params.has('domain')) {
    return getDefaultDomainKey();
  }
  const d = (params.get('domain') || '').trim().toLowerCase();
  if (!d || d === 'all') {
    return null;
  }
  return d;
}

/** Value shown in the domain select. */
function selectValue(params: URLSearchParams): string {
  if (!params.has('domain')) {
    return getDefaultDomainKey();
  }
  const d = (params.get('domain') || '').trim().toLowerCase();
  if (!d || d === 'all') {
    return 'all';
  }
  return d;
}

export function DomainFilter() {
  const [params, setParams] = useSearchParams();
  const current = selectValue(params);

  return (
    <label className='v2-chrome-actions' style={{ gap: '0.35rem' }}>
      <span className='v2-classic-link'>Domain</span>
      <select
        className='v2-domain-select'
        value={current}
        aria-label='Filter by domain'
        onChange={e => {
          const next = new URLSearchParams(params);
          const v = e.target.value;
          if (v === 'all') {
            next.set('domain', 'all');
          } else if (v) {
            next.set('domain', v);
          } else {
            next.delete('domain');
          }
          next.delete('page');
          setParams(next, { replace: true });
        }}
      >
        {DOMAINS.map(d => (
          <option key={d.value} value={d.value}>
            {d.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function withDomainQuery(path: string, domain: string | null): string {
  const effective = domain ?? 'all';
  try {
    const url = new URL(path, 'https://ni.local');
    if (url.searchParams.get('domain') === effective) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
    url.searchParams.set('domain', effective);
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    if (path.includes('domain=')) return path;
    const join = path.includes('?') ? '&' : '?';
    return `${path}${join}domain=${encodeURIComponent(effective)}`;
  }
}
