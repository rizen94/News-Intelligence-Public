/**
 * Context-centric status and quality — Phase 4 (validation).
 * Shows pipeline counts and per-domain coverage for dual-mode validation.
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Alert,
  Button,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';
import Assessment as AssessmentIcon from '@mui/icons-material/Assessment';
import Refresh as RefreshIcon from '@mui/icons-material/Refresh';
import {
  contextCentricApi,
  type ContextCentricStatus,
  type ContextCentricQuality,
} from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const ContextCentricStatusPage: React.FC = () => {
  const [status, setStatus] = useState<ContextCentricStatus | null>(null);
  const [quality, setQuality] = useState<ContextCentricQuality | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, q] = await Promise.all([
        contextCentricApi.getStatus(),
        contextCentricApi.getQuality(),
      ]);
      setStatus(s);
      setQuality(q);
    } catch (e) {
      Logger.apiError('Context-centric status/quality load failed', e as Error);
      setError((e as Error).message ?? 'Failed to load');
      setStatus(null);
      setQuality(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }} component="h1">
        <AssessmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Context-Centric Pipeline Status
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Counts and coverage for the context-centric model. Use this to validate sync and entity coverage (Phase 3.2).
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Button startIcon={<RefreshIcon />} onClick={load} disabled={loading} sx={{ mb: 2 }}>
        Refresh
      </Button>

      {status && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={4} md={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="caption" color="text.secondary">Contexts</Typography>
                <Typography variant="h5">{status.contexts}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="caption" color="text.secondary">Article→Context</Typography>
                <Typography variant="h5">{status.article_to_context_links}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="caption" color="text.secondary">Entity profiles</Typography>
                <Typography variant="h5">{status.entity_profiles}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="caption" color="text.secondary">Claims</Typography>
                <Typography variant="h5">{status.extracted_claims}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="caption" color="text.secondary">Tracked events</Typography>
                <Typography variant="h5">{status.tracked_events}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="caption" color="text.secondary">Patterns</Typography>
                <Typography variant="h5">{status.pattern_discoveries}</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {quality && (
        <Paper sx={{ overflow: 'auto' }}>
          <Typography variant="h6" sx={{ p: 2 }}>Per-domain coverage</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Domain</TableCell>
                <TableCell align="right">Articles</TableCell>
                <TableCell align="right">Context links</TableCell>
                <TableCell align="right">Context %</TableCell>
                <TableCell align="right">Entity canonical</TableCell>
                <TableCell align="right">Entity profiles</TableCell>
                <TableCell align="right">Entity %</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(quality.by_domain).map(([domain, row]) => (
                <TableRow key={domain}>
                  <TableCell>{domain}</TableCell>
                  <TableCell align="right">{row.articles ?? '—'}</TableCell>
                  <TableCell align="right">{row.article_to_context_links ?? '—'}</TableCell>
                  <TableCell align="right">
                    {row.context_coverage_pct != null ? `${row.context_coverage_pct}%` : '—'}
                  </TableCell>
                  <TableCell align="right">{row.entity_canonical ?? '—'}</TableCell>
                  <TableCell align="right">{row.entity_profiles ?? '—'}</TableCell>
                  <TableCell align="right">
                    {row.entity_coverage_pct != null ? `${row.entity_coverage_pct}%` : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 2 }}>
            {quality.summary}
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default ContextCentricStatusPage;
