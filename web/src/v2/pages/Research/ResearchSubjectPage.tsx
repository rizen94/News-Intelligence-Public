/**
 * Subject fact sheet — supported / not supported / open + claims / citations.
 */
import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  readerApi,
  type ResearchCitation,
  type ResearchClaim,
  type ResearchSubjectBoard,
} from '../../../services/api/readerResearch';

type Assertion = {
  text?: string;
  evidence_grade?: string;
  verdict?: string;
  quote?: string;
  source_refs?: { source_url?: string; quote?: string; article_id?: number };
  article_id?: number;
};

const DOMAIN_LABELS: Record<string, string> = {
  neurodiversity: 'Neurodiversity',
  'artificial-intelligence': 'Artificial intelligence',
  medicine: 'Medicine',
};

function FactRows({
  items,
  emptyLabel,
}: {
  items: Assertion[];
  emptyLabel: string;
}) {
  if (!items.length) {
    return <p className='v2-empty'>{emptyLabel}</p>;
  }
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {items.map((a, i) => {
        const quote = a.quote || a.source_refs?.quote;
        const url = a.source_refs?.source_url;
        const grade = a.evidence_grade;
        return (
          <li
            key={`${a.text?.slice(0, 40)}-${i}`}
            style={{
              borderTop: '1px solid var(--v2-rule)',
              padding: '0.9rem 0',
            }}
          >
            <p style={{ margin: '0 0 0.35rem', lineHeight: 1.5 }}>{a.text}</p>
            <p
              style={{
                margin: 0,
                fontSize: '0.82rem',
                color: 'var(--v2-ink-muted)',
              }}
            >
              {[grade, a.verdict].filter(Boolean).join(' · ')}
              {url ? (
                <>
                  {' · '}
                  <a href={url} target='_blank' rel='noreferrer'>
                    evidence
                  </a>
                </>
              ) : null}
            </p>
            {quote ? (
              <blockquote
                style={{
                  margin: '0.55rem 0 0',
                  paddingLeft: '0.75rem',
                  borderLeft: '2px solid var(--v2-rule)',
                  color: 'var(--v2-ink-muted)',
                  fontSize: '0.88rem',
                  lineHeight: 1.45,
                }}
              >
                {quote}
              </blockquote>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function claimText(c: ResearchClaim): string {
  return (c.claim_text || c.text || '').trim();
}

export default function ResearchSubjectPage() {
  const { domainKey = '', entityId = '' } = useParams();
  const [board, setBoard] = useState<ResearchSubjectBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setPending(true);
    setError(null);
    readerApi
      .getResearchSubject(domainKey, Number(entityId))
      .then(data => {
        if (cancelled) return;
        if (!data?.ok) {
          setError(data?.error || 'Subject not found');
          setBoard(null);
        } else {
          setBoard(data);
        }
      })
      .catch(err => {
        if (!cancelled) setError(String(err?.message || err));
      })
      .finally(() => {
        if (!cancelled) setPending(false);
      });
    return () => {
      cancelled = true;
    };
  }, [domainKey, entityId]);

  const title =
    board?.title || board?.entity?.canonical_name || 'Research subject';
  const domainLabel =
    board?.domain_label || DOMAIN_LABELS[domainKey] || domainKey;
  const domainKeywords = board?.domain_keywords || [];
  const counts = board?.assertion_counts || { is: 0, is_not: 0, open: 0 };
  const claims = (board?.claims || []).filter(c => claimText(c));
  const citations = (board?.citations || []).filter(
    (c: ResearchCitation) => c.source_url || c.url || c.title || c.quote
  );
  const vaultPath = board?.vault_path || null;

  return (
    <div>
      <p className='v2-section-label'>
        <Link to='/research' style={{ color: 'inherit' }}>
          Research
        </Link>
        {domainLabel ? ` / ${domainLabel}` : null}
      </p>
      <h1
        style={{
          fontFamily: 'var(--v2-font-display)',
          fontSize: '2rem',
          margin: '0 0 0.35rem',
        }}
      >
        {title}
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '42rem', marginTop: 0 }}>
        Fact sheet from appraised research — not article headlines.
        {board && !pending ? (
          <>
            {' '}
            {counts.is} supported · {counts.is_not} not supported · {counts.open}{' '}
            open
          </>
        ) : null}
      </p>
      {domainKeywords.length ? (
        <p
          style={{
            color: 'var(--v2-ink-muted)',
            fontSize: '0.88rem',
            marginTop: '0.25rem',
            maxWidth: '48rem',
          }}
        >
          {domainKeywords.join(' · ')}
        </p>
      ) : null}
      {vaultPath ? (
        <p
          style={{
            color: 'var(--v2-ink-muted)',
            fontSize: '0.85rem',
            marginTop: '0.35rem',
          }}
        >
          Vault note:{' '}
          <code style={{ fontSize: '0.82rem' }}>{vaultPath}</code>
          {domainKey === 'neurodiversity' ? (
            <>
              {' '}
              · DSM-5-TR definitions live in that note’s “DSM definitions” section
            </>
          ) : null}
        </p>
      ) : null}
      <hr className='v2-section-rule' />

      {pending ? <p className='v2-empty'>Loading fact sheet…</p> : null}
      {error ? <p className='v2-empty'>{error}</p> : null}

      {board && !pending ? (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(16rem, 1fr))',
              gap: '1.75rem',
              marginTop: '1rem',
            }}
          >
            <section>
              <h2
                style={{
                  fontFamily: 'var(--v2-font-display)',
                  fontSize: '1.15rem',
                  margin: '0 0 0.35rem',
                }}
              >
                Supported
              </h2>
              <p
                style={{
                  margin: '0 0 0.5rem',
                  fontSize: '0.85rem',
                  color: 'var(--v2-ink-muted)',
                }}
              >
                Evidence leans in favor ({counts.is})
              </p>
              <FactRows
                items={(board.supported || []) as Assertion[]}
                emptyLabel='Nothing graded as supported yet.'
              />
            </section>
            <section>
              <h2
                style={{
                  fontFamily: 'var(--v2-font-display)',
                  fontSize: '1.15rem',
                  margin: '0 0 0.35rem',
                }}
              >
                Not supported
              </h2>
              <p
                style={{
                  margin: '0 0 0.5rem',
                  fontSize: '0.85rem',
                  color: 'var(--v2-ink-muted)',
                }}
              >
                Evidence leans against ({counts.is_not})
              </p>
              <FactRows
                items={(board.not_supported || []) as Assertion[]}
                emptyLabel='Nothing graded as not supported yet.'
              />
            </section>
            <section>
              <h2
                style={{
                  fontFamily: 'var(--v2-font-display)',
                  fontSize: '1.15rem',
                  margin: '0 0 0.35rem',
                }}
              >
                Open
              </h2>
              <p
                style={{
                  margin: '0 0 0.5rem',
                  fontSize: '0.85rem',
                  color: 'var(--v2-ink-muted)',
                }}
              >
                Unsettled or preliminary ({counts.open})
              </p>
              <FactRows
                items={(board.open || []) as Assertion[]}
                emptyLabel='No open questions yet.'
              />
            </section>
          </div>

          <hr className='v2-section-rule' style={{ marginTop: '2rem' }} />

          <section style={{ marginTop: '1.25rem', maxWidth: '48rem' }}>
            <h2
              style={{
                fontFamily: 'var(--v2-font-display)',
                fontSize: '1.15rem',
                margin: '0 0 0.35rem',
              }}
            >
              Claim ledger
            </h2>
            <p
              style={{
                margin: '0 0 0.75rem',
                fontSize: '0.85rem',
                color: 'var(--v2-ink-muted)',
              }}
            >
              Durable research claims for this subject ({claims.length})
            </p>
            {!claims.length ? (
              <p className='v2-empty'>No ledger claims yet.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {claims.slice(0, 40).map((c, i) => {
                  const text = claimText(c);
                  const url = c.source_url;
                  const meta = [
                    c.verdict,
                    c.evidence_strength || c.evidence_grade,
                  ]
                    .filter(Boolean)
                    .join(' · ');
                  return (
                    <li
                      key={c.id ?? `${text.slice(0, 32)}-${i}`}
                      style={{
                        borderTop: '1px solid var(--v2-rule)',
                        padding: '0.75rem 0',
                      }}
                    >
                      <p style={{ margin: '0 0 0.3rem', lineHeight: 1.45 }}>
                        {text}
                      </p>
                      <p
                        style={{
                          margin: 0,
                          fontSize: '0.82rem',
                          color: 'var(--v2-ink-muted)',
                        }}
                      >
                        {meta || 'claim'}
                        {url ? (
                          <>
                            {' · '}
                            <a href={url} target='_blank' rel='noreferrer'>
                              source
                            </a>
                          </>
                        ) : null}
                      </p>
                      {c.quote ? (
                        <blockquote
                          style={{
                            margin: '0.45rem 0 0',
                            paddingLeft: '0.75rem',
                            borderLeft: '2px solid var(--v2-rule)',
                            color: 'var(--v2-ink-muted)',
                            fontSize: '0.86rem',
                            lineHeight: 1.4,
                          }}
                        >
                          {c.quote}
                        </blockquote>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section style={{ marginTop: '2rem', maxWidth: '48rem' }}>
            <h2
              style={{
                fontFamily: 'var(--v2-font-display)',
                fontSize: '1.15rem',
                margin: '0 0 0.35rem',
              }}
            >
              Citations
            </h2>
            <p
              style={{
                margin: '0 0 0.75rem',
                fontSize: '0.85rem',
                color: 'var(--v2-ink-muted)',
              }}
            >
              Source links attached to the knowledge profile ({citations.length})
            </p>
            {!citations.length ? (
              <p className='v2-empty'>No citations attached yet.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {citations.slice(0, 40).map((c, i) => {
                  const href = c.source_url || c.url;
                  const label =
                    c.title || c.label || href || `Citation ${i + 1}`;
                  return (
                    <li
                      key={`${href || label}-${i}`}
                      style={{
                        borderTop: '1px solid var(--v2-rule)',
                        padding: '0.65rem 0',
                      }}
                    >
                      <p style={{ margin: '0 0 0.25rem', lineHeight: 1.4 }}>
                        {href ? (
                          <a href={href} target='_blank' rel='noreferrer'>
                            {label}
                          </a>
                        ) : (
                          label
                        )}
                      </p>
                      {c.quote ? (
                        <p
                          style={{
                            margin: 0,
                            fontSize: '0.84rem',
                            color: 'var(--v2-ink-muted)',
                            lineHeight: 1.4,
                          }}
                        >
                          {c.quote}
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
