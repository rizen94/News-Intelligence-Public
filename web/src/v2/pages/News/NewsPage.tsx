import React from 'react';
import { StoryUnit } from '../../components/StoryUnit';
import { PaginationBar } from '../../components/PaginationBar';
import { usePagedFeed } from '../../hooks/usePagedFeed';

export default function NewsPage() {
  const { items, pagination, error, pending, windowHours } = usePagedFeed('news', 12);

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
        Material updates · last {windowHours} hours
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '36rem' }}>
        Storylines with a real standfirst after editorial or timeline change —
        not membership-only article adds.
      </p>
      <div className='v2-hero-rule' />
      {error ? <p className='v2-empty'>{error}</p> : null}
      {pending && !items.length ? <p className='v2-empty'>Loading…</p> : null}
      {!error && !pending && items.length === 0 ? (
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
      <PaginationBar pagination={pagination} ariaLabel='News pages' />
    </div>
  );
}
