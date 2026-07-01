/**
 * Arc tension heatmap — monthly composite scores with analogue comparison.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Button, Stack, Typography } from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { contextCentricApi } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { PageShell, DataTable, LoadingState, UiCard } from '@/components/ui';

type HeatCell = {
  month_start?: string;
  region_key?: string;
  event_count?: number;
  fatalities_sum?: number;
  gpr_index?: number;
  composite_score?: number;
  sources?: string[];
};

export default function ArcHeatmapPage() {
  const { domain, arcId } = useParams<{ domain: string; arcId: string }>();
  const navigate = useNavigate();
  const { domain: domainKey } = useDomain();
  const [heatmap, setHeatmap] = useState<Record<string, unknown> | null>(null);
  const [analogues, setAnalogues] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!arcId) return;
    setLoading(true);
    try {
      const [hm, an] = await Promise.all([
        contextCentricApi.getArcHeatmap(arcId, 24),
        contextCentricApi.getArcAnalogues(arcId, 4),
      ]);
      setHeatmap(hm);
      setAnalogues(an);
    } finally {
      setLoading(false);
    }
  }, [arcId]);

  useEffect(() => {
    load();
  }, [load]);

  const cells = (heatmap?.cells ?? []) as HeatCell[];
  const patterns = (analogues?.patterns ?? []) as Record<string, unknown>[];
  const correlations = (analogues?.correlations ?? []) as Record<string, unknown>[];

  return (
    <PageShell
      title={`Heatmap — ${arcId}`}
      subtitle='Tension composite (events + GPR index)'
      breadcrumbs={[
        { label: 'Arcs', to: `/${domainKey}/arcs` },
        { label: arcId ?? 'Heatmap' },
      ]}
      actions={
        <Stack direction='row' spacing={1}>
          <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/arcs`)}>
            Catalog
          </Button>
          <Button onClick={() => navigate(`/${domain}/arcs/${arcId}/spine`)}>
            Spine
          </Button>
        </Stack>
      }
    >
      {loading ? (
        <LoadingState message='Loading heatmap…' />
      ) : (
        <>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
            GPR series: {String(heatmap?.gpr_series_id ?? 'GPRHICU')} ·{' '}
            {heatmap?.months ?? 24} months
          </Typography>
          {cells.length === 0 ? (
            <Typography color='text.secondary'>No heatmap cells — refresh mat view after ingest.</Typography>
          ) : (
            <DataTable
              rows={cells.map((c, i) => ({ ...c, id: `${c.month_start}-${c.region_key}-${i}` }))}
              columns={[
                { key: 'month', header: 'Month', render: row => row.month_start ?? '—' },
                { key: 'region', header: 'Region', render: row => row.region_key ?? '—' },
                { key: 'events', header: 'Events', render: row => row.event_count ?? 0 },
                { key: 'fatal', header: 'Fatalities', render: row => row.fatalities_sum ?? 0 },
                { key: 'gpr', header: 'GPR', render: row => row.gpr_index?.toFixed(2) ?? '—' },
                {
                  key: 'composite',
                  header: 'Composite',
                  render: row => row.composite_score?.toFixed(3) ?? '—',
                },
              ]}
            />
          )}

          {(patterns.length > 0 || correlations.length > 0) && (
            <Box sx={{ mt: 3 }}>
              <UiCard title='Historical analogues' subheader='Rhymes-with prior arcs — not predictive'>
                {patterns.map((p, i) => (
                  <Typography key={`p-${i}`} variant='body2' sx={{ mb: 1 }}>
                    {(p.pattern_type as string) ?? 'pattern'}:{' '}
                    {(p.summary as string) ?? JSON.stringify(p).slice(0, 120)}
                  </Typography>
                ))}
                {correlations.map((c, i) => (
                  <Typography key={`c-${i}`} variant='body2' sx={{ mb: 1 }}>
                    {(c.correlation_type as string) ?? 'correlation'}:{' '}
                    {(c.label as string) ?? JSON.stringify(c).slice(0, 120)}
                  </Typography>
                ))}
              </UiCard>
            </Box>
          )}
        </>
      )}
    </PageShell>
  );
}
