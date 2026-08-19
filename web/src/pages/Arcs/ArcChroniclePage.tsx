/**
 * Arc chronicle — linear longitudinal timeline (geopolitics/politics/finance frames).
 * Not used for medicine/legal/AI research or docket ledgers.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
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

type Protein = {
  domain_key?: string;
  storyline_id?: number;
  title?: string;
  story_kind?: string;
  article_count?: number;
  status?: string;
};

export default function ArcChroniclePage() {
  const { domain, arcId } = useParams<{ domain: string; arcId: string }>();
  const navigate = useNavigate();
  const { domain: domainKey } = useDomain();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!arcId) return;
    setLoading(true);
    try {
      const chronicle = await contextCentricApi.getArcChronicle(arcId);
      setData(chronicle);
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
  const proteins = (data?.supporting_proteins ?? []) as Protein[];
  const bondCount = Number(data?.established_bond_count ?? 0);
  const tracked = (data?.tracked_events ?? []) as Array<Record<string, unknown>>;

  return (
    <PageShell
      title={(arc.display_name as string) ?? arcId ?? 'Arc chronicle'}
      subtitle='Historical ribbon, supporting episodes, and established bonds (linear frames only)'
      breadcrumbs={[
        { label: 'Arcs', to: `/${domainKey}/arcs` },
        { label: arcId ?? 'Chronicle' },
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
        <LoadingState message='Loading arc chronicle…' />
      ) : (
        <>
          {chapter && (
            <UiCard title='Current chapter' sx={{ mb: 2 }}>
              <Typography variant='body2'>
                {(chapter.label as string) ?? (chapter.chapter_id as string) ?? '—'}
              </Typography>
            </UiCard>
          )}

          <UiCard
            title='Supporting episodes'
            subheader={`${proteins.length} episodes · ${bondCount} established bonds · ${tracked.length} tracked events`}
            sx={{ mb: 2 }}
          >
            {proteins.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No linear-kind storylines linked via arc entity QIDs yet.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {proteins.slice(0, 24).map(p => (
                  <Stack
                    key={`${p.domain_key}:${p.storyline_id}`}
                    direction='row'
                    spacing={1}
                    alignItems='center'
                    flexWrap='wrap'
                  >
                    <Chip size='small' label={p.story_kind ?? 'episode'} />
                    <Typography
                      component={RouterLink}
                      to={`/${p.domain_key ?? domain}/stories/${p.storyline_id}`}
                      variant='body2'
                      sx={{ textDecoration: 'none' }}
                    >
                      {p.title ?? `Storyline ${p.storyline_id}`}
                    </Typography>
                    <Typography variant='caption' color='text.secondary'>
                      {p.article_count ?? 0} articles · {p.domain_key}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            )}
          </UiCard>

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
              <UiCard
                title='Macro series'
                subheader={`${(data.macro_series as unknown[]).length} observations loaded`}
              >
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
