/**
 * StoryUnit — consistent anatomy for News / Current / One-off items.
 * Hairline-separated; not a card.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import type { StoryUnit as StoryUnitData } from '../services/readerApi';
import { withDomainQuery } from '../hooks/useV2Domain';

type Variant = 'hero' | 'lead' | 'secondary';

type Props = {
  item: StoryUnitData;
  variant?: Variant;
  style?: React.CSSProperties;
};

export function StoryUnit({ item, variant = 'secondary', style }: Props) {
  const href = withDomainQuery(
    item.href || `/v2/storylines/${item.domain}/${item.storyline_id}`,
    item.domain || null
  );
  return (
    <article
      className={`v2-story-unit v2-story-unit--${variant}`}
      style={style}
    >
      <div className='v2-story-kicker'>
        {item.section_label}
        {item.domain ? ` · ${item.domain.toUpperCase()}` : ''}
      </div>
      <h2 className='v2-story-headline'>
        <Link to={href}>{item.headline}</Link>
      </h2>
      {item.dek ? <p className='v2-story-dek'>{item.dek}</p> : null}
      <div className='v2-story-meta'>
        {item.updated_label ? <span>{item.updated_label}</span> : null}
        {item.read_minutes ? <span>{item.read_minutes} min read</span> : null}
        {item.expected_on ? <span>Expected {item.expected_on}</span> : null}
        {item.announced_on && !item.expected_on ? (
          <span>Announced {item.announced_on}</span>
        ) : null}
        {(item.badges || []).map(b => (
          <span key={b} className='v2-badge'>
            {b}
          </span>
        ))}
      </div>
    </article>
  );
}
