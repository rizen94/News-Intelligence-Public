/**
 * NRI vault hypotheses v2 — loop timeline, shadow badge, ACH frontmatter fields.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Stack, Typography } from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import {
  contextCentricApi,
  type NriHypothesis,
  type NriHypothesisDetail,
  type NriLoopRun,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import {
  PageShell,
  DataTable,
  DetailDrawer,
  LoadingState,
  UiBadge,
  UiCard,
  StatCard,
  StatCardRow,
} from '@/components/ui';

function parseFrontmatter(body?: string): Record<string, string> {
  if (!body) return {};
  const match = body.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return {};
  const out: Record<string, string> = {};
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':');
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
    out[key] = val;
  }
  return out;
}

function isShadowHypothesis(h: NriHypothesis, fm?: Record<string, string>): boolean {
  const branch = h.vault_branch ?? fm?.vault_branch ?? fm?.branch ?? '';
  const path = (h as NriHypothesisDetail).path ?? '';
  return /shadow/i.test(branch) || /shadow/i.test(path);
}

const ACH_KEYS = [
  'ach_alternatives',
  'ach_evidence_for',
  'ach_evidence_against',
  'ach_assessment',
  'ach_key_assumption',
];

export default function HypothesesPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [items, setItems] = useState<NriHypothesis[]>([]);
  const [loopRuns, setLoopRuns] = useState<NriLoopRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<NriHypothesisDetail | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hyps, loops] = await Promise.all([
        contextCentricApi.getNriHypotheses({ limit: 100 }),
        contextCentricApi.getNriLoopRuns(15),
      ]);
      setItems(hyps?.items ?? []);
      setLoopRuns(loops?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const latestLoop = loopRuns[0];

  const openDetail = async (hypId: string) => {
    const detail = await contextCentricApi.getNriHypothesis(hypId);
    const fm = parseFrontmatter(detail.body);
    setSelected({ ...detail, frontmatter: fm });
  };

  const drawerFm = useMemo(
    () =>
      selected?.frontmatter ??
      parseFrontmatter(selected?.body) ??
      ({} as Record<string, string>),
    [selected],
  );

  const bodyWithoutFm = useMemo(() => {
    if (!selected?.body) return '';
    return selected.body.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '').trim();
  }, [selected?.body]);

  return (
    <PageShell
      title='Investigative hypotheses'
      subtitle='NRI vault — ACH structured hypotheses from loop iterations'
      breadcrumbs={[
        { label: 'Investigate', to: `/${domain}/investigate` },
        { label: 'Hypotheses' },
      ]}
      actions={
        <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate`)}>
          Hub
        </Button>
      }
    >
      {latestLoop && (
        <StatCardRow>
          <StatCard label='Latest iteration' value={latestLoop.iteration ?? '—'} />
          <StatCard
            label='Shadow branch'
            value={latestLoop.shadow_branch ?? 'main'}
          />
          <StatCard label='Added' value={latestLoop.added_count ?? 0} tone='success' />
          <StatCard label='Killed' value={latestLoop.killed_count ?? 0} tone='error' />
          <StatCard label='Demoted' value={latestLoop.demoted_count ?? 0} tone='warning' />
        </StatCardRow>
      )}

      {loopRuns.length > 0 && (
        <UiCard title='Loop run timeline' sx={{ mb: 3 }}>
          <Stack spacing={1}>
            {loopRuns.map(run => (
              <Stack
                key={run.id}
                direction='row'
                spacing={1}
                alignItems='center'
                flexWrap='wrap'
              >
                <Typography variant='body2' fontWeight={600}>
                  #{run.iteration ?? run.id}
                </Typography>
                {run.shadow_branch && <UiBadge label={run.shadow_branch} color='secondary' />}
                <Typography variant='caption' color='text.secondary'>
                  {run.ran_at ? new Date(run.ran_at).toLocaleString() : '—'}
                </Typography>
                <Typography variant='caption'>
                  +{run.added_count ?? 0} / −{run.killed_count ?? 0} / ↓
                  {run.demoted_count ?? 0}
                </Typography>
              </Stack>
            ))}
          </Stack>
        </UiCard>
      )}

      {loading ? (
        <LoadingState message='Loading hypotheses…' />
      ) : items.length === 0 ? (
        <Typography color='text.secondary'>
          No hypotheses in vault yet. Loop runs in shadow mode write here when patterns are
          detected.
        </Typography>
      ) : (
        <DataTable
          rows={items.map(h => ({ ...h, id: h.hyp_id }))}
          rowKey={row => row.hyp_id}
          onRowClick={row => openDetail(row.hyp_id)}
          columns={[
              { key: 'id', header: 'ID', render: row => row.hyp_id },
              {
                key: 'claim',
                header: 'Claim',
                render: row => row.claim ?? '—',
              },
              {
                key: 'status',
                header: 'Status',
                render: row => <UiBadge label={row.status ?? 'open'} />,
              },
              {
                key: 'branch',
                header: 'Vault',
                render: row =>
                  isShadowHypothesis(row) ? (
                    <UiBadge label='shadow' color='warning' />
                  ) : (
                    <UiBadge label='main' />
                  ),
              },
              {
                key: 'conf',
                header: 'Confidence',
                render: row => row.confidence ?? '—',
              },
            ]}
          />
      )}

      <DetailDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.hyp_id ?? ''}
        subtitle={selected?.claim ?? undefined}
      >
        {selected && (
          <>
            <Stack direction='row' spacing={1} sx={{ mb: 2 }} flexWrap='wrap'>
              <UiBadge label={selected.status ?? 'open'} />
              {isShadowHypothesis(selected, drawerFm) && (
                <UiBadge label='shadow vault' color='warning' />
              )}
              {selected.iteration_introduced != null && (
                <UiBadge label={`iter ${selected.iteration_introduced}`} />
              )}
              <Typography variant='caption' color='text.secondary'>
                test: {selected.test_status ?? 'pending'}
              </Typography>
            </Stack>

            {ACH_KEYS.filter(k => drawerFm[k]).length > 0 && (
              <UiCard title='ACH analysis' sx={{ mb: 2 }}>
                {ACH_KEYS.filter(k => drawerFm[k]).map(k => (
                  <Box key={k} sx={{ mb: 1.5 }}>
                    <Typography variant='caption' color='text.secondary' textTransform='uppercase'>
                      {k.replace(/^ach_/, '').replace(/_/g, ' ')}
                    </Typography>
                    <Typography variant='body2' sx={{ whiteSpace: 'pre-wrap' }}>
                      {drawerFm[k]}
                    </Typography>
                  </Box>
                ))}
              </UiCard>
            )}

            <Typography variant='body2' sx={{ whiteSpace: 'pre-wrap' }}>
              {bodyWithoutFm || selected.body}
            </Typography>
          </>
        )}
      </DetailDrawer>
    </PageShell>
  );
}
