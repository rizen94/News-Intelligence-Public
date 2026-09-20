/**
 * Light entity dossier page for Wikipedia-style links from the reader rail.
 */
import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { getApi } from '../../../services/api/client';

export default function EntityDossierPage() {
  const { id } = useParams<{ id: string }>();
  const [params] = useSearchParams();
  const domain = params.get('domain') || 'politics';
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const api = getApi();
    Promise.all([
      api
        .get('/api/entity_dossiers', { params: { entity_id: id, domain_key: domain } })
        .catch(() => ({ data: null })),
      api
        .get(`/api/synthesis/entity/${id}`, { params: { domain_key: domain } })
        .catch(() => ({ data: null })),
    ])
      .then(([dossier, synthesis]) => {
        if (cancelled) return;
        setData({
          dossier: dossier.data,
          synthesis: synthesis.data,
        });
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load entity');
      });
    return () => {
      cancelled = true;
    };
  }, [id, domain]);

  const synth = (data?.synthesis || {}) as Record<string, unknown>;
  const name =
    (synth.name as string) ||
    (synth.entity_name as string) ||
    `Entity ${id}`;

  return (
    <div>
      <p className='v2-section-label'>Entity dossier</p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.75rem',
        }}
      >
        {name}
      </h1>
      <div className='v2-hero-rule' />
      <p>
        <Link to='/v2'>← Home</Link>
      </p>
      {error ? <p className='v2-empty'>{error}</p> : null}
      {!data && !error ? <p className='v2-empty'>Loading…</p> : null}
      {data ? (
        <pre
          style={{
            whiteSpace: 'pre-wrap',
            fontSize: '0.8rem',
            color: 'var(--v2-ink-muted)',
            maxWidth: '42rem',
          }}
        >
          {JSON.stringify(data, null, 2).slice(0, 8000)}
        </pre>
      ) : null}
    </div>
  );
}
