/**
 * Reader home — hero + cascade (News) with Current / One-offs rails.
 * News paints first; other rails load in parallel via sectioned endpoints.
 */
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { StoryUnit } from '../../components/StoryUnit';
import { rememberFeedNav } from '../../components/PaginationBar';
import { useV2Domain, withDomainQuery } from '../../hooks/useV2Domain';
import {
  fetchReaderHome,
  type PaginationMeta,
  type ReaderHomeResponse,
  type StoryUnit as StoryUnitType,
} from '../../services/readerApi';

type HomeState = {
  news_window_hours: number;
  news: StoryUnitType[];
  current_events: StoryUnitType[];
  one_offs: StoryUnitType[];
  research: StoryUnitType[];
  newsTotal: number;
};

function emptyHome(windowHours = 48): HomeState {
  return {
    news_window_hours: windowHours,
    news: [],
    current_events: [],
    one_offs: [],
    research: [],
    newsTotal: 0,
  };
}

export default function HomePage() {
  const domain = useV2Domain();
  const [data, setData] = useState<HomeState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setPending(true);
    setData(null);

    const opts = { page: 1, pageSize: 12 as const };

    fetchReaderHome(domain, { ...opts, section: 'news' })
      .then(newsRes => {
        if (cancelled) return null;
        const news = newsRes.news || [];
        rememberFeedNav(
          'news',
          news.map(it => ({
            domain: it.domain,
            storyline_id: it.storyline_id,
            href: withDomainQuery(
              it.href || `/storylines/${it.domain}/${it.storyline_id}`,
              it.domain || domain
            ),
          }))
        );
        const newsPag =
          newsRes.pagination && 'page' in newsRes.pagination
            ? (newsRes.pagination as PaginationMeta)
            : null;
        setData({
          ...emptyHome(newsRes.news_window_hours || 48),
          news,
          newsTotal: newsPag?.total ?? news.length,
        });
        setPending(false);
        return Promise.all([
          fetchReaderHome(domain, { ...opts, section: 'current_events' }),
          fetchReaderHome(domain, { ...opts, section: 'research' }),
          fetchReaderHome(domain, { ...opts, section: 'one_offs' }),
        ]);
      })
      .then(rails => {
        if (cancelled || !rails) return;
        const [currentRes, researchRes, oneOffsRes] = rails as ReaderHomeResponse[];
        setData(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            current_events: currentRes.current_events || [],
            research: researchRes.research || [],
            one_offs: oneOffsRes.one_offs || [],
          };
        });
      })
      .catch(err => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load home feed');
          setPending(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [domain]);

  const news = data?.news || [];
  const lead = news[0];
  const rest = news.slice(1, 8);
  const current = (data?.current_events || []).slice(0, 6);
  const oneOffs = (data?.one_offs || []).slice(0, 6);
  const research = (data?.research || []).slice(0, 6);
  const newsTotal = data?.newsTotal ?? news.length;

  return (
    <div>
      <p className='v2-section-label'>The Brief</p>
      {error ? <p className='v2-empty'>{error}</p> : null}
      {pending && !data ? <p className='v2-empty'>Loading…</p> : null}

      {lead ? (
        <>
          <StoryUnit item={lead} variant='hero' />
          <div className='v2-hero-rule' />
        </>
      ) : !error && data ? (
        <p className='v2-empty'>
          No material news updates in the last {data.news_window_hours}h with a
          standfirst. Check Current Events below.
        </p>
      ) : null}

      <div className='v2-cascade'>
        {rest.map((item, i) => (
          <StoryUnit
            key={
              item.surface_kind === 'daily_briefing'
                ? `briefing-${item.briefing_day || item.vault_path || item.href}`
                : item.surface_kind === 'vault_hub'
                  ? `hub-${item.hub_id || item.cluster_key || item.href}`
                  : `${item.domain}-${item.storyline_id}`
            }
            item={item}
            variant={i < 2 ? 'lead' : 'secondary'}
            style={{ animationDelay: `${80 + i * 40}ms` }}
          />
        ))}
      </div>

      {newsTotal > rest.length + (lead ? 1 : 0) ? (
        <p style={{ marginTop: '0.75rem' }}>
          <Link to={withDomainQuery('/news', domain)}>
            All news ({newsTotal}) →
          </Link>
        </p>
      ) : null}

      {(current.length > 0 || !data) && (
        <>
          <hr className='v2-section-rule' />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
            }}
          >
            <h2 className='v2-section-label' style={{ margin: 0 }}>
              Current Events
            </h2>
            <Link to={withDomainQuery('/current', domain)}>View all</Link>
          </div>
          <div className='v2-rail-list'>
            {!data ? (
              <p className='v2-empty'>Loading…</p>
            ) : (
              current.map(item => (
                <StoryUnit
                  key={`c-${item.domain}-${item.storyline_id}`}
                  item={item}
                  variant='secondary'
                />
              ))
            )}
          </div>
        </>
      )}

      <hr className='v2-section-rule' />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
        }}
      >
        <h2 className='v2-section-label' style={{ margin: 0 }}>
          Situations
        </h2>
        <Link to={withDomainQuery('/hubs', domain)}>All situations</Link>
      </div>
      <p style={{ color: 'var(--v2-ink-muted)', fontSize: '0.9rem' }}>
        Living hubs appear in the News cascade when active — browse the full
        index anytime.
      </p>

      {research.length > 0 || !data ? (
        <>
          <hr className='v2-section-rule' />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
            }}
          >
            <h2 className='v2-section-label' style={{ margin: 0 }}>
              Research
            </h2>
            <Link to={withDomainQuery('/research', domain)}>All papers</Link>
          </div>
          <div className='v2-rail-list'>
            {!data ? (
              <p className='v2-empty'>Loading…</p>
            ) : (
              research.map(item => (
                <StoryUnit
                  key={`r-${item.domain}-${item.storyline_id}`}
                  item={item}
                  variant='secondary'
                />
              ))
            )}
          </div>
        </>
      ) : null}

      {(oneOffs.length > 0 || !data) && (
        <>
          <hr className='v2-section-rule' />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
            }}
          >
            <h2 className='v2-section-label' style={{ margin: 0 }}>
              One-offs
            </h2>
            <Link to={withDomainQuery('/one-offs', domain)}>Calendar</Link>
          </div>
          <div className='v2-rail-list'>
            {!data ? (
              <p className='v2-empty'>Loading…</p>
            ) : (
              oneOffs.map(item => (
                <StoryUnit
                  key={`o-${item.domain}-${item.storyline_id}`}
                  item={item}
                  variant='secondary'
                />
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
