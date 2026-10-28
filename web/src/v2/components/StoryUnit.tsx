/**
 * StoryUnit — consistent anatomy for News / Current / One-off items.
 * Hairline-separated; not a card.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import type { StoryUnit as StoryUnitData } from '../services/readerApi';
import { withDomainQuery } from '../hooks/useV2Domain';
import { stripReaderMdMarkers } from '../../utils/sanitizeSnippet';

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

function surfaceLabel(kind: string | undefined): string | null {
  switch (kind) {
    case 'vault_hub':
      return 'Situation';
    case 'storyline_expansion':
      return 'Today’s brief';
    case 'research_paper':
    case 'research':
      return 'Paper';
    case 'one_off':
      return 'One-off';
    case 'daily_briefing':
      return 'Briefing';
    default:
      return null;
  }
}

export function StoryUnit({ item, variant = 'secondary', style }: Props) {
  const href =
    item.surface_kind === 'daily_briefing'
      ? withDomainQuery(item.href || '/news', null)
      : withDomainQuery(
          item.href ||
            (item.surface_kind === 'vault_hub' && item.cluster_key
              ? `/hubs/${item.cluster_key}`
              : `/storylines/${item.domain}/${item.storyline_id}`),
          item.domain || null
        );
  const kind = surfaceLabel(item.surface_kind);
  const hubBrief =
    item.surface_kind === 'vault_hub' && item.current_brief
      ? stripReaderMdMarkers(item.current_brief).slice(0, 200)
      : '';
  const meta: React.ReactNode[] = [];
  const push = (node: React.ReactNode) => {
    if (meta.length) meta.push(<MetaSep key={`sep-${meta.length}`} />);
    meta.push(node);
  };
  if (item.updated_label) {
    push(<span key='upd'>{item.updated_label}</span>);
  }
  if (item.article_count != null && item.article_count > 0) {
    push(
      <span key='ac'>
        {item.surface_kind === 'vault_hub'
          ? `${item.article_count} episodes`
          : `${item.article_count} sources`}
      </span>
    );
  }
  if (item.read_minutes) {
    push(<span key='read'>{item.read_minutes} min read</span>);
  }
  if (item.expected_on) {
    push(<span key='exp'>Expected {item.expected_on}</span>);
  } else if (item.announced_on) {
    push(<span key='ann'>Announced {item.announced_on}</span>);
  }
  if (item.surface_kind === 'storyline_expansion') {
    push(
      <span key='today' className='v2-badge'>
        In today’s brief
      </span>
    );
    if (item.briefing_lane === 'ongoing' || item.briefing_lane === 'new') {
      push(
        <span key='lane' className='v2-badge'>
          {item.briefing_lane === 'ongoing' ? 'ongoing' : 'new'}
        </span>
      );
    }
  }
  for (const b of item.badges || []) {
    if (
      item.surface_kind === 'storyline_expansion' &&
      (b === 'ongoing' || b === 'new' || b === 'situation')
    ) {
      continue;
    }
    if (item.surface_kind === 'vault_hub' && b === 'situation') {
      continue;
    }
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
        {kind || item.section_label}
        {item.domain ? ` · ${item.domain.toUpperCase()}` : ''}
      </div>
      <h2 className='v2-story-headline'>
        <Link to={href}>{item.headline}</Link>
      </h2>
      {item.dek ? <p className='v2-story-dek'>{item.dek}</p> : null}
      {hubBrief && hubBrief !== item.dek ? (
        <p
          className='v2-story-dek'
          style={{ opacity: 0.85, fontSize: '0.95em' }}
        >
          {hubBrief}
          {item.current_brief && item.current_brief.length > 200 ? '…' : ''}
        </p>
      ) : null}
      {meta.length ? <div className='v2-story-meta'>{meta}</div> : null}
    </article>
  );
}
