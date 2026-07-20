/**
 * Rolling 12-month arcs list/detail (Phase B).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button, Stack, Typography } from '@mui/material';
import { PageShell, DataTable, LoadingState } from '@/components/ui';
import { getApi } from '@/services/api/client';
import { useDomain } from '@/contexts/DomainContext';

type RollingArc = {
  id: number;
  domain_key: string;
  theme_key: string;
  title: string;
  strength?: number;
  summary?: string;
  material_updated_at?: string;
  chapters?: Array<{ label?: string; storyline_ids?: number[] }>;
};

export default function RollingArcsPage() {
  const { domain } = useDomain();
  const [arcs, setArcs] = useState<RollingArc[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getApi().get('/api/rolling_arcs', {
        params: { domain_key: domain || undefined },
      });
      setArcs((res.data?.arcs as RollingArc[]) || []);
    } finally {
      setLoading(false);
    }
  }, [domain]);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await getApi().post('/api/rolling_arcs/refresh');
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <PageShell
      title='Rolling 12‑month arcs'
      subtitle='Mid-horizon coherence across the last year of storylines and timeline atoms'
      breadcrumbs={[{ label: 'Arcs' }, { label: 'Rolling' }]}
      actions={
        <Button variant='outlined' onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Refreshing…' : 'Refresh arcs'}
        </Button>
      }
    >
      {loading ? (
        <LoadingState message='Loading rolling arcs…' />
      ) : arcs.length === 0 ? (
        <Stack spacing={1}>
          <Typography color='text.secondary'>
            No rolling arcs yet. Run refresh to chapterize the last 365 days.
          </Typography>
        </Stack>
      ) : (
        <DataTable
          rows={arcs}
          columns={[
            { key: 'title', header: 'Title', render: r => r.title },
            { key: 'domain', header: 'Domain', render: r => r.domain_key },
            { key: 'theme', header: 'Theme', render: r => r.theme_key },
            {
              key: 'strength',
              header: 'Strength',
              render: r => (r.strength != null ? Number(r.strength).toFixed(2) : '—'),
            },
            {
              key: 'chapters',
              header: 'Chapters',
              render: r => String((r.chapters || []).length),
            },
            {
              key: 'updated',
              header: 'Updated',
              render: r =>
                r.material_updated_at
                  ? new Date(r.material_updated_at).toLocaleString()
                  : '—',
            },
          ]}
        />
      )}
    </PageShell>
  );
}
