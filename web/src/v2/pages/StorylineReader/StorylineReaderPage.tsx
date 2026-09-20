/**
 * Longform storyline reader — summary, timeline, citations, dossier rail.
 * Interactive: breadcrumbs, prev/next from last feed, j/k keyboard nav.
 */
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Breadcrumb,
  feedNavNeighbors,
  rememberFeedNav,
} from '../../components/PaginationBar';
import { withDomainQuery } from '../../hooks/useV2Domain';
import {
  fetchReaderHome,
  fetchReaderStoryline,
  type ReaderPackResponse,
} from '../../services/readerApi';

function DossierTree({ nodes }: { nodes: Array<Record<string, unknown>> }) {
  if (!nodes?.length) return null;
  return (
    <ul>
      {nodes.map((n, i) => {
        const name = String(n.name || 'Entity');
        const href = n.href ? String(n.href) : null;
        const children = (n.children as Array<Record<string, unknown>>) || [];
        return (
          <li key={String(n.id ?? i)} className='v2-dossier-item'>
            {href ? <Link to={href}>{name}</Link> : <strong>{name}</strong>}
            {n.who ? (
              <div style={{ color: 'var(--v2-ink-muted)' }}>{String(n.who)}</div>
            ) : null}
            {children.length ? <DossierTree nodes={children} /> : null}
          </li>
        );
      })}
    </ul>
  );
}

