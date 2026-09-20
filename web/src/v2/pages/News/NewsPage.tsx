import React, { useEffect, useState } from 'react';
import { StoryUnit } from '../../components/StoryUnit';
import { useV2Domain } from '../../hooks/useV2Domain';
import { fetchReaderHome, type StoryUnit as StoryUnitData } from '../../services/readerApi';

export default function NewsPage() {
  const domain = useV2Domain();
  const [items, setItems] = useState<StoryUnitData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReaderHome(domain)
      .then(res => {
        if (!cancelled) setItems(res.news || []);
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load news');
      });
    return () => {
      cancelled = true;
    };
  }, [domain]);

  return (
    <div>
      <p className='v2-section-label'>News</p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.5rem',
        }}
      >
        Material updates · last 48 hours
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '36rem' }}>
        Storylines with a real standfirst after editorial or timeline change —
        not membership-only article adds.
      </p>
      <div className='v2-hero-rule' />
      {error ? <p className='v2-empty'>{error}</p> : null}
      {!error && items.length === 0 ? (
        <p className='v2-empty'>No qualifying news right now.</p>
      ) : null}
      <div className='v2-cascade'>
        {items.map((item, i) => (
          <StoryUnit
            key={`${item.domain}-${item.storyline_id}`}
            item={item}
            variant={i === 0 ? 'hero' : i < 3 ? 'lead' : 'secondary'}
          />
        ))}
      </div>
    </div>
  );
}
