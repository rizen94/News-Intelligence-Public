/**
 * NRI entity resolution — resolved mentions, parked queue, health.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Skeleton,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import {
  contextCentricApi,
  type NriParkedResolution,
  type NriResolvedMention,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

export default function EntityResolutionPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [resolved, setResolved] = useState<NriResolvedMention[]>([]);
  const [parked, setParked] = useState<NriParkedResolution[]>([]);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, p, h] = await Promise.all([
        contextCentricApi.getNriResolvedMentions({ domain_key: domain, limit: 100 }),
        contextCentricApi.getNriParked({ domain_key: domain, review_status: 'open', limit: 100 }),
        contextCentricApi.getNriHealth(),
      ]);
      setResolved(r?.items ?? []);
      setParked(p?.items ?? []);
      setHealth(h ?? null);
    } finally {
      setLoading(false);
    }
  }, [domain]);

  useEffect(() => {
    load();
  }, [load]);

  const handleReview = async (id: number) => {
    await contextCentricApi.reviewNriParked(id, { review_status: 'reviewed' });
    await load();
  };

  const statusCounts = resolved.reduce<Record<string, number>>((acc, row) => {
    acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, {});

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
        <CardHeader title='Entity resolution (NRI)' subheader={domain} />
        <CardContent>
          {health && (
            <Alert severity={health.status === 'ok' ? 'success' : 'warning'} sx={{ mb: 2 }}>
              NRI API: {String(health.status ?? 'unknown')}
              {health.reachable === false ? ' — unreachable' : ''}
            </Alert>
          )}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
            {Object.entries(statusCounts).map(([status, count]) => (
              <Chip key={status} label={`${status}: ${count}`} size='small' />
            ))}
            <Chip label={`parked open: ${parked.length}`} color='warning' size='small' />
          </Box>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
            <Tab label='Resolved' />
            <Tab label='Parked queue' />
          </Tabs>
          <Divider sx={{ mb: 2 }} />
          {loading ? (
            <Skeleton height={240} />
          ) : tab === 0 ? (
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>Mention</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>FtM ID</TableCell>
                  <TableCell>Score</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {resolved.map(row => (
                  <TableRow key={row.id}>
                    <TableCell>{row.canonical_name ?? row.mention_text}</TableCell>
                    <TableCell>{row.status}</TableCell>
                    <TableCell>{row.ftm_id ?? '—'}</TableCell>
                    <TableCell>{row.match_score?.toFixed(3) ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>Mention</TableCell>
                  <TableCell>Candidate</TableCell>
                  <TableCell>Score</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {parked.map(row => (
                  <TableRow key={row.id}>
                    <TableCell>{row.canonical_name ?? row.mention_text}</TableCell>
                    <TableCell>{row.candidate_ftm_id ?? '—'}</TableCell>
                    <TableCell>{row.match_score?.toFixed(3) ?? '—'}</TableCell>
                    <TableCell>
                      <Button size='small' onClick={() => handleReview(row.id)}>
                        Mark reviewed
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
