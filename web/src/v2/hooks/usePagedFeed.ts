/**
 * Shared hook for v2 section feeds with URL pagination + nav memory.
 */
import { useEffect, useState, useTransition } from 'react';
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

export type FeedSection = 'news' | 'current_events' | 'one_offs';

const SECTION_KEY: Record<FeedSection, 'news' | 'current_events' | 'one_offs'> = {
  news: 'news',
  current_events: 'current_events',
  one_offs: 'one_offs',
};

export function usePagedFeed(section: FeedSection, pageSize = 12) {
  const domain = useV2Domain();
  const [params] = useSearchParams();
  const page = pageFromSearch(params);
  const [items, setItems] = useState<StoryUnit[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [windowHours, setWindowHours] = useState(48);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchReaderHome(domain, { page, pageSize, section })
      .then(res => {
        if (cancelled) return;
        const key = SECTION_KEY[section];
        const list = (res[key] as StoryUnit[]) || [];
        const pag =
          res.pagination && 'page' in res.pagination
            ? (res.pagination as PaginationMeta)
            : null;
        const navIds: NavId[] =
          res.nav_ids ||
          list.map(it => ({
            domain: it.domain,
            storyline_id: it.storyline_id,
            href: it.href,
          }));
        rememberFeedNav(section, navIds);
        startTransition(() => {
          setItems(list);
          setPagination(pag);
          setWindowHours(res.news_window_hours || 48);
        });
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load feed');
      });
    return () => {
      cancelled = true;
    };
  }, [domain, page, pageSize, section]);

  return { domain, page, items, pagination, error, pending, windowHours };
}
