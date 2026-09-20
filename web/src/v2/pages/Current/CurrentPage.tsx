import React from 'react';
import { StoryUnit } from '../../components/StoryUnit';
import { PaginationBar } from '../../components/PaginationBar';
import { usePagedFeed } from '../../hooks/usePagedFeed';

export default function CurrentPage() {
  const { items, pagination, error, pending } = usePagedFeed('current_events', 12);

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
      {pending && !items.length ? <p className='v2-empty'>Loading…</p> : null}
      {!error && !pending && items.length === 0 ? (
        <p className='v2-empty'>No long-running arcs matched.</p>
      ) : null}
      <div className='v2-rail-list'>
        {items.map(item => (
          <StoryUnit
            key={`${item.domain}-${item.storyline_id}`}
            item={item}
            variant='lead'
          />
        ))}
      </div>
      <PaginationBar pagination={pagination} ariaLabel='Current events pages' />
    </div>
  );
}
