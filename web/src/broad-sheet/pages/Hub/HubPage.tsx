/**
 * Situation reader — elevated vault cluster hub with current brief.
 */
import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { withDomainQuery } from '../../hooks/useV2Domain';
import {
  fetchVaultHub,
  type VaultHubPackResponse,
} from '../../services/readerApi';
import { stripReaderMdMarkers } from '../../../utils/sanitizeSnippet';

export default function HubPage() {
  const { idOrSlug } = useParams<{ idOrSlug: string }>();
  const [pack, setPack] = useState<VaultHubPackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showNote, setShowNote] = useState(false);

  useEffect(() => {
    if (!idOrSlug) return;
    let cancelled = false;
    setError(null);
    setPack(null);
    setShowNote(false);
    fetchVaultHub(idOrSlug)
      .then(res => {
        if (!cancelled) setPack(res);
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load situation');
      });
    return () => {
      cancelled = true;
    };
  }, [idOrSlug]);

  const hub = pack?.hub;
  const brief =
    stripReaderMdMarkers(pack?.current_brief || hub?.current_brief || '') ||
    null;
  const noteBody = stripReaderMdMarkers(
    (pack?.note as { body?: string; markdown?: string; content?: string } | undefined)
      ?.body ||
      (pack?.note as { markdown?: string } | undefined)?.markdown ||
      (pack?.note as { content?: string } | undefined)?.content ||
      ''
  );
  const siblings = pack?.sibling_hubs || [];
  const memberDekBullets = (pack?.members || [])
    .map(m => stripReaderMdMarkers(m.dek || '').trim())
    .filter(Boolean)
    .slice(0, 3);

  return (
    <div>
      <p className='v2-section-label'>
        <Link to={withDomainQuery('/', hub?.domain_key || null)}>Home</Link>
        {' · '}
        <Link to={withDomainQuery('/hubs', hub?.domain_key || null)}>
          Situations
        </Link>
        {' · '}
        Situation
      </p>
      {error ? <p className='v2-empty'>{error}</p> : null}
      {!pack && !error ? <p className='v2-empty'>Loading…</p> : null}
      {hub ? (
        <>
          <h1 className='v2-story-headline' style={{ fontSize: '1.75rem' }}>
            {hub.title}
          </h1>
          <p className='v2-story-dek'>
            {(hub.member_storyline_ids || []).length} member episodes
            {hub.domain_key ? ` · ${hub.domain_key}` : ''}
            {hub.brief_updated_at
              ? ` · brief ${(hub.brief_updated_at || '').slice(0, 10)}`
              : ''}
          </p>

          <hr className='v2-section-rule' />
          <h2 className='v2-section-label'>Current brief</h2>
          {brief ? (
            <div
              className='v2-story-dek'
              style={{ whiteSpace: 'pre-wrap', fontSize: '1.05rem', lineHeight: 1.5 }}
            >
              {brief}
            </div>
          ) : (
            <p className='v2-empty'>
              Brief not ready yet — open again after the next hub refresh, or wait
              while evidence accumulates.
            </p>
          )}

          {memberDekBullets.length > 0 ? (
            <>
              <hr className='v2-section-rule' />
              <h2 className='v2-section-label'>Now / watch</h2>
              <ul style={{ paddingLeft: '1.1rem', margin: 0 }}>
                {memberDekBullets.map((line, i) => (
                  <li
                    key={i}
                    style={{
                      marginBottom: '0.4rem',
                      color: 'var(--v2-ink-muted)',
                    }}
                  >
                    {line.slice(0, 220)}
                    {line.length > 220 ? '…' : ''}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          <hr className='v2-section-rule' />
          <h2 className='v2-section-label'>Member episodes</h2>
          <div className='v2-rail-list'>
            {(pack?.members || []).length === 0 ? (
              <p className='v2-empty'>No active members.</p>
            ) : (
              (pack?.members || []).map(m => (
                <article
                  key={m.storyline_id}
                  className='v2-story-unit v2-story-unit--secondary'
                >
                  <h3 className='v2-story-headline' style={{ fontSize: '1.1rem' }}>
                    <Link
                      to={withDomainQuery(
                        m.href || `/storylines/${m.domain}/${m.storyline_id}`,
                        m.domain
                      )}
                    >
                      {m.headline}
                    </Link>
                  </h3>
                  {m.dek ? <p className='v2-story-dek'>{m.dek}</p> : null}
                  <div className='v2-story-meta'>
                    {m.article_count != null ? `${m.article_count} articles` : null}
                  </div>
                </article>
              ))
            )}
          </div>

          <hr className='v2-section-rule' />
          <h2 className='v2-section-label'>Timeline</h2>
          {(pack?.timeline || []).length === 0 ? (
            <p className='v2-empty'>No recent member articles yet.</p>
          ) : (
            <ul className='v2-rail-list'>
              {(pack?.timeline || []).map(ev => (
                <li
                  key={`${ev.article_id}-${ev.storyline_id}`}
                  style={{ marginBottom: '0.5rem' }}
                >
                  <span style={{ color: 'var(--v2-ink-muted)' }}>
                    {(ev.published_at || '').slice(0, 10) || 'undated'}
                  </span>
                  {' — '}
                  {ev.url ? (
                    <a href={ev.url} target='_blank' rel='noreferrer'>
                      {ev.title}
                    </a>
                  ) : (
                    ev.title
                  )}
                  <span style={{ color: 'var(--v2-ink-muted)' }}>
                    {' '}
                    (
                    <Link
                      to={withDomainQuery(
                        `/storylines/${hub.domain_key}/${ev.storyline_id}`,
                        hub.domain_key
                      )}
                    >
                      ep {ev.storyline_id}
                    </Link>
                    )
                  </span>
                </li>
              ))}
            </ul>
          )}

          {(pack?.vault_context_pack?.notes || []).length ? (
            <>
              <hr className='v2-section-rule' />
              <h2 className='v2-section-label'>Vault context</h2>
              <ul>
                {(pack?.vault_context_pack?.notes || []).map((n, i) => (
                  <li key={String(n.vault_path || n.title || i)}>
                    <strong>{n.title || 'Note'}</strong>
                    {n.significance_excerpt ? (
                      <div style={{ color: 'var(--v2-ink-muted)' }}>
                        {stripReaderMdMarkers(
                          String(n.significance_excerpt)
                        ).slice(0, 220)}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {siblings.length > 0 ? (
            <>
              <hr className='v2-section-rule' />
              <h2 className='v2-section-label'>Related situations</h2>
              <ul style={{ paddingLeft: '1.1rem' }}>
                {siblings.map(s => (
                  <li key={s.id} style={{ marginBottom: '0.5rem' }}>
                    <Link
                      to={withDomainQuery(
                        s.href || `/hubs/${s.cluster_key || s.id}`,
                        hub.domain_key
                      )}
                    >
                      {s.title || s.cluster_key || `Hub ${s.id}`}
                    </Link>
                    <span style={{ color: 'var(--v2-ink-muted)', fontSize: '0.85rem' }}>
                      {s.member_count != null
                        ? ` · ${s.member_count} episodes`
                        : ''}
                    </span>
                    {s.current_brief ? (
                      <div
                        style={{
                          color: 'var(--v2-ink-muted)',
                          fontSize: '0.9rem',
                          marginTop: '0.15rem',
                        }}
                      >
                        {stripReaderMdMarkers(s.current_brief).slice(0, 160)}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {noteBody ? (
            <>
              <hr className='v2-section-rule' />
              <button
                type='button'
                className='v2-reader-nav-link'
                onClick={() => setShowNote(v => !v)}
                style={{
                  border: '1px solid var(--v2-rule, var(--v2-hairline))',
                  background: 'transparent',
                  cursor: 'pointer',
                  padding: '0.35rem 0.75rem',
                  fontFamily: 'inherit',
                }}
              >
                {showNote ? 'Hide full vault note' : 'Full vault note'}
              </button>
              {showNote ? (
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'inherit',
                    fontSize: '0.9rem',
                    lineHeight: 1.45,
                    marginTop: '0.75rem',
                  }}
                >
                  {String(noteBody).slice(0, 8000)}
                </pre>
              ) : null}
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
