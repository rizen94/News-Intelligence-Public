/**
 * NRI entity resolution v2 — status tabs, park-rate KPIs, context/entity links, parked review.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import {
  contextCentricApi,
  type NriParkedResolution,
  type NriParkedCrossDomain,
  type NriResolvedMention,
  type NriResolutionStats,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { usePublicDemoMode } from '@/contexts/PublicDemoContext';
import {
  PageShell,
  StatCard,
  StatCardRow,
  UiTabs,
  DataTable,
  LoadingState,
  UiBadge,
} from '@/components/ui';

const STATUS_TABS = [
  { id: 'auto_linked', label: 'Auto linked' },
  { id: 'parked', label: 'Parked' },
  { id: 'provisional', label: 'Provisional' },
  { id: 'non_entity_topic', label: 'Non-entity topic' },
  { id: 'cross_domain', label: 'Cross-domain' },
] as const;

type StatusTab = (typeof STATUS_TABS)[number]['id'];

export default function EntityResolutionPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const { readonly: demoReadonly } = usePublicDemoMode();
  const [tab, setTab] = useState<StatusTab>('auto_linked');
  const [resolved, setResolved] = useState<NriResolvedMention[]>([]);
  const [parked, setParked] = useState<NriParkedResolution[]>([]);
  const [crossDomain, setCrossDomain] = useState<NriParkedCrossDomain[]>([]);
  const [hideGeneric, setHideGeneric] = useState(true);
  const [stats, setStats] = useState<NriResolutionStats | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [approveFtm, setApproveFtm] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, p, h, s, cd] = await Promise.all([
        contextCentricApi.getNriResolvedMentions({ domain_key: domain, limit: 150 }),
        contextCentricApi.getNriParked({ domain_key: domain, review_status: 'open', limit: 75 }),
        contextCentricApi.getNriHealth(),
        contextCentricApi.getNriResolutionStats(domain),
        contextCentricApi.getNriParkedCrossDomain({
          exclude_generic: hideGeneric,
          min_domains: 2,
          limit: 100,
        }),
      ]);
      setResolved(r?.items ?? []);
      setParked(p?.items ?? []);
      setHealth(h ?? null);
      setStats(s ?? null);
      setCrossDomain(cd?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, [domain, hideGeneric]);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => {
    if (tab === 'cross_domain') {
      return crossDomain.map((row, idx) => ({
        id: idx,
        mention: row.mention_text,
        context_id: row.sample_context_id,
        entity_profile_id: null as number | null,
        ftm_id: row.domain_list.join(', '),
        score: row.parked_contexts,
        reason: `${row.domains} domains`,
        parked: true as const,
      }));
    }
    if (tab === 'parked') {
      return parked.map(p => ({
        id: p.id,
        mention: p.canonical_name ?? p.mention_text,
        context_id: p.context_id,
        entity_profile_id: null as number | null,
        ftm_id: p.candidate_ftm_id,
        score: p.match_score,
        reason: p.reason,
        parked: true as const,
      }));
    }
    return resolved
      .filter(r => r.status === tab)
      .map(r => ({
        id: r.id,
        mention: r.canonical_name ?? r.mention_text,
        context_id: r.context_id,
        entity_profile_id: r.entity_profile_id,
        ftm_id: r.ftm_id,
        score: r.match_score,
        reason: null as string | null,
        parked: false as const,
      }));
  }, [tab, resolved, parked, crossDomain]);

  const handleApprove = async (parkedId: number, candidateFtmId?: string | null) => {
    await contextCentricApi.reviewNriParked(parkedId, {
      review_status: 'approved',
      candidate_ftm_id: candidateFtmId ?? undefined,
    });
    await load();
  };

  const parkRatePct =
    stats?.park_rate != null ? `${(stats.park_rate * 100).toFixed(1)}%` : '—';
  const autoLinkPct =
    stats?.auto_link_rate != null ? `${(stats.auto_link_rate * 100).toFixed(1)}%` : '—';

  return (
    <PageShell
      title='Entity resolution'
      subtitle={`NRI resolver — ${domain}`}
      breadcrumbs={[
        { label: 'Investigate', to: `/${domain}/investigate` },
        { label: 'Entity resolution' },
      ]}
      actions={
        <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate`)}>
          Hub
        </Button>
      }
    >
      {health && (
        <Alert severity={health.status === 'ok' ? 'success' : 'warning'} sx={{ mb: 2 }}>
          NRI API: {String(health.status ?? 'unknown')}
          {health.reachable === false ? ' — unreachable' : ''}
        </Alert>
      )}

      <StatCardRow>
        <StatCard
          label='Auto-link rate'
          value={autoLinkPct}
          hint='Person/org mentions only (excl. non_entity_topic)'
          tone='success'
        />
        <StatCard
          label='Park rate'
          value={parkRatePct}
          hint='Excludes non_entity_topic subjects'
          tone='warning'
        />
        <StatCard
          label='Entity bridges'
          value={stats?.entity_bridge_count ?? '—'}
        />
        <StatCard
          label='Watermark lag'
          value={stats?.watermark_lag ?? '—'}
          hint={`wm ${stats?.watermark ?? '—'} / max ${stats?.max_mention_id ?? '—'}`}
        />
        <StatCard
          label='Backfill'
          value={
            stats?.backfill_pct != null
              ? `${(stats.backfill_pct * 100).toFixed(1)}%`
              : '—'
          }
          hint={
            stats?.resolved_mentions != null && stats?.total_context_entity_mentions != null
              ? `${stats.resolved_mentions} / ${stats.total_context_entity_mentions} mentions`
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
          hint='Id-space progress through context_entity_mentions'
        />
      </StatCardRow>

      <UiTabs tabs={[...STATUS_TABS]} value={tab} onChange={v => setTab(v as StatusTab)}>
        {tab === 'cross_domain' && (
          <FormControlLabel
            control={
              <Checkbox
                checked={hideGeneric}
                onChange={e => setHideGeneric(e.target.checked)}
              />
            }
            label='Hide generic tokens (US, war, elections, …)'
            sx={{ mb: 1 }}
          />
        )}
        {loading ? (
          <LoadingState message='Loading resolution data…' />
        ) : (
          <DataTable
            rows={rows}
            rowKey={row => row.id}
            columns={[
              {
                key: 'mention',
                header: 'Mention',
                render: row => row.mention,
              },
              {
                key: 'links',
                header: 'Links',
                render: row => (
                  <Stack direction='row' spacing={1}>
                    {row.context_id ? (
                      <Link component={RouterLink} to={`/${domain}/discover/contexts/${row.context_id}`}>
                        Context #{row.context_id}
                      </Link>
                    ) : (
                      '—'
                    )}
                    {row.entity_profile_id ? (
                      <Link
                        component={RouterLink}
                        to={`/${domain}/investigate/entities/${row.entity_profile_id}`}
                      >
                        Profile #{row.entity_profile_id}
                      </Link>
                    ) : null}
                  </Stack>
                ),
              },
              {
                key: 'ftm',
                header: tab === 'cross_domain' ? 'Domains' : 'FtM',
                render: row =>
                  tab === 'cross_domain' ? (
                    row.ftm_id
                  ) : row.parked && demoReadonly ? (
                    <Typography variant='caption' color='text.secondary'>
                      Hidden in demo
                    </Typography>
                  ) : (
                    row.ftm_id ?? '—'
                  ),
              },
              {
                key: 'score',
                header: tab === 'cross_domain' ? 'Parked contexts' : 'Score',
                render: row =>
                  tab === 'cross_domain'
                    ? String(row.score ?? '—')
                    : row.score != null
                      ? row.score.toFixed(3)
                      : '—',
              },
              ...(tab === 'parked'
                ? [
                    {
                      key: 'action',
                      header: 'Review',
                      render: (row: (typeof rows)[number]) =>
                        demoReadonly ? (
                          <UiBadge label='Read-only demo' />
                        ) : (
                          <Stack direction='row' spacing={1} alignItems='center'>
                            <TextField
                              size='small'
                              placeholder='candidate FtM ID'
                              value={approveFtm[row.id] ?? row.ftm_id ?? ''}
                              onChange={e =>
                                setApproveFtm(prev => ({ ...prev, [row.id]: e.target.value }))
                              }
                              sx={{ width: 160 }}
                            />
                            <Button
                              size='small'
                              variant='contained'
                              onClick={() =>
                                handleApprove(
                                  row.id,
                                  approveFtm[row.id] ?? row.ftm_id ?? undefined,
                                )
                              }
                            >
                              Approve
                            </Button>
                          </Stack>
                        ),
                    },
                  ]
                : []),
            ]}
          />
        )}
      </UiTabs>
    </PageShell>
  );
}
