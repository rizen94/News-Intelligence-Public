/**
 * Source Health — Data source status cards and refresh history
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Card,
  CardContent,
  Grid,
} from '@mui/material';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import type { SourceStatus } from '../../types/finance';

function SourceCard({ s }: { s: SourceStatus }) {
  const color =
    s.status === 'healthy'
      ? 'success'
      : s.status === 'down'
      ? 'error'
      : 'warning';
  return (
    <Card variant='outlined' sx={{ height: '100%' }}>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 1,
          }}
        >
          <Typography variant='subtitle1'>{s.name}</Typography>
          <Chip label={s.status} color={color} size='small' />
        </Box>
        <Typography variant='body2' color='text.secondary'>
          Last success: {s.last_success || 'Never'}
        </Typography>
        {s.last_failure && (
          <Typography variant='body2' color='error.main'>
            Last failure: {s.last_failure}
          </Typography>
        )}
        {s.last_error && (
          <Typography
            variant='caption'
            color='text.secondary'
            display='block'
            sx={{ mt: 0.5 }}
          >
            {s.last_error}
          </Typography>
        )}
        {s.next_scheduled_refresh && (
          <Typography
            variant='caption'
            color='text.secondary'
            display='block'
            sx={{ mt: 0.5 }}
          >
            Next: {s.next_scheduled_refresh}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

export default function SourceHealth() {
  const { domain } = useDomainRoute();
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!domain) return;
    setLoading(true);
    apiService
      .getFinanceSourceStatus(domain)
      .then(res => {
        setSources(res?.data?.sources || []);
      })
      .catch(() => setSources([]))
      .finally(() => setLoading(false));
  }, [domain]);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h5' gutterBottom>
        Source Health
      </Typography>
      <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
        Status of data sources used by the Finance orchestrator.
      </Typography>

      <Grid container spacing={2}>
        {sources.map(s => (
          <Grid item xs={12} sm={6} md={4} key={s.source_id}>
            <SourceCard s={s} />
          </Grid>
        ))}
      </Grid>
      {sources.length === 0 && !loading && (
        <Paper sx={{ p: 3, textAlign: 'center' }}>
          <Typography color='text.secondary'>
            No source status available.
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
