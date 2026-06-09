/**
 * NRI vault hypotheses — read-only list from NRI loop.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Drawer,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import {
  contextCentricApi,
  type NriHypothesis,
  type NriHypothesisDetail,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

export default function HypothesesPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [items, setItems] = useState<NriHypothesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<NriHypothesisDetail | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await contextCentricApi.getNriHypotheses({ limit: 100 });
      setItems(res?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = async (hypId: string) => {
    const detail = await contextCentricApi.getNriHypothesis(hypId);
    setSelected(detail);
  };

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate(`/${domain}/investigate`)}
        sx={{ mb: 2 }}
      >
        Back to Investigate
      </Button>
      <Card>
        <CardHeader title='Investigative hypotheses (NRI vault)' subheader={domain} />
        <CardContent>
          {loading ? (
            <Skeleton height={200} />
          ) : items.length === 0 ? (
            <Typography color='text.secondary'>
              No hypotheses in vault yet. Loop runs in shadow mode write here when patterns are detected.
            </Typography>
          ) : (
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Claim</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Confidence</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map(row => (
                  <TableRow
                    key={row.hyp_id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => openDetail(row.hyp_id)}
                  >
                    <TableCell>{row.hyp_id}</TableCell>
                    <TableCell>{row.claim ?? '—'}</TableCell>
                    <TableCell>
                      <Chip label={row.status ?? 'open'} size='small' />
                    </TableCell>
                    <TableCell>{row.confidence ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <Drawer anchor='right' open={!!selected} onClose={() => setSelected(null)}>
        <Box sx={{ width: 420, p: 2 }}>
          <Typography variant='h6' gutterBottom>
            {selected?.hyp_id}
          </Typography>
          <Typography variant='body2' color='text.secondary' paragraph>
            {selected?.claim}
          </Typography>
          <Typography variant='caption' display='block'>
            test_status: {selected?.test_status ?? 'pending'}
          </Typography>
          <Typography variant='body2' sx={{ mt: 2, whiteSpace: 'pre-wrap' }}>
            {selected?.body}
          </Typography>
        </Box>
      </Drawer>
    </Box>
  );
}
