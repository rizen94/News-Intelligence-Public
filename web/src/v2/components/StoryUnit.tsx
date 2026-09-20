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

function MetaSep() {
  return (
    <span className='v2-meta-sep' aria-hidden='true'>
      ·
    </span>
  );
}

export function StoryUnit({ item, variant = 'secondary', style }: Props) {
  const href = withDomainQuery(
    item.href || `/v2/storylines/${item.domain}/${item.storyline_id}`,
    item.domain || null
  );
  const meta: React.ReactNode[] = [];
  const push = (node: React.ReactNode) => {
    if (meta.length) meta.push(<MetaSep key={`sep-${meta.length}`} />);
    meta.push(node);
  };
  if (item.updated_label) {
    push(<span key='upd'>{item.updated_label}</span>);
  }
  if (item.read_minutes) {
    push(<span key='read'>{item.read_minutes} min read</span>);
  }
  if (item.expected_on) {
    push(<span key='exp'>Expected {item.expected_on}</span>);
  } else if (item.announced_on) {
    push(<span key='ann'>Announced {item.announced_on}</span>);
  }
  for (const b of item.badges || []) {
    push(
      <span key={`b-${b}`} className='v2-badge'>
        {b}
      </span>
    );
  }
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
      {meta.length ? <div className='v2-story-meta'>{meta}</div> : null}
    </article>
  );
}
