/**
 * Arc spine view — reference events + macro series for a longitudinal arc.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Button, Stack, Typography } from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { contextCentricApi } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { PageShell, DataTable, LoadingState, UiCard } from '@/components/ui';

type RefEvent = {
  id?: number;
  event_date?: string;
  title?: string;
  summary?: string;
  category?: string;
};

export default function ArcSpinePage() {
  const { domain, arcId } = useParams<{ domain: string; arcId: string }>();
  const navigate = useNavigate();
  const { domain: domainKey } = useDomain();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!arcId) return;
    setLoading(true);
    try {
      const spine = await contextCentricApi.getArcSpine(arcId);
      setData(spine);
    } finally {
      setLoading(false);
    }
  }, [arcId]);

  useEffect(() => {
    load();
  }, [load]);

  const arc = (data?.arc ?? {}) as Record<string, unknown>;
  const events = (data?.reference_events ?? []) as RefEvent[];
  const chapter = data?.current_chapter as Record<string, unknown> | undefined;

  return (
    <PageShell
      title={(arc.display_name as string) ?? arcId ?? 'Arc spine'}
      subtitle='Reference events and macro context'
      breadcrumbs={[
        { label: 'Arcs', to: `/${domainKey}/arcs` },
        { label: arcId ?? 'Spine' },
      ]}
      actions={
        <Stack direction='row' spacing={1}>
          <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/arcs`)}>
            Catalog
          </Button>
          <Button onClick={() => navigate(`/${domain}/arcs/${arcId}/heatmap`)}>
            Heatmap
          </Button>
        </Stack>
      }
    >
      {loading ? (
        <LoadingState message='Loading arc spine…' />
      ) : (
        <>
          {chapter && (
            <UiCard title='Current chapter' sx={{ mb: 2 }}>
              <Typography variant='body2'>
                {(chapter.label as string) ?? (chapter.chapter_id as string) ?? '—'}
              </Typography>
            </UiCard>
          )}
          {events.length === 0 ? (
            <Typography color='text.secondary'>No reference events for this arc.</Typography>
          ) : (
            <DataTable
              rows={events.map((e, i) => ({ ...e, id: e.id ?? i }))}
              columns={[
                {
                  key: 'date',
                  header: 'Date',
                  render: row => row.event_date ?? '—',
                },
                { key: 'title', header: 'Event', render: row => row.title ?? '—' },
                { key: 'cat', header: 'Category', render: row => row.category ?? '—' },
                {
                  key: 'summary',
                  header: 'Summary',
                  render: row => (
                    <Typography variant='body2' sx={{ maxWidth: 420 }}>
                      {row.summary ?? '—'}
                    </Typography>
                  ),
                },
              ]}
            />
          )}
          {Array.isArray(data?.macro_series) && (data.macro_series as unknown[]).length > 0 && (
            <Box sx={{ mt: 3 }}>
              <UiCard title='Macro series' subheader={`${(data.macro_series as unknown[]).length} observations loaded`}>
                <Typography variant='body2' color='text.secondary'>
                  Macro data available — see heatmap for GPR composite overlay.
                </Typography>
              </UiCard>
            </Box>
          )}
        </>
      )}
    </PageShell>
  );
}
