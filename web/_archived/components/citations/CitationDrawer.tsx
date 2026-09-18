import React, { useEffect, useState } from 'react';
import { Typography, Box, Link } from '@mui/material';
import { DetailDrawer, LoadingState, ErrorState } from '../ui';
import { getApi } from '../../services/apiConnectionManager';

type CitationData = {
  citation_id?: string;
  source_title?: string;
  source_url?: string;
  excerpt?: string;
  context_id?: number;
  vintage_date?: string;
  [key: string]: unknown;
};

export function CitationDrawer({
  citationId,
  open,
  onClose,
}: {
  citationId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<CitationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !citationId) return;
    setLoading(true);
    setError(null);
    getApi()
      .get(`/api/intelligence/citation/${encodeURIComponent(citationId)}`)
      .then(res => {
        const payload = res.data?.data ?? res.data;
        setData(payload as CitationData);
      })
      .catch(e => setError(e?.message ?? 'Failed to load citation'))
      .finally(() => setLoading(false));
  }, [open, citationId]);

  return (
    <DetailDrawer
      open={open}
      onClose={onClose}
      title='Citation'
      subtitle={citationId ?? undefined}
    >
      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={() => citationId && setError(null)} />}
      {data && !loading && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {data.source_title && (
            <Typography variant='subtitle1' fontWeight={600}>
              {data.source_title}
            </Typography>
          )}
          {data.source_url && (
            <Link href={String(data.source_url)} target='_blank' rel='noopener'>
              {data.source_url}
            </Link>
          )}
          {data.vintage_date && (
            <Typography variant='caption' color='text.secondary'>
              Vintage: {String(data.vintage_date)}
            </Typography>
          )}
          {data.excerpt && (
            <Typography variant='body2' sx={{ whiteSpace: 'pre-wrap' }}>
              {String(data.excerpt)}
            </Typography>
          )}
          <Typography variant='caption' color='text.secondary' component='pre' sx={{ fontSize: '0.7rem' }}>
            {JSON.stringify(data, null, 2)}
          </Typography>
        </Box>
      )}
    </DetailDrawer>
  );
}
