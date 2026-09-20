import React, { useEffect, useState } from 'react';
import { StoryUnit } from '../../components/StoryUnit';
import { useV2Domain } from '../../hooks/useV2Domain';
import { fetchReaderHome, type StoryUnit as StoryUnitData } from '../../services/readerApi';

export default function CurrentPage() {
  const domain = useV2Domain();
  const [items, setItems] = useState<StoryUnitData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReaderHome(domain)
      .then(res => {
        if (!cancelled) setItems(res.current_events || []);
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load current events');
      });
    return () => {
      cancelled = true;
    };
  }, [domain]);

  return (
    <div>
      <p className='v2-section-label'>Current Events</p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.5rem',
        }}
      >
        Long-running arcs
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '36rem' }}>
        Mega storylines, parent trees, and high-cadence coverage — last
        meaningful beat, not a raw article dump.
      </p>
      <hr className='v2-section-rule' />
      {error ? <p className='v2-empty'>{error}</p> : null}
      <div className='v2-rail-list'>
        {items.map(item => (
          <StoryUnit
            key={`${item.domain}-${item.storyline_id}`}
            item={item}
            variant='lead'
          />
        ))}
      </div>
    </div>
  );
}
