/**
 * Research list — scientific papers with research-axis cards (not news storylines).
 */
import React from 'react';
import { StoryUnit } from '../../components/StoryUnit';
import { PaginationBar } from '../../components/PaginationBar';
import { usePagedFeed } from '../../hooks/usePagedFeed';

export default function ResearchPage() {
  const { items, pagination, error, pending } = usePagedFeed('research', 20);

  return (
    <div>
      <p className='v2-section-label'>Research</p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.5rem',
        }}
      >
        Papers &amp; findings
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '40rem' }}>
        Scientific papers are profiled by research question, methods, findings, and
        implications — separate from event-driven news storylines. Dated papers also
        appear on the One-offs calendar.
      </p>
      <hr className='v2-section-rule' />

      {error ? <p className='v2-empty'>{error}</p> : null}
      {pending && !items.length ? <p className='v2-empty'>Loading…</p> : null}
      {!pending && !items.length && !error ? (
        <p className='v2-empty'>No profiled papers yet.</p>
      ) : null}

      <div className='v2-rail-list'>
        {items.map(item => (
          <StoryUnit
            key={`${item.domain}-${item.storyline_id}-${item.href}`}
            item={item}
            variant='secondary'
          />
        ))}
      </div>
      <PaginationBar pagination={pagination} ariaLabel='Research pages' />
    </div>
  );
}
