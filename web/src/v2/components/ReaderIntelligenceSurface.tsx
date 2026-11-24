/**
 * Surfaces spine data on public reader pages: article_entities + intelligence.contexts.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { withDomainQuery } from '../hooks/useV2Domain';
import type {
  ReaderArticleIntelligence,
  ReaderContextSnapshot,
  ReaderEntityMention,
} from '../services/readerApi';

function EntityList({
  entities,
  domain,
  compact,
}: {
  entities: ReaderEntityMention[];
  domain: string;
  compact?: boolean;
}) {
  if (!entities?.length) return null;
  if (compact) {
    return (
      <div className='v2-entity-chips' style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
        {entities.slice(0, 24).map((e, i) => {
          const inner = (
            <span
              className='v2-badge'
              title={e.snippet || e.description || undefined}
              style={{ fontWeight: 500 }}
            >
              {e.name}
              {e.entity_type ? ` · ${e.entity_type}` : ''}
            </span>
          );
          return e.href ? (
            <Link key={`${e.name}-${i}`} to={withDomainQuery(e.href, domain)}>
              {inner}
            </Link>
          ) : (
            <span key={`${e.name}-${i}`}>{inner}</span>
          );
        })}
      </div>
    );
  }
  return (
    <ul style={{ paddingLeft: '1.1rem', margin: 0 }}>
      {entities.slice(0, 32).map((e, i) => (
        <li key={`${e.name}-${i}`} style={{ marginBottom: '0.45rem' }}>
          {e.href ? (
            <Link to={withDomainQuery(e.href, domain)}>{e.name}</Link>
          ) : (
            <strong>{e.name}</strong>
          )}
          <span style={{ fontSize: '0.8rem', color: 'var(--v2-ink-muted)' }}>
            {e.entity_type ? ` · ${e.entity_type}` : ''}
            {e.confidence != null ? ` · ${Math.round(e.confidence * 100)}%` : ''}
            {(e as { mention_count?: number }).mention_count
              ? ` · ${(e as { mention_count: number }).mention_count} mentions`
              : ''}
          </span>
          {e.snippet ? (
            <div style={{ fontSize: '0.85rem', color: 'var(--v2-ink-muted)' }}>
              {e.snippet}
            </div>
          ) : e.description ? (
            <div style={{ fontSize: '0.85rem', color: 'var(--v2-ink-muted)' }}>
              {e.description}
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function ContextList({
  contexts,
  domain,
}: {
  contexts: ReaderContextSnapshot[];
  domain: string;
}) {
  if (!contexts?.length) return null;
  return (
    <ul style={{ paddingLeft: '1.1rem', margin: 0 }}>
      {contexts.map(c => (
        <li key={c.context_id} style={{ marginBottom: '0.85rem' }}>
          <strong style={{ fontFamily: 'var(--v2-font-display)' }}>
            {c.title || `Context ${c.context_id}`}
          </strong>
          {c.article_id != null ? (
            <span style={{ fontSize: '0.8rem', color: 'var(--v2-ink-muted)' }}>
              {' '}
              ·{' '}
              <Link to={withDomainQuery(`/${domain}/articles/${c.article_id}`, domain)}>
                article {c.article_id}
              </Link>
            </span>
          ) : null}
          {c.excerpt ? (
            <p
              style={{
                margin: '0.35rem 0 0',
                color: 'var(--v2-ink-muted)',
                whiteSpace: 'pre-wrap',
                lineHeight: 1.45,
              }}
            >
              {c.excerpt}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function ArticleIntelligencePanel({
  data,
  domain,
}: {
  data: ReaderArticleIntelligence | null;
  domain: string;
}) {
  if (!data) return null;
  const hasEntities = (data.entities?.length || 0) > 0;
  const ctx = data.context;
  if (!hasEntities && !ctx) {
    return (
      <p className='v2-empty' style={{ fontSize: '0.9rem' }}>
        No extracted entities or stored context yet for this article.
      </p>
    );
  }
  return (
    <div>
      {hasEntities ? (
        <section style={{ marginBottom: '1rem' }}>
          <h3 className='v2-section-label' style={{ marginBottom: '0.5rem' }}>
            Entities ({data.entity_count ?? data.entities.length})
          </h3>
          <EntityList entities={data.entities} domain={domain} />
        </section>
      ) : null}
      {ctx ? (
        <section>
          <h3 className='v2-section-label' style={{ marginBottom: '0.5rem' }}>
            Intelligence context
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--v2-ink-muted)', marginBottom: '0.5rem' }}>
            Spine context #{ctx.context_id}
            {ctx.updated_at ? ` · updated ${ctx.updated_at.slice(0, 10)}` : ''}
          </p>
          <ContextList contexts={[ctx]} domain={domain} />
        </section>
      ) : null}
    </div>
  );
}

export function StorylineIntelligenceSection({
  entities,
  contexts,
  domain,
}: {
  entities?: ReaderEntityMention[];
  contexts?: ReaderContextSnapshot[];
  domain: string;
}) {
  const ents = entities || [];
  const ctxs = contexts || [];
  if (!ents.length && !ctxs.length) return null;
  return (
    <section>
      <hr className='v2-section-rule' />
      <h2 className='v2-section-label'>Intelligence spine</h2>
      <p
        style={{
          fontSize: '0.85rem',
          color: 'var(--v2-ink-muted)',
          marginBottom: '0.75rem',
        }}
      >
        Extracted mentions and stored contexts from member articles
      </p>
      {ents.length ? (
        <div style={{ marginBottom: '1rem' }}>
          <h3 className='v2-section-label' style={{ fontSize: '0.75rem' }}>
            Top entities
          </h3>
          <EntityList entities={ents} domain={domain} compact />
        </div>
      ) : null}
      {ctxs.length ? (
        <div>
          <h3 className='v2-section-label' style={{ fontSize: '0.75rem' }}>
            Context snapshots
          </h3>
          <ContextList contexts={ctxs} domain={domain} />
        </div>
      ) : null}
    </section>
  );
}