/**
 * Matter docket ledger — legal case rulings + running legal_status.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Chip, Stack, Typography } from '@mui/material';
import { contextCentricApi } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { PageShell, DataTable, LoadingState, UiCard } from '@/components/ui';

export default function MatterDocketPage() {
  const { domain, storylineId } = useParams<{ domain: string; storylineId: string }>();
  const { domain: domainKey } = useDomain();
  const dk = domain || domainKey || 'legal';
  const sid = Number(storylineId);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(sid)) return;
    setLoading(true);
    setError(null);
    try {
      const res = await contextCentricApi.getMatterDocket(sid, dk);
      if ((res as { error?: string }).error) {
        setError(String((res as { error?: string }).error));
        setData(null);
      } else {
        setData(res);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [dk, sid]);

  useEffect(() => {
    load();
  }, [load]);

  const protein = (data?.protein ?? {}) as Record<string, unknown>;
  const rulings = (data?.rulings ?? []) as Array<Record<string, unknown>>;
  const status = String(data?.legal_status ?? 'unsettled');

  return (
    <PageShell
      title={(protein.title as string) || `Docket ${storylineId}`}
      subtitle='Matter docket — procedural rulings and legal status (episode-backed)'
      breadcrumbs={[
        { label: 'Episodes', to: `/${dk}/storylines` },
        { label: `Docket ${storylineId}` },
      ]}
    >
      {loading ? (
        <LoadingState message='Loading matter docket…' />
      ) : error ? (
        <Typography color='error'>{error}</Typography>
      ) : (
        <>
          <UiCard title='Legal status' sx={{ mb: 2 }}>
            <Stack direction='row' spacing={1} alignItems='center'>
              <Chip
                label={status}
                color={
                  status === 'legal'
                    ? 'success'
                    : status === 'not_legal'
                      ? 'error'
                      : status === 'contested'
                        ? 'warning'
                        : 'default'
                }
              />
              <Typography variant='body2' color='text.secondary'>
                {(data?.status_rationale as string) || 'No rationale recorded yet.'}
              </Typography>
            </Stack>
          </UiCard>

          {rulings.length === 0 ? (
            <Typography color='text.secondary'>
              No rulings yet. POST /api/intelligence/matter_dockets/rulings to append holdings.
            </Typography>
          ) : (
            <DataTable
              rows={rulings.map((r, i) => ({ ...r, id: r.id ?? i }))}
              columns={[
                {
                  key: 'date',
                  header: 'Date',
                  render: row => String(row.decision_date ?? '—'),
                },
                { key: 'court', header: 'Court', render: row => String(row.court ?? '—') },
                {
                  key: 'delta',
                  header: 'Status delta',
                  render: row => String(row.status_delta ?? '—'),
                },
                {
                  key: 'holding',
                  header: 'Holding',
                  render: row => String(row.holding_summary ?? '—'),
                },
              ]}
            />
          )}
        </>
      )}
    </PageShell>
  );
}
