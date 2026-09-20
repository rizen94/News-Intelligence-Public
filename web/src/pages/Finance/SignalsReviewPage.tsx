/**
 * Trading signals HITL review queue (Phase C). No auto-execution.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button, Stack, TextField, Typography } from '@mui/material';
import { PageShell, DataTable, LoadingState } from '@/components/ui';
import { getApi } from '@/services/api/client';

type SignalRow = {
  id: number;
  ticker: string;
  idea_summary: string;
  expected_move_pct?: number;
  confidence?: number;
  review_status: string;
  created_at?: string;
};

export default function SignalsReviewPage() {
  const [rows, setRows] = useState<SignalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getApi().get('/api/signals', {
        params: { review_status: 'pending' },
      });
      setRows((res.data?.signals as SignalRow[]) || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const review = async (id: number, decision: 'approved' | 'rejected') => {
    setBusyId(id);
    try {
      await getApi().post(`/api/signals/${id}/review`, {
        decision,
        reason,
        reviewed_by: 'operator',
      });
      setReason('');
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const generate = async () => {
    setLoading(true);
    try {
      await getApi().post('/api/signals/generate', null, {
        params: { days: 14, limit: 15 },
      });
      await load();
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageShell
      title='Trade signal review'
      subtitle='Event → ticker impact ideas — human approve/reject only (no auto-execution)'
      breadcrumbs={[{ label: 'Finance' }, { label: 'Signals' }]}
      actions={
        <Button variant='outlined' onClick={generate}>
          Generate from events
        </Button>
      }
    >
      <TextField
        size='small'
        fullWidth
        label='Review reason'
        value={reason}
        onChange={e => setReason(e.target.value)}
        sx={{ mb: 2, maxWidth: 480 }}
      />
      {loading ? (
        <LoadingState message='Loading signals…' />
      ) : rows.length === 0 ? (
        <Typography color='text.secondary'>No pending signals.</Typography>
      ) : (
        <DataTable
          rows={rows}
          columns={[
            { key: 'ticker', header: 'Ticker', render: r => r.ticker },
            { key: 'idea', header: 'Idea', render: r => r.idea_summary },
            {
              key: 'move',
              header: 'Expected %',
              render: r =>
                r.expected_move_pct != null ? String(r.expected_move_pct) : '—',
            },
            {
              key: 'conf',
              header: 'Confidence',
              render: r =>
                r.confidence != null ? Number(r.confidence).toFixed(2) : '—',
            },
            {
              key: 'actions',
              header: 'Review',
              render: r => (
                <Stack direction='row' spacing={1}>
                  <Button
                    size='small'
                    variant='contained'
                    disabled={busyId === r.id}
                    onClick={() => review(r.id, 'approved')}
                  >
                    Approve
                  </Button>
                  <Button
                    size='small'
                    color='warning'
                    variant='outlined'
                    disabled={busyId === r.id}
                    onClick={() => review(r.id, 'rejected')}
                  >
                    Reject
                  </Button>
                </Stack>
              ),
            },
          ]}
        />
      )}
    </PageShell>
  );
}
