/**
 * Pagination controls for v2 feed pages — URL ?page= driven.
 */
import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';

export type PaginationMeta = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_prev: boolean;
  has_next: boolean;
};

type Props = {
  pagination: PaginationMeta | null | undefined;
  /** Preserve other query params (domain, section). */
  ariaLabel?: string;
};

export function PaginationBar({ pagination, ariaLabel = 'Pagination' }: Props) {
  const [params, setParams] = useSearchParams();
  if (!pagination || pagination.total_pages <= 1) {
    if (pagination && pagination.total > 0) {
      return (
        <p className='v2-pager-meta' aria-live='polite'>
          {pagination.total} {pagination.total === 1 ? 'story' : 'stories'}
        </p>
      );
    }
    return null;
  }

  const go = (page: number) => {
    const next = new URLSearchParams(params);
    if (page <= 1) next.delete('page');
    else next.set('page', String(page));
    setParams(next, { replace: false });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const { page, total_pages, total, has_prev, has_next } = pagination;
  const windowStart = Math.max(1, page - 2);
  const windowEnd = Math.min(total_pages, page + 2);
  const pages: number[] = [];
  for (let p = windowStart; p <= windowEnd; p += 1) pages.push(p);

  return (
    <nav className='v2-pager' aria-label={ariaLabel}>
      <p className='v2-pager-meta'>
        Page {page} of {total_pages} · {total} stories
      </p>
      <div className='v2-pager-controls'>
        <button
          type='button'
          className='v2-pager-btn'
          disabled={!has_prev}
          onClick={() => go(page - 1)}
        >
          ← Prev
        </button>
        {windowStart > 1 ? (
          <>
            <button type='button' className='v2-pager-btn' onClick={() => go(1)}>
              1
            </button>
            {windowStart > 2 ? <span className='v2-pager-ellipsis'>…</span> : null}
          </>
        ) : null}
        {pages.map(p => (
          <button
            key={p}
            type='button'
            className={`v2-pager-btn${p === page ? ' is-active' : ''}`}
            aria-current={p === page ? 'page' : undefined}
            onClick={() => go(p)}
          >
            {p}
          </button>
        ))}
        {windowEnd < total_pages ? (
          <>
            {windowEnd < total_pages - 1 ? (
              <span className='v2-pager-ellipsis'>…</span>
            ) : null}
            <button
              type='button'
              className='v2-pager-btn'
              onClick={() => go(total_pages)}
            >
              {total_pages}
            </button>
          </>
        ) : null}
        <button
          type='button'
          className='v2-pager-btn'
          disabled={!has_next}
          onClick={() => go(page + 1)}
        >
          Next →
        </button>
      </div>
    </nav>
  );
}

export function pageFromSearch(params: URLSearchParams): number {
  const raw = Number(params.get('page') || '1');
  return Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : 1;
}

/** Persist feed nav_ids so the reader can offer prev/next. */
const NAV_KEY = 'ni.v2.feedNav';

export type NavId = { domain: string; storyline_id: number; href: string };

export function rememberFeedNav(section: string, ids: NavId[]): void {
  try {
    sessionStorage.setItem(
      NAV_KEY,
      JSON.stringify({ section, ids, saved_at: Date.now() })
    );
  } catch {
    /* ignore quota */
  }
}

export function loadFeedNav(): { section: string; ids: NavId[] } | null {
  try {
    const raw = sessionStorage.getItem(NAV_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { section?: string; ids?: NavId[] };
    if (!parsed?.ids?.length) return null;
    return { section: parsed.section || 'news', ids: parsed.ids };
  } catch {
    return null;
  }
}

export function feedNavNeighbors(
  domain: string,
  storylineId: number
): { prev: NavId | null; next: NavId | null; index: number; total: number } {
  const nav = loadFeedNav();
  if (!nav) return { prev: null, next: null, index: -1, total: 0 };
  const idx = nav.ids.findIndex(
    n => n.domain === domain && Number(n.storyline_id) === Number(storylineId)
  );
  if (idx < 0) return { prev: null, next: null, index: -1, total: nav.ids.length };
  return {
    prev: idx > 0 ? nav.ids[idx - 1] : null,
    next: idx < nav.ids.length - 1 ? nav.ids[idx + 1] : null,
    index: idx,
    total: nav.ids.length,
  };
}

/** Breadcrumb link helper that keeps domain query. */
export function Breadcrumb({
  crumbs,
}: {
  crumbs: Array<{ label: string; to?: string }>;
}) {
  return (
    <nav className='v2-breadcrumb' aria-label='Breadcrumb'>
      {crumbs.map((c, i) => (
        <span key={`${c.label}-${i}`}>
          {i > 0 ? <span className='v2-breadcrumb-sep'>/</span> : null}
          {c.to ? <Link to={c.to}>{c.label}</Link> : <span>{c.label}</span>}
        </span>
      ))}
    </nav>
  );
}
