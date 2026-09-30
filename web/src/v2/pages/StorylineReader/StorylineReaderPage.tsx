/**
 * Longform storyline reader — summary, timeline, citations, dossier rail.
 * Interactive: breadcrumbs, prev/next from last feed, j/k keyboard nav.
 */
import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
import { articlesApi } from '../../../services/api/articles';

function MetaSep() {
  return (
    <span className='v2-meta-sep' aria-hidden='true'>
      ·
    </span>
  );
}

function ReaderMarkdown({ source }: { source: string }) {
  const text = (source || '').trim();
  if (!text) return null;
  return (
    <div className='v2-reader-md'>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

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
  const [pullLoading, setPullLoading] = useState(false);
  const [pullStatus, setPullStatus] = useState<string | null>(null);
  const [pullSummary, setPullSummary] = useState<string | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);
  const [pullArticleId, setPullArticleId] = useState<number | null>(null);
  const [pullActors, setPullActors] = useState<string[]>([]);
  const [pullNoteCount, setPullNoteCount] = useState(0);

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
        navigate(withDomainQuery('/news', domain || null));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate, domain, id, navTick]);

  useEffect(() => {
    setPullSummary(null);
    setPullError(null);
    setPullStatus(null);
    setPullArticleId(null);
    setPullActors([]);
    setPullNoteCount(0);
    setPullLoading(false);
  }, [domain, id]);

  const applyReadyPull = (st: Record<string, unknown>) => {
    if (st.summary_markdown) {
      setPullSummary(String(st.summary_markdown));
    }
    setPullStatus(String(st.status || 'ready'));
    setPullActors(
      Array.isArray(st.vault_actors)
        ? (st.vault_actors as unknown[]).map(String)
        : Array.isArray((st.context_meta as { vault_actors?: unknown[] } | undefined)?.vault_actors)
          ? ((st.context_meta as { vault_actors: unknown[] }).vault_actors).map(String)
          : []
    );
    setPullNoteCount(
      Number(
        st.vault_note_count ||
          (st.context_meta as { vault_note_count?: number } | undefined)?.vault_note_count ||
          0
      )
    );
    if (st.article_id) setPullArticleId(Number(st.article_id));
    setPullLoading(false);
  };

  const pollPull = async (pullId: number | string) => {
    for (let i = 0; i < 90; i++) {
      await new Promise(r => setTimeout(r, 2000));
      const st = await articlesApi.getContextPull(pullId);
      if (!st || st.ok === false) continue;
      setPullStatus(String(st.status || ''));
      if (st.status === 'ready' && st.summary_markdown) {
        applyReadyPull(st as Record<string, unknown>);
        return;
      }
      if (st.status === 'failed') {
        setPullError(st.error_message || 'Pull context failed');
        setPullLoading(false);
        return;
      }
    }
    setPullError('Timed out waiting for context brief');
    setPullLoading(false);
  };

  /** Cache-first: if enqueue already returned ready + summary, show it; only poll pending jobs. */
  const handlePullResponse = async (res: Record<string, unknown>) => {
    const pullId = (res?.pull_id || res?.id) as number | string | undefined;
    if (!pullId) {
      setPullError(String(res?.error || 'Failed to start pull context'));
      setPullLoading(false);
      return;
    }
    if (res.article_id) setPullArticleId(Number(res.article_id));
    const readyCached =
      (res.cached === true || res.status === 'ready') && res.summary_markdown;
    if (readyCached) {
      applyReadyPull(res);
      return;
    }
    if (res.status === 'ready' && !res.summary_markdown) {
      // Deferred / empty ready — fetch once rather than polling a running job
      const st = await articlesApi.getContextPull(pullId);
      if (st?.status === 'ready') {
        applyReadyPull(st as Record<string, unknown>);
        if (!st.summary_markdown) {
          setPullSummary(
            '_No primed expansion yet. Check back after the morning vault prime._'
          );
        }
        return;
      }
    }
    setPullStatus(String(res.status || 'pending'));
    await pollPull(pullId);
  };

  const runStorylinePull = async () => {
    if (!domain || !id) return;
    setPullLoading(true);
    setPullError(null);
    setPullStatus('pending');
    setPullSummary(null);
    setPullActors([]);
    try {
      const res = await articlesApi.pullStorylineContext(id, domain);
      await handlePullResponse((res || {}) as Record<string, unknown>);
    } catch (e: unknown) {
      setPullError(e instanceof Error ? e.message : 'Failed');
      setPullLoading(false);
    }
  };

  const runPullContext = async (articleId: number) => {
    if (!domain || !articleId) return;
    setPullLoading(true);
    setPullError(null);
    setPullStatus('pending');
    setPullArticleId(articleId);
    setPullSummary(null);
    setPullActors([]);
    try {
      const res = await articlesApi.pullContext(articleId, domain, id);
      await handlePullResponse((res || {}) as Record<string, unknown>);
    } catch (e: unknown) {
      setPullError(e instanceof Error ? e.message : 'Failed');
      setPullLoading(false);
    }
  };

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
            { label: 'Home', to: withDomainQuery('/', domain || null) },
            { label: 'News', to: withDomainQuery('/news', domain || null) },
            { label: 'Error' },
          ]}
        />
        <p className='v2-empty'>{error}</p>
        <Link to={withDomainQuery('/', domain || null)}>← Home</Link>
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

  const expansionBody = String(
    pack.vault_expansion?.summary_md &&
      String(pack.vault_expansion?.body_md || '').includes('Vault context')
      ? pack.vault_expansion.summary_md
      : pack.vault_expansion?.body_md || pack.vault_expansion?.summary_md || ''
  ).trim();
  // One brief surface: Pull refreshes the same block (no stacked Morning + Executive).
  const briefMd = (pullSummary || expansionBody).trim();
  const briefFromPull = Boolean(pullSummary);
  const summaryText = String(pack.summary || '').trim();
  const summaryDup = Boolean(
    summaryText &&
      briefMd &&
      (summaryText === briefMd ||
        briefMd.includes(summaryText.slice(0, Math.min(120, summaryText.length))) ||
        summaryText.includes(briefMd.slice(0, Math.min(120, briefMd.length))))
  );

  return (
    <div>
      <Breadcrumb
        crumbs={[
          { label: 'Home', to: withDomainQuery('/', domain || null) },
          { label: 'News', to: withDomainQuery('/news', domain || null) },
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
            {pack.updated_at && pack.article_count != null ? <MetaSep /> : null}
            {pack.article_count != null ? (
              <span>{pack.article_count} sources</span>
            ) : null}
            {(pack.updated_at || pack.article_count != null) && pack.status ? (
              <MetaSep />
            ) : null}
            {pack.status ? <span>{pack.status}</span> : null}
          </div>

          {pull ? <blockquote className='v2-pull-quote'>{pull}</blockquote> : null}

          {briefMd ? (
            <section style={{ marginBottom: '1.25rem' }}>
              <h2 className='v2-section-label'>
                {briefFromPull ? 'Executive brief' : 'Morning brief'}
              </h2>
              <p
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--v2-ink-muted)',
                  marginBottom: '0.75rem',
                }}
              >
                {briefFromPull
                  ? [
                      'Living context',
                      pullNoteCount ? `${pullNoteCount} notes` : null,
                      pullActors.length
                        ? pullActors.slice(0, 8).join(', ')
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')
                  : [
                      'Primed vault brief',
                      pack.vault_expansion?.updated_at
                        ? String(pack.vault_expansion.updated_at).slice(0, 10)
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
              </p>
              <ReaderMarkdown source={briefMd} />
            </section>
          ) : null}

          <div className='v2-pull-toolbar'>
            <button
              type='button'
              className='v2-reader-nav-link'
              disabled={pullLoading || !domain || !id}
              onClick={() => runStorylinePull()}
              style={{
                border: '1px solid var(--v2-rule)',
                background: 'transparent',
                cursor: pullLoading ? 'wait' : 'pointer',
                padding: '0.35rem 0.75rem',
                fontFamily: 'inherit',
              }}
            >
              {pullLoading ? 'Pulling context…' : 'Pull context'}
            </button>
            <span className='v2-pull-hint'>
              Cache-first living context
              {pullArticleId ? ` · article ${pullArticleId}` : ''}
            </span>
          </div>
          {pullError ? (
            <p className='v2-empty' style={{ color: 'crimson' }}>
              {pullError}
            </p>
          ) : null}
          {pullStatus && pullStatus !== 'ready' && !pullError ? (
            <p className='v2-empty'>Context job: {pullStatus}</p>
          ) : null}

          {!summaryDup ? (
            <section>
              <h2 className='v2-section-label'>Summary</h2>
              <p style={{ whiteSpace: 'pre-wrap' }}>
                {summaryText || 'No summary yet.'}
              </p>
            </section>
          ) : null}

          {pack.background_information ? (
            <section>
              <hr className='v2-section-rule' />
              <h2 className='v2-section-label'>Background</h2>
              <p style={{ whiteSpace: 'pre-wrap' }}>{pack.background_information}</p>
            </section>
          ) : null}

          {pack.vault_context_pack?.notes &&
          pack.vault_context_pack.notes.length > 0 ? (
            <section>
              <hr className='v2-section-rule' />
              <h2 className='v2-section-label'>Living context</h2>
              <p
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--v2-ink-muted)',
                  marginBottom: '0.75rem',
                }}
              >
                From Obsidian vault notes linked to this arc
                {pack.vault_context_pack.note_count
                  ? ` · ${pack.vault_context_pack.note_count} notes`
                  : ''}
              </p>
              <ul style={{ paddingLeft: '1.1rem' }}>
                {pack.vault_context_pack.notes.map((n, i) => (
                  <li
                    key={String(n.vault_path || n.title || i)}
                    style={{ marginBottom: '0.75rem' }}
                  >
                    <strong style={{ fontFamily: 'var(--v2-font-display)' }}>
                      {n.title || n.vault_path || 'Note'}
                    </strong>
                    {n.is_seed ? (
                      <span
                        style={{
                          marginLeft: '0.4rem',
                          fontSize: '0.75rem',
                          color: 'var(--v2-ink-muted)',
                        }}
                      >
                        seed
                      </span>
                    ) : null}
                    {n.significance_excerpt ? (
                      <p
                        style={{
                          margin: '0.25rem 0 0',
                          color: 'var(--v2-ink-muted)',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {n.significance_excerpt}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
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
                      {domain ? (
                        <>
                          {' · '}
                          <button
                            type='button'
                            disabled={pullLoading}
                            onClick={() => runPullContext(Number(c.id))}
                            style={{
                              background: 'none',
                              border: 'none',
                              padding: 0,
                              color: 'var(--v2-accent, inherit)',
                              textDecoration: 'underline',
                              cursor: pullLoading ? 'wait' : 'pointer',
                              font: 'inherit',
                            }}
                          >
                            Pull context
                          </button>
                        </>
                      ) : null}
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
                    <Link to={ch.href || `/storylines/${domain}/${ch.id}`}>
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
