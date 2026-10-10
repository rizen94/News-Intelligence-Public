/**
 * Research — high-level topics → subject fact sheets (not paper headlines).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  readerApi,
  type ResearchDomainBlock,
  type ResearchSubjectSummary,
} from '../../../services/api/readerResearch';

const DOMAIN_ORDER = [
  'neurodiversity',
  'artificial-intelligence',
  'medicine',
] as const;

export default function ResearchPage() {
  const [subjects, setSubjects] = useState<ResearchSubjectSummary[]>([]);
  const [domains, setDomains] = useState<ResearchDomainBlock[]>([]);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPending(true);
    setError(null);
    readerApi
      .listResearchSubjects(undefined, 50)
      .then(data => {
        if (cancelled) return;
        if (!data?.ok && !(data.subjects || []).length) {
          setError('Could not load subjects');
        }
        setSubjects(data.subjects || []);
        setDomains(data.domains || []);
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
  }, []);

  const byDomain = useMemo(() => {
    const map = new Map<string, ResearchSubjectSummary[]>();
    for (const s of subjects) {
      const dk = s.domain_key || 'other';
      const list = map.get(dk) || [];
      list.push(s);
      map.set(dk, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    }
    return map;
  }, [subjects]);

  const domainMeta = useMemo(() => {
    const map = new Map<string, ResearchDomainBlock>();
    for (const d of domains) map.set(d.domain_key, d);
    return map;
  }, [domains]);

  const domainKeys = [
    ...DOMAIN_ORDER.filter(d => byDomain.has(d) || domainMeta.has(d)),
    ...[...new Set([...byDomain.keys(), ...domainMeta.keys()])].filter(
      d => !(DOMAIN_ORDER as readonly string[]).includes(d)
    ),
  ];

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
        What we know
      </h1>
      <p style={{ color: 'var(--v2-ink-muted)', maxWidth: '40rem' }}>
        High-level topics with accumulating fact sheets — supported, not
        supported, and open — from appraised papers. Keywords mirror vault
        research topic notes.
      </p>
      <hr className='v2-section-rule' />

      {pending ? <p className='v2-empty'>Loading topics…</p> : null}
      {error ? <p className='v2-empty'>{error}</p> : null}
      {!pending && !subjects.length && !domains.length && !error ? (
        <p className='v2-empty'>
          No subject fact sheets yet. Appraisal will open boards as papers are
          graded.
        </p>
      ) : null}

      {domainKeys.map(dk => {
        const list = byDomain.get(dk) || [];
        const meta = domainMeta.get(dk);
        const label = meta?.label || dk;
        const keywords = meta?.keywords || [];
        return (
          <section key={dk} style={{ marginTop: '1.75rem' }}>
            <h2
              style={{
                fontFamily: 'var(--v2-font-display)',
                fontSize: '1.2rem',
                margin: '0 0 0.35rem',
              }}
            >
              {label}
            </h2>
            {keywords.length ? (
              <p
                style={{
                  margin: '0 0 0.85rem',
                  fontSize: '0.88rem',
                  color: 'var(--v2-ink-muted)',
                  lineHeight: 1.45,
                  maxWidth: '48rem',
                }}
              >
                {keywords.join(' · ')}
              </p>
            ) : null}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(15rem, 1fr))',
                gap: '0 1.5rem',
              }}
            >
              {list.map(s => {
                const c = s.assertion_counts || {
                  is: 0,
                  is_not: 0,
                  open: 0,
                };
                const href =
                  s.href ||
                  `/research/subjects/${s.domain_key}/${s.canonical_entity_id}`;
                return (
                  <Link
                    key={`${s.domain_key}-${s.canonical_entity_id}`}
                    to={href}
                    style={{
                      textDecoration: 'none',
                      color: 'inherit',
                      borderTop: '1px solid var(--v2-rule)',
                      padding: '0.85rem 0',
                    }}
                  >
                    <div
                      style={{
                        fontFamily: 'var(--v2-font-display)',
                        fontSize: '1.15rem',
                      }}
                    >
                      {s.title}
                    </div>
                    <div
                      style={{
                        fontSize: '0.85rem',
                        color: 'var(--v2-ink-muted)',
                        marginTop: '0.35rem',
                        lineHeight: 1.4,
                      }}
                    >
                      {c.is} supported · {c.is_not} not supported · {c.open} open
                    </div>
                  </Link>
                );
              })}
            </div>
            {!list.length && !pending ? (
              <p className='v2-empty' style={{ marginTop: '0.5rem' }}>
                No fact sheets open yet for this domain.
              </p>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
