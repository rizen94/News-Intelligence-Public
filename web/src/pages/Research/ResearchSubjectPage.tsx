/**
 * Research subject ledger — medicine / AI entity-rooted evidence (not an arc chronicle).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams, useSearchParams } from 'react-router-dom';
import { Chip, Stack, TextField, Button, Typography } from '@mui/material';
import { contextCentricApi } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { PageShell, DataTable, LoadingState, UiCard } from '@/components/ui';

export default function ResearchSubjectPage() {
  const { domain: routeDomain } = useParams<{ domain: string }>();
  const { domain: domainKey } = useDomain();
  const dk = routeDomain || domainKey;
  const [params, setParams] = useSearchParams();
  const [nameInput, setNameInput] = useState(params.get('entity') || 'Autism');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const entityName = params.get('entity') || nameInput;
    if (!entityName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await contextCentricApi.getResearchSubject(dk, {
        entityName: entityName.trim(),
      });
      if ((res as { error?: string }).error) {
        setError(String((res as { error?: string }).error));
        setData(null);
      } else {
        setData(res);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [dk, nameInput, params]);

  useEffect(() => {
    if (params.get('entity')) load();
  }, [load, params]);

  const entity = (data?.entity ?? {}) as Record<string, unknown>;
  const claims = (data?.claims ?? []) as Array<Record<string, unknown>>;
  const proteins = (data?.proteins ?? []) as Array<Record<string, unknown>>;
  const counts = (data?.claim_verdict_counts ?? {}) as Record<string, number>;

  return (
    <PageShell
      title='Research subject'
      subtitle='Entity-rooted evidence ledger (medicine / AI) — hypotheses, papers, proved/disproved'
      breadcrumbs={[
        { label: 'Episodes', to: `/${dk}/storylines` },
        { label: 'Research subject' },
      ]}
    >
      <Stack direction='row' spacing={1} sx={{ mb: 2 }} alignItems='center'>
        <TextField
          size='small'
          label='Entity / ailment'
          value={nameInput}
          onChange={e => setNameInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              setParams({ entity: nameInput.trim() });
            }
          }}
        />
        <Button
          variant='contained'
          onClick={() => setParams({ entity: nameInput.trim() })}
        >
          Load
        </Button>
      </Stack>

      {loading ? (
        <LoadingState message='Loading research subject…' />
      ) : error ? (
        <Typography color='error'>{error}</Typography>
      ) : data ? (
        <>
          <UiCard
            title={(entity.canonical_name as string) || 'Subject'}
            subheader={`id ${entity.id ?? '—'} · ${entity.wikidata_qid ?? 'no QID'}`}
            sx={{ mb: 2 }}
          >
            <Stack direction='row' spacing={1} flexWrap='wrap'>
              {Object.entries(counts).map(([k, v]) =>
                v > 0 ? <Chip key={k} size='small' label={`${k}: ${v}`} /> : null,
              )}
            </Stack>
          </UiCard>

          <UiCard title='Subject episodes' sx={{ mb: 2 }}>
            {proteins.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No evidence_thread / research_topic episodes linked yet.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {proteins.map(p => (
                  <Typography
                    key={String(p.storyline_id)}
                    component={RouterLink}
                    to={`/${dk}/stories/${p.storyline_id}`}
                    variant='body2'
                  >
                    {(p.title as string) || `Storyline ${p.storyline_id}`}
                    {p.subtype_label ? ` · ${p.subtype_label}` : ''}
                    {p.severity_label ? ` · ${p.severity_label}` : ''}
                  </Typography>
                ))}
              </Stack>
            )}
          </UiCard>

          {claims.length === 0 ? (
            <Typography color='text.secondary'>
              No research claims in the ledger yet. POST /api/intelligence/research_subjects/claims
              to record hypothesis verdicts.
            </Typography>
          ) : (
            <DataTable
              rows={claims.map((c, i) => ({ ...c, id: c.id ?? i }))}
              columns={[
                {
                  key: 'verdict',
                  header: 'Verdict',
                  render: row => String(row.verdict ?? '—'),
                },
                {
                  key: 'hypothesis',
                  header: 'Hypothesis',
                  render: row => String(row.hypothesis_text ?? '—'),
                },
                {
                  key: 'finding',
                  header: 'Finding',
                  render: row => String(row.finding_summary ?? '—'),
                },
              ]}
            />
          )}
        </>
      ) : (
        <Typography color='text.secondary'>
          Enter an entity name (e.g. Autism) to open its research subject ledger.
        </Typography>
      )}
    </PageShell>
  );
}
