/**
 * Arc weekly briefs — catalog of arcs with links to latest generated report.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import ReactMarkdown from 'react-markdown';
import { contextCentricApi, type ArcReport, type ArcSummary } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { PageShell, DataTable, LoadingState, UiBadge } from '@/components/ui';

type ArcRow = ArcSummary & { id: string; hasReport?: boolean; reportTitle?: string };

export default function ArcWeeklyBriefsPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [rows, setRows] = useState<ArcRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [reportOpen, setReportOpen] = useState<ArcReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const arcs = await contextCentricApi.listArcs();
      const enriched: ArcRow[] = await Promise.all(
        arcs.map(async arc => {
          const report = await contextCentricApi.getLatestArcReport(arc.arc_id).catch(() => null);
          return {
            ...arc,
            id: arc.arc_id,
            hasReport: !!report,
            reportTitle: report?.title ?? undefined,
          };
        }),
      );
      setRows(enriched);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openReport = async (arcId: string) => {
    setLoadingReport(true);
    try {
      const report = await contextCentricApi.getLatestArcReport(arcId);
      if (report) setReportOpen(report);
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <PageShell
      title='Arc weekly briefs'
      subtitle='Latest longitudinal reports per arc'
      breadcrumbs={[
        { label: 'Outputs' },
        { label: 'Arc reports' },
      ]}
      actions={
        <Button size='small' onClick={() => navigate(`/${domain}/arcs`)}>
          Arc catalog
        </Button>
      }
    >
      {loading ? (
        <LoadingState message='Loading arc reports…' />
      ) : (
        <DataTable
          rows={rows}
          columns={[
            {
              key: 'arc',
              header: 'Arc',
              render: row => row.display_name ?? row.arc_id,
            },
            {
              key: 'status',
              header: 'Report',
              render: row =>
                row.hasReport ? (
                  <UiBadge label={row.reportTitle ?? 'Available'} color='success' />
                ) : (
                  <UiBadge label='Not generated' />
                ),
            },
            {
              key: 'actions',
              header: 'Actions',
              render: row => (
                <Stack direction='row' spacing={1}>
                  <Button
                    size='small'
                    disabled={!row.hasReport || loadingReport}
                    onClick={() => openReport(row.arc_id)}
                  >
                    Latest brief
                  </Button>
                  <Button
                    size='small'
                    onClick={() => navigate(`/${domain}/arcs/${row.arc_id}/spine`)}
                  >
                    Spine
                  </Button>
                </Stack>
              ),
            },
          ]}
        />
      )}

      <Dialog
        open={!!reportOpen}
        onClose={() => setReportOpen(null)}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>{reportOpen?.title ?? `Arc report — ${reportOpen?.arc_id}`}</DialogTitle>
        <DialogContent dividers>
          {reportOpen?.generated_at && (
            <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 2 }}>
              Generated {new Date(reportOpen.generated_at).toLocaleString()}
            </Typography>
          )}
          <Box sx={{ '& p': { mb: 1.5 } }}>
            <ReactMarkdown>{reportOpen?.content_markdown ?? ''}</ReactMarkdown>
          </Box>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