export default function StorylineReaderPage() {
  const { domain, id } = useParams<{ domain: string; id: string }>();
  const navigate = useNavigate();
  const [pack, setPack] = useState<ReaderPackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [navTick, setNavTick] = useState(0);

  useEffect(() => {
    if (!domain || !id) return;
    let cancelled = false;
    setError(null);
    setPack(null);
    fetchReaderStoryline(id, domain)
      .then(res => {
        if (!cancelled) setPack(res);
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load storyline');
      });
    return () => {
      cancelled = true;
    };
  }, [domain, id]);

  // Seed prev/next from the news feed when the user deep-links (no session nav).
  useEffect(() => {
    if (!domain || !id) return;
    if (feedNavNeighbors(domain, Number(id)).index >= 0) return;
    let cancelled = false;
    fetchReaderHome(domain, { page: 1, pageSize: 24, section: 'news' })
      .then(res => {
        if (cancelled) return;
        const ids = (res.nav_ids || []).map(n => ({
          ...n,
          href: withDomainQuery(n.href, n.domain || domain),
        }));
        if (!ids.length) return;
        rememberFeedNav('news', ids);
        setNavTick(t => t + 1);
      })
      .catch(() => {
        /* non-fatal — reader body still loads */
      });
    return () => {
      cancelled = true;
    };
  }, [domain, id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const nav = domain && id ? feedNavNeighbors(domain, Number(id)) : null;
      if (e.key === 'j' || e.key === 'ArrowRight') {
        if (nav?.next) {
          e.preventDefault();
          navigate(nav.next.href);
        }
      } else if (e.key === 'k' || e.key === 'ArrowLeft') {
        if (nav?.prev) {
          e.preventDefault();
          navigate(nav.prev.href);
        }
      } else if (e.key === 'Escape') {
        navigate(withDomainQuery('/v2/news', domain || null));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate, domain, id, navTick]);

  const nav =
    domain && id
      ? feedNavNeighbors(domain, Number(id))
      : { prev: null, next: null, index: -1, total: 0 };
  void navTick;

  if (error) {
    return (
      <div>
        <Breadcrumb
          crumbs={[
            { label: 'Home', to: withDomainQuery('/v2', domain || null) },
            { label: 'News', to: withDomainQuery('/v2/news', domain || null) },
            { label: 'Error' },
          ]}
        />
        <p className='v2-empty'>{error}</p>
        <Link to={withDomainQuery('/v2', domain || null)}>← Home</Link>
      </div>
    );
  }

  if (!pack) {
    return <p className='v2-empty'>Loading reader…</p>;
  }

  const events = pack.timeline?.events || [];
  const citations = pack.citations || [];
  const tree = (pack.dossier_rail?.tree || pack.dossier_rail?.entities || []) as Array<
    Record<string, unknown>
  >;
  const hierarchy = pack.dossier_rail?.hierarchy || {};
  const pull =
    pack.lede ||
    (typeof pack.editorial_document?.what === 'string'
      ? pack.editorial_document.what
      : null);

  return (
    <div>
      <Breadcrumb
        crumbs={[
          { label: 'Home', to: withDomainQuery('/v2', domain || null) },
          { label: 'News', to: withDomainQuery('/v2/news', domain || null) },
          { label: (domain || '').toUpperCase() },
          { label: pack.title.slice(0, 48) + (pack.title.length > 48 ? '…' : '') },
        ]}
      />

      <div className='v2-reader-nav' role='navigation' aria-label='Story navigation'>
        {nav.prev ? (
          <Link className='v2-reader-nav-link' to={nav.prev.href}>
            ← Previous
          </Link>
        ) : (
          <span className='v2-reader-nav-link is-disabled'>← Previous</span>
        )}
        <span className='v2-pager-meta'>
          {nav.index >= 0 ? `${nav.index + 1} / ${nav.total}` : 'From feed'}
          <span style={{ marginLeft: '0.5rem', opacity: 0.7 }}>
            {' '}
            j/k or ←/→
          </span>
        </span>
        {nav.next ? (
          <Link className='v2-reader-nav-link' to={nav.next.href}>
            Next →
          </Link>
        ) : (
          <span className='v2-reader-nav-link is-disabled'>Next →</span>
        )}
      </div>

      <div className='v2-reader-layout'>
        <article className='v2-reader-body'>
          <p className='v2-section-label'>
            {(domain || '').toUpperCase()} · Storyline
          </p>
          <h1>{pack.title}</h1>
          <div className='v2-hero-rule' />
          <div className='v2-story-meta' style={{ marginBottom: '1.25rem' }}>
            {pack.updated_at ? (
              <span>Updated {pack.updated_at.slice(0, 10)}</span>
            ) : null}
            {pack.article_count != null ? (
              <span>{pack.article_count} sources</span>
            ) : null}
            {pack.status ? <span>{pack.status}</span> : null}
          </div>

          {pull ? <blockquote className='v2-pull-quote'>{pull}</blockquote> : null}

          <section>
            <h2 className='v2-section-label'>Summary</h2>
            <p style={{ whiteSpace: 'pre-wrap' }}>
              {pack.summary || 'No summary yet.'}
            </p>
          </section>

          {pack.background_information ? (
            <section>
              <hr className='v2-section-rule' />
              <h2 className='v2-section-label'>Background</h2>
              <p style={{ whiteSpace: 'pre-wrap' }}>{pack.background_information}</p>
            </section>
          ) : null}

          <section>
            <hr className='v2-section-rule' />
            <h2 className='v2-section-label'>Timeline</h2>
            {events.length === 0 ? (
              <p className='v2-empty'>No timeline events yet.</p>
            ) : (
              <ol className='v2-timeline'>
                {events.map((ev, i) => (
                  <li key={String(ev.id ?? i)}>
                    <div className='v2-story-kicker'>
                      {String(ev.event_date || ev.actual_event_date || 'Undated')}
                    </div>
                    <strong style={{ fontFamily: 'var(--v2-font-display)' }}>
                      {String(ev.title || 'Event')}
                    </strong>
                    {ev.description ? (
                      <p
                        style={{
                          margin: '0.25rem 0 0',
                          color: 'var(--v2-ink-muted)',
                        }}
                      >
                        {String(ev.description)}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section>
            <hr className='v2-section-rule' />
            <h2 className='v2-section-label'>Citations</h2>
            {citations.length === 0 ? (
              <p className='v2-empty'>No member articles.</p>
            ) : (
              <ul style={{ paddingLeft: '1.1rem' }}>
                {citations.map(c => (
                  <li key={c.id} style={{ marginBottom: '0.65rem' }}>
                    {c.url ? (
                      <a href={c.url} target='_blank' rel='noreferrer'>
                        {c.title}
                      </a>
                    ) : (
                      c.title
                    )}
                    <div
                      style={{ fontSize: '0.8rem', color: 'var(--v2-ink-muted)' }}
                    >
                      {[c.source_domain, c.published_at?.slice(0, 10)]
                        .filter(Boolean)
                        .join(' · ')}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </article>

        <aside className='v2-dossier-rail' aria-label='Dossier'>
          <h3>Dossier</h3>
          <p style={{ color: 'var(--v2-ink-muted)', fontSize: '0.8rem' }}>
            Who / what / why · hierarchy
          </p>
          {hierarchy &&
          (hierarchy as { is_mega_storyline?: boolean }).is_mega_storyline ? (
            <p className='v2-badge'>Mega storyline</p>
          ) : null}
          {Array.isArray((hierarchy as { children?: unknown[] }).children) &&
          (
            hierarchy as {
              children: Array<{ id: number; title: string; href?: string }>;
            }
          ).children.length > 0 ? (
            <div style={{ marginBottom: '1rem' }}>
              <div className='v2-story-kicker'>Child arcs</div>
              <ul style={{ paddingLeft: '1rem', margin: '0.35rem 0' }}>
                {(
                  hierarchy as {
                    children: Array<{ id: number; title: string; href?: string }>;
                  }
                ).children.map(ch => (
                  <li key={ch.id}>
                    <Link to={ch.href || `/v2/storylines/${domain}/${ch.id}`}>
                      {ch.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <DossierTree nodes={tree} />
          {!tree.length ? <p className='v2-empty'>No entities linked yet.</p> : null}
        </aside>
      </div>
    </div>
  );
}
