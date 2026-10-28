/**
 * Situations index — vault cluster hubs (living situation pages).
 */
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useV2Domain, withDomainQuery } from '../../hooks/useV2Domain';
import { fetchVaultHubs } from '../../services/readerApi';
import { stripReaderMdMarkers } from '../../../utils/sanitizeSnippet';

type HubRow = {
  id: number;
  domain_key?: string;
  title?: string;
  cluster_key?: string;
  href?: string;
  current_brief?: string | null;
  updated_at?: string | null;
  member_storyline_ids?: number[];
  tags?: string[];
};

export default function SituationsPage() {
  const domain = useV2Domain();
  const [hubs, setHubs] = useState<HubRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setPending(true);
    setError(null);
    fetchVaultHubs(domain)
      .then(res => {
        if (cancelled) return;
        setHubs((res.hubs || []) as HubRow[]);
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load situations');
      })
      .finally(() => {
        if (!cancelled) setPending(false);
      });
    return () => {
      cancelled = true;
    };
  }, [domain]);

  return (
    <div>
      <p className='v2-section-label'>Situations</p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.5rem',
        }}
      >
        Living situations
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '36rem' }}>
        Cluster hubs that index related episodes by shared entities, tags, and
        events — open a situation for the current brief and member arcs.
      </p>
      <div className='v2-hero-rule' />

      {error ? <p className='v2-empty'>{error}</p> : null}
      {pending && !hubs.length ? <p className='v2-empty'>Loading…</p> : null}
      {!pending && !error && hubs.length === 0 ? (
        <p className='v2-empty'>
          No situations indexed yet
          {domain ? ` for ${domain}` : ''}. They appear here once vault cluster
          hubs are seeded.
        </p>
      ) : null}

      <div className='v2-cascade'>
        {hubs.map((h, i) => {
          const members = (h.member_storyline_ids || []).length;
          const href = withDomainQuery(
            h.href || `/hubs/${h.cluster_key || h.id}`,
            h.domain_key || domain
          );
          const brief = stripReaderMdMarkers(h.current_brief || '').slice(0, 280);
          return (
            <article
              key={h.id}
              className={`v2-story-unit ${
                i === 0 ? 'v2-story-unit--hero' : i < 3 ? 'v2-story-unit--lead' : 'v2-story-unit--secondary'
              }`}
            >
              <div className='v2-story-kicker'>
                Situation
                {h.domain_key ? ` · ${h.domain_key.toUpperCase()}` : ''}
              </div>
              <h2 className='v2-story-headline'>
                <Link to={href}>{h.title || h.cluster_key || `Hub ${h.id}`}</Link>
              </h2>
              {brief ? <p className='v2-story-dek'>{brief}</p> : null}
              <div className='v2-story-meta'>
                <span>{members} member episodes</span>
                {h.updated_at ? (
                  <>
                    <span className='v2-meta-sep' aria-hidden='true'>
                      ·
                    </span>
                    <span>Updated {String(h.updated_at).slice(0, 10)}</span>
                  </>
                ) : null}
                <span className='v2-meta-sep' aria-hidden='true'>
                  ·
                </span>
                <span className='v2-badge'>situation</span>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
