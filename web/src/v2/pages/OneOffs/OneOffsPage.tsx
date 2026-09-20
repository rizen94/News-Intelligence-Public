/**
 * One-offs list + calendar (expected_on / announced_on) with pagination.
 */
import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { StoryUnit } from '../../components/StoryUnit';
import { PaginationBar } from '../../components/PaginationBar';
import { usePagedFeed } from '../../hooks/usePagedFeed';

function dayKey(iso: string | null | undefined): string | null {
  if (!iso) return null;
  return iso.slice(0, 10);
}

export default function OneOffsPage() {
  const { items, pagination, error, pending } = usePagedFeed('one_offs', 20);

  const byDay = useMemo(() => {
    const map = new Map<string, typeof items>();
    for (const item of items) {
      const key = dayKey(item.expected_on) || dayKey(item.announced_on);
      if (!key) continue;
      const list = map.get(key) || [];
      list.push(item);
      map.set(key, list);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [items]);

  return (
    <div>
      <p className='v2-section-label'>One-offs</p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.5rem',
        }}
      >
        Announcements &amp; dated events
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '38rem' }}>
        Calendar uses <strong>expected_on</strong> when known; otherwise{' '}
        <strong>announced_on</strong>. Month phrases resolve to the 1st of that
        month.
      </p>
      <hr className='v2-section-rule' />

      {error ? <p className='v2-empty'>{error}</p> : null}
      {pending && !items.length ? <p className='v2-empty'>Loading…</p> : null}

      <h2 className='v2-section-label'>Calendar</h2>
      {byDay.length === 0 && !pending ? (
        <p className='v2-empty'>No concrete expected dates yet.</p>
      ) : (
        <div className='v2-cal-grid'>
          {byDay.map(([day, events]) => (
            <div key={day} className='v2-cal-cell'>
              <div className='v2-cal-day'>{day}</div>
              {events.map(ev => (
                <div key={`${ev.domain}-${ev.storyline_id}`} className='v2-cal-event'>
                  <Link to={ev.href}>{ev.headline}</Link>
                  {ev.expected_on ? (
                    <div style={{ fontSize: '0.7rem', color: 'var(--v2-ink-muted)' }}>
                      expected
                      {ev.date_precision === 'month' ? ' (month → 1st)' : ''}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.7rem', color: 'var(--v2-ink-muted)' }}>
                      announced
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <hr className='v2-section-rule' />
      <h2 className='v2-section-label'>List</h2>
      <div className='v2-rail-list'>
        {items.map(item => (
          <StoryUnit
            key={`${item.domain}-${item.storyline_id}`}
            item={item}
            variant='secondary'
          />
        ))}
      </div>
      <PaginationBar pagination={pagination} ariaLabel='One-offs pages' />
    </div>
  );
}
