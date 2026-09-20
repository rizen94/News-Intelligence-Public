/**
 * Shared hook for v2 section feeds with URL pagination + nav memory.
 */
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useV2Domain } from '../hooks/useV2Domain';
import {
  fetchReaderHome,
  type PaginationMeta,
  type StoryUnit,
} from '../services/readerApi';
import {
  pageFromSearch,
  rememberFeedNav,
  type NavId,
} from '../components/PaginationBar';
import { withDomainQuery } from './useV2Domain';

export type FeedSection = 'news' | 'current_events' | 'one_offs';

const SECTION_KEY: Record<FeedSection, 'news' | 'current_events' | 'one_offs'> = {
  news: 'news',
  current_events: 'current_events',
  one_offs: 'one_offs',
};

function withNavHref(it: { domain: string; storyline_id: number; href?: string }): NavId {
  const base = it.href || `/v2/storylines/${it.domain}/${it.storyline_id}`;
  return {
    domain: it.domain,
    storyline_id: it.storyline_id,
    href: withDomainQuery(base, it.domain || null),
  };
}

export function usePagedFeed(section: FeedSection, pageSize = 12) {
  const domain = useV2Domain();
  const [params] = useSearchParams();
  const page = pageFromSearch(params);
  const [items, setItems] = useState<StoryUnit[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);
  const [windowHours, setWindowHours] = useState(48);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setPending(true);
    // Drop stale rows immediately so ?page=2 never paints page-1 headlines.
    setItems([]);
    setPagination(null);
    fetchReaderHome(domain, { page, pageSize, section })
      .then(res => {
        if (cancelled) return;
        const key = SECTION_KEY[section];
        const list = ((res[key] as StoryUnit[]) || []).map(it => ({
          ...it,
          href: withDomainQuery(
            it.href || `/v2/storylines/${it.domain}/${it.storyline_id}`,
            it.domain || domain
          ),
        }));
        const pag =
          res.pagination && 'page' in res.pagination
            ? (res.pagination as PaginationMeta)
            : null;
        const navIds: NavId[] = (res.nav_ids || list).map(withNavHref);
        rememberFeedNav(section, navIds);
        setItems(list);
        setPagination(pag);
        setWindowHours(res.news_window_hours || 48);
        setPending(false);
      })
      .catch(err => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load feed');
          setPending(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [domain, page, pageSize, section]);

  return { domain, page, items, pagination, error, pending, windowHours };
}
