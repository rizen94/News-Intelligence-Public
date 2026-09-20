/**
 * Domain filter for v2 — query param ?domain=, not URL spine.
 */
import React from 'react';
import { useSearchParams } from 'react-router-dom';

const DOMAINS = [
  { value: '', label: 'All domains' },
  { value: 'politics', label: 'Politics' },
  { value: 'finance', label: 'Finance' },
  { value: 'legal', label: 'Legal' },
  { value: 'medicine', label: 'Medicine' },
  { value: 'artificial-intelligence', label: 'AI' },
];

export function useV2Domain(): string | null {
  const [params] = useSearchParams();
  const d = params.get('domain');
  return d && d.trim() ? d.trim().toLowerCase() : null;
}

export function DomainFilter() {
  const [params, setParams] = useSearchParams();
  const current = params.get('domain') || '';

  return (
    <label className='v2-chrome-actions' style={{ gap: '0.35rem' }}>
      <span className='v2-classic-link'>Domain</span>
      <select
        className='v2-domain-select'
        value={current}
        aria-label='Filter by domain'
        onChange={e => {
          const next = new URLSearchParams(params);
          if (e.target.value) next.set('domain', e.target.value);
          else next.delete('domain');
          // Reset page when domain changes
          next.delete('page');
          setParams(next, { replace: true });
        }}
      >
        {DOMAINS.map(d => (
          <option key={d.value || 'all'} value={d.value}>
            {d.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function withDomainQuery(path: string, domain: string | null): string {
  if (!domain) return path;
  const join = path.includes('?') ? '&' : '?';
  return `${path}${join}domain=${encodeURIComponent(domain)}`;
}
