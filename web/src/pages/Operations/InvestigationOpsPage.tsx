/**
 * Investigation operations dashboard — resolver, loop, FtM cache, and bridge QA.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Stack, Typography } from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import {
  investigationApi,
} from '@/services/api/investigationApi';
import type {
  NriEntityBridge,
  NriLoopRun,
  NriParkedCrossDomain,
  NriResolutionStats,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import {
  PageShell,
  StatCard,
  StatCardRow,
  UiCard,
  LoadingState,
  DataTable,
  UiBadge,
} from '@/components/ui';

export default function InvestigationOpsPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [stats, setStats] = useState<NriResolutionStats | null>(null);
  const [loopRuns, setLoopRuns] = useState<NriLoopRun[]>([]);
  const [ftmCache, setFtmCache] = useState<Record<string, number>>({});
  const [crossDomain, setCrossDomain] = useState<NriParkedCrossDomain[]>([]);
  const [bridgeQa, setBridgeQa] = useState<NriEntityBridge[]>([]);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [loadErrors, setLoadErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadErrors([]);
    try {
      const results = await Promise.allSettled([
        investigationApi.getResolutionStats(domain),
        investigationApi.getLoopRuns(25),
        investigationApi.getFtMCacheStats(),
        investigationApi.getHealth(),
        investigationApi.getParkedCrossDomain({ exclude_generic: true, limit: 10 }),
        investigationApi.getBridgeQaAudit({ domain_key: domain, qa_status: 'suspect', limit: 15 }),
      ]);
      const labels = [
        'resolution stats',
        'loop runs',
        'FtM cache',
        'health',
        'cross-domain parked',
        'bridge QA',
      ];
      const errors: string[] = [];
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          const reason =
            result.reason instanceof Error ? result.reason.message : String(result.reason);
          errors.push(`${labels[index]}: ${reason}`);
        }
      });
      setLoadErrors(errors);

      const [s, loops, ftm, h, cd, qa] = results;
      if (s.status === 'fulfilled') setStats(s.value);
      if (loops.status === 'fulfilled') setLoopRuns(loops.value?.items ?? []);
      if (ftm.status === 'fulfilled') setFtmCache(ftm.value?.bridged_by_dataset ?? {});
      if (h.status === 'fulfilled') setHealth(h.value ?? null);
      if (cd.status === 'fulfilled') setCrossDomain(cd.value?.items ?? []);
      if (qa.status === 'fulfilled') setBridgeQa(qa.value?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, [domain]);

  useEffect(() => {
    load();
  }, [load]);

  const byStatus = stats?.by_status ?? {};
  const ftmRows = Object.entries(ftmCache).map(([dataset, count]) => ({
    id: dataset,
    dataset,
    count,
  }));

  return (
    <PageShell
      title='Investigation operations'
      subtitle='Resolver, loop, identity spine, and bridge QA metrics'
      breadcrumbs={[{ label: 'Operations' }, { label: 'Investigation ops' }]}
      actions={
        <Stack direction='row' spacing={1}>
          <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/monitor`)}>
            Monitor
          </Button>
          <Button size='small' onClick={load}>
            Refresh
          </Button>
        </Stack>
      }
    >
      {loadErrors.length > 0 && (
        <Alert severity='error' sx={{ mb: 2 }}>
          Some investigation metrics failed to load: {loadErrors.join('; ')}
        </Alert>
      )}

      {health && (
        <Alert severity={health.status === 'ok' ? 'success' : 'warning'} sx={{ mb: 2 }}>
          Investigation service: {String(health.status ?? 'unknown')}
          {health.reachable === false ? ' — unreachable' : ''}
        </Alert>
      )}

      {loading ? (
        <LoadingState message='Loading investigation metrics…' />
      ) : (
        <>
          <StatCardRow>
            <StatCard
              label='Auto-link rate'
              value={
                stats?.auto_link_rate != null
                  ? `${(stats.auto_link_rate * 100).toFixed(1)}%`
                  : '—'
              }
              tone='success'
            />
            <StatCard
              label='Park rate'
              value={
                stats?.park_rate != null ? `${(stats.park_rate * 100).toFixed(1)}%` : '—'
              }
              hint='Excl. non_entity_topic'
              tone='warning'
            />
            <StatCard label='Entity bridges' value={stats?.entity_bridge_count ?? '—'} />
            <StatCard label='Watermark lag' value={stats?.watermark_lag ?? '—'} />
            <StatCard
              label='Backfill'
              value={
                stats?.backfill_pct != null
                  ? `${(stats.backfill_pct * 100).toFixed(1)}%`
                  : '—'
              }
              hint={
                stats?.resolved_mentions != null
                  ? `${stats.resolved_mentions} resolved`
                  : undefined
              }
            />
            <StatCard
              label='Resolver watermark'
              value={
                stats?.watermark_pct != null
                  ? `${(stats.watermark_pct * 100).toFixed(1)}%`
                  : '—'
              }
            />
          </StatCardRow>

          <UiCard title='Bridge QA — suspect links' sx={{ mb: 3 }}>
            {bridgeQa.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No suspect bridge links for this domain.
              </Typography>
            ) : (
              <DataTable
                rows={bridgeQa.map((row, i) => ({ ...row, id: row.entity_profile_id ?? i }))}
                rowKey={row => row.id}
                columns={[
                  {
                    key: 'ep',
                    header: 'Profile',
                    render: row => row.entity_profile_id,
                  },
                  {
                    key: 'ni',
                    header: 'NI name',
                    render: row => row.ni_canonical_name ?? '—',
                  },
                  {
                    key: 'ftm',
                    header: 'FtM caption',
                    render: row => row.caption ?? row.ftm_id,
                  },
                  {
                    key: 'qa',
                    header: 'QA',
                    render: row => (
                      <UiBadge
                        label={row.qa_status ?? 'unknown'}
                        color={row.qa_status === 'mismatch' ? 'error' : 'warning'}
                      />
                    ),
                  },
                  {
                    key: 'sim',
                    header: 'Similarity',
                    render: row =>
                      row.name_similarity != null
                        ? `${(row.name_similarity * 100).toFixed(0)}%`
                        : '—',
                  },
                ]}
              />
            )}
          </UiCard>

          <UiCard title='Cross-domain parked (top 10)' sx={{ mb: 3 }}>
            {crossDomain.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No cross-domain parked mentions (generic tokens excluded).
              </Typography>
            ) : (
              <DataTable
                rows={crossDomain.map((row, i) => ({ ...row, id: i }))}
                rowKey={row => row.id}
                columns={[
                  { key: 'm', header: 'Mention', render: row => row.mention_text },
                  { key: 'd', header: 'Domains', render: row => row.domains },
                  { key: 'p', header: 'Parked', render: row => row.parked_contexts },
                  {
                    key: 'dl',
                    header: 'Domain list',
                    render: row => row.domain_list.join(', '),
                  },
                ]}
              />
            )}
          </UiCard>

          <UiCard title='Resolution by status' sx={{ mb: 3 }}>
            <Stack direction='row' spacing={1} flexWrap='wrap'>
              {Object.entries(byStatus).map(([status, count]) => (
                <UiBadge key={status} label={`${status}: ${count}`} />
              ))}
              {Object.keys(byStatus).length === 0 && (
                <Typography variant='body2' color='text.secondary'>
                  No resolved mentions yet.
                </Typography>
              )}
            </Stack>
          </UiCard>

          <UiCard title='FtM cache by dataset' sx={{ mb: 3 }}>
            {ftmRows.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No cached FtM entities.
              </Typography>
            ) : (
              <DataTable
                rows={ftmRows}
                columns={[
                  { key: 'ds', header: 'Dataset', render: row => row.dataset },
                  { key: 'cnt', header: 'Cached entities', render: row => row.count },
                ]}
              />
            )}
          </UiCard>

          <UiCard title='Loop run history'>
            {loopRuns.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No loop runs recorded.
              </Typography>
            ) : (
              <DataTable
                rows={loopRuns}
                columns={[
                  { key: 'iter', header: 'Iter', render: row => row.iteration ?? row.id },
                  {
                    key: 'branch',
                    header: 'Branch',
                    render: row => row.shadow_branch ?? 'main',
                  },
                  {
                    key: 'ran',
                    header: 'Ran at',
                    render: row =>
                      row.ran_at ? new Date(row.ran_at).toLocaleString() : '—',
                  },
                  { key: 'add', header: '+', render: row => row.added_count ?? 0 },
                  { key: 'kill', header: '−', render: row => row.killed_count ?? 0 },
                  { key: 'dem', header: '↓', render: row => row.demoted_count ?? 0 },
                  { key: 'dor', header: '○', render: row => row.dormant_count ?? 0 },
                ]}
              />
            )}
          </UiCard>
        </>
      )}
    </PageShell>
  );
}
