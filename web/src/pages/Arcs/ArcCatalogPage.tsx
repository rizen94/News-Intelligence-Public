/**
 * Longitudinal arc catalog — links to spine, heatmap, and reports per arc.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Button, Link, Stack, Typography } from '@mui/material';
import { contextCentricApi, type ArcSummary } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { PageShell, DataTable, LoadingState } from '@/components/ui';

export default function ArcCatalogPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [arcs, setArcs] = useState<ArcSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await contextCentricApi.listArcs();
      setArcs(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PageShell
      title='Arc catalog'
      subtitle='Longitudinal intelligence arcs — historical context spines'
      breadcrumbs={[{ label: 'Arcs' }]}
    >
      {loading ? (
        <LoadingState message='Loading arcs…' />
      ) : arcs.length === 0 ? (
        <Typography color='text.secondary'>No active arcs configured.</Typography>
      ) : (
        <DataTable
          rows={arcs.map(a => ({ ...a, id: a.arc_id }))}
          columns={[
            {
              key: 'name',
              header: 'Arc',
              render: row => (
                <Stack>
                  <Typography variant='body2' fontWeight={600}>
                    {row.display_name ?? row.arc_id}
                  </Typography>
                  <Typography variant='caption' color='text.secondary'>
                    {row.arc_id}
                  </Typography>
                </Stack>
              ),
            },
            {
              key: 'desc',
              header: 'Description',
              render: row => (
                <Typography variant='body2' color='text.secondary' sx={{ maxWidth: 360 }}>
                  {row.description ?? '—'}
                </Typography>
              ),
            },
            {
              key: 'dates',
              header: 'Span',
              render: row =>
                [row.start_date, row.end_date].filter(Boolean).join(' → ') || '—',
            },
            {
              key: 'actions',
              header: 'Views',
              render: row => (
                <Stack direction='row' spacing={1} flexWrap='wrap'>
                  <Button
                    size='small'
                    component={RouterLink}
                    to={`/${domain}/arcs/${row.arc_id}/spine`}
                  >
                    Spine
                  </Button>
                  <Button
                    size='small'
                    component={RouterLink}
                    to={`/${domain}/arcs/${row.arc_id}/heatmap`}
                  >
                    Heatmap
                  </Button>
                  <Link
                    component={RouterLink}
                    to={`/${domain}/arcs/reports`}
                    variant='body2'
                  >
                    Reports
                  </Link>
                </Stack>
              ),
            },
          ]}
        />
      )}
      <Button sx={{ mt: 2 }} size='small' onClick={() => navigate(`/${domain}/arcs/reports`)}>
        Arc weekly briefs
      </Button>
    </PageShell>
  );
}
