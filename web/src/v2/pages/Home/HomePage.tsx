/**
 * Reader home — hero + cascade (News) with Current / One-offs rails.
 */
import React, { useEffect, useState, useTransition } from 'react';
import { Link } from 'react-router-dom';
import { StoryUnit } from '../../components/StoryUnit';
import { useV2Domain, withDomainQuery } from '../../hooks/useV2Domain';
import { fetchReaderHome, type ReaderHomeResponse } from '../../services/readerApi';

export default function HomePage() {
  const domain = useV2Domain();
  const [data, setData] = useState<ReaderHomeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchReaderHome(domain)
      .then(res => {
        if (!cancelled) startTransition(() => setData(res));
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load home feed');
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
            key={`${item.domain}-${item.storyline_id}`}
            item={item}
            variant={i < 2 ? 'lead' : 'secondary'}
            style={{ animationDelay: `${80 + i * 40}ms` }}
          />
        ))}
      </div>

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
        <Link to={withDomainQuery('/v2/current', domain)}>View all</Link>
      </div>
      <div className='v2-rail-list'>
        {current.length === 0 ? (
          <p className='v2-empty'>No long-running arcs matched.</p>
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
        <Link to={withDomainQuery('/v2/one-offs', domain)}>Calendar</Link>
      </div>
      <div className='v2-rail-list'>
        {oneOffs.length === 0 ? (
          <p className='v2-empty'>No dated announcements yet.</p>
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
    </div>
  );
}
