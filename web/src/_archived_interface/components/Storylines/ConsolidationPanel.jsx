import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  CircularProgress,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
} from '@mui/material';
import {
  Merge as MergeIcon,
  Refresh,
  PlayArrow,
  CheckCircle,
  Schedule,
  AccountTree,
  Timeline,
  Info,
} from '@mui/icons-material';
import apiService from '../../services/apiService';

const ConsolidationPanel = () => {
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [lastRunResult, setLastRunResult] = useState(null);
  const [megaStorylines, setMegaStorylines] = useState([]);
  const [evolution, setEvolution] = useState(null);

  const fetchStatus = useCallback(async() => {
    try {
      setLoading(true);
      const response = await apiService.getConsolidationStatus();
      if (response.success) {
        setStatus(response.stats);
      }
    } catch (err) {
      setError('Failed to fetch consolidation status');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMegaStorylines = useCallback(async() => {
    try {
      const response = await apiService.getMegaStorylines(10);
      if (response.success) {
        setMegaStorylines(response.mega_storylines || []);
      }
    } catch (err) {
      console.error('Failed to fetch mega-storylines:', err);
    }
  }, []);

  const fetchEvolution = useCallback(async() => {
    try {
      const response = await apiService.getStorylineEvolution(168);
      if (response.success) {
        setEvolution(response);
      }
    } catch (err) {
      console.error('Failed to fetch evolution:', err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchMegaStorylines();
    fetchEvolution();
  }, [fetchStatus, fetchMegaStorylines, fetchEvolution]);

  const handleRunConsolidation = async(domain = null) => {
    try {
      setRunning(true);
      setError(null);
      const response = await apiService.runConsolidation(domain);
      if (response.success) {
        setLastRunResult(response.result || response);
        fetchStatus();
        fetchMegaStorylines();
        fetchEvolution();
      }
    } catch (err) {
      setError('Failed to run consolidation');
    } finally {
      setRunning(false);
    }
  };

  const formatDuration = (ms) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MergeIcon color="primary" />
            Storyline Consolidation
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Automatically merges similar storylines and creates mega-storylines
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={() => {
              fetchStatus();
              fetchMegaStorylines();
              fetchEvolution();
            }}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={running ? <CircularProgress size={20} color="inherit" /> : <PlayArrow />}
            onClick={() => handleRunConsolidation()}
            disabled={running}
          >
            {running ? 'Running...' : 'Run Now'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Service Status */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <Schedule sx={{ verticalAlign: 'middle', mr: 1 }} />
                Service Status
              </Typography>

              {status ? (
                <Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Total Runs</Typography>
                    <Chip label={status.total_runs || 0} size="small" />
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Total Merges</Typography>
                    <Chip label={status.total_merges || 0} size="small" color="primary" />
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Mega-Storylines Created</Typography>
                    <Chip label={status.total_parents_created || 0} size="small" color="secondary" />
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Last Run</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(status.last_run_at)}
                    </Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Last Duration</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatDuration(status.last_run_duration_ms)}
                    </Typography>
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Typography variant="subtitle2" gutterBottom>Configuration</Typography>
                  {status.config && (
                    <Box>
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption">Merge Threshold</Typography>
                        <Typography variant="caption">{(status.config.merge_threshold * 100).toFixed(0)}%</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption">Parent Threshold</Typography>
                        <Typography variant="caption">{(status.config.parent_threshold * 100).toFixed(0)}%</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption">Run Interval</Typography>
                        <Typography variant="caption">{status.config.interval_minutes} min</Typography>
                      </Box>
                    </Box>
                  )}
                </Box>
              ) : (
                <Typography color="text.secondary">No status available</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Last Run Result */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <CheckCircle sx={{ verticalAlign: 'middle', mr: 1 }} />
                Last Run Result
              </Typography>

              {lastRunResult ? (
                <Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Domain</Typography>
                    <Chip label={lastRunResult.domain || 'all'} size="small" />
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Storylines Analyzed</Typography>
                    <Typography variant="body2">{lastRunResult.storylines_analyzed || 0}</Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">With Embeddings</Typography>
                    <Typography variant="body2">{lastRunResult.storylines_with_embeddings || 0}</Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">With Entities</Typography>
                    <Typography variant="body2">{lastRunResult.storylines_with_entities || 0}</Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Merge Candidates</Typography>
                    <Chip label={lastRunResult.merge_candidates_found || 0} size="small" color="warning" />
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Merges Performed</Typography>
                    <Chip label={lastRunResult.merges_performed || 0} size="small" color="success" />
                  </Box>
                  <Box display="flex" justifyContent="space-between" mb={1}>
                    <Typography variant="body2">Duration</Typography>
                    <Typography variant="body2">{formatDuration(lastRunResult.duration_ms)}</Typography>
                  </Box>
                </Box>
              ) : (
                <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'grey.50' }}>
                  <Info sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
                  <Typography color="text.secondary">
                    Click "Run Now" to see consolidation results
                  </Typography>
                </Paper>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Mega-Storylines */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <AccountTree sx={{ verticalAlign: 'middle', mr: 1 }} />
                Mega-Storylines ({megaStorylines.length})
              </Typography>

              {megaStorylines.length > 0 ? (
                <List dense>
                  {megaStorylines.slice(0, 5).map((mega, idx) => (
                    <ListItem key={idx}>
                      <ListItemIcon>
                        <Chip label={mega.child_count || 0} size="small" color="primary" />
                      </ListItemIcon>
                      <ListItemText
                        primary={mega.title}
                        secondary={`${mega.article_count} articles • Score: ${((mega.consolidation_score || 0) * 100).toFixed(0)}%`}
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                  No mega-storylines created yet
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Evolution Chains */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <Timeline sx={{ verticalAlign: 'middle', mr: 1 }} />
                Evolution Chains
              </Typography>

              {evolution && evolution.evolution_chains?.length > 0 ? (
                <Box>
                  <Box display="flex" justifyContent="space-between" mb={2}>
                    <Typography variant="body2">Chains Found</Typography>
                    <Chip label={evolution.total_chains || 0} size="small" />
                  </Box>

                  {evolution.evolution_chains.slice(0, 3).map((chain, idx) => (
                    <Paper key={idx} sx={{ p: 1.5, mb: 1, bgcolor: 'grey.50' }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Chain {idx + 1} ({chain.storylines?.length || 0} storylines)
                      </Typography>
                      <Box display="flex" flexWrap="wrap" gap={0.5}>
                        {(chain.storylines || []).slice(0, 4).map((s, i) => (
                          <Chip
                            key={i}
                            label={s.title?.substring(0, 20) || `Story ${i + 1}`}
                            size="small"
                            variant={i === 0 ? 'filled' : 'outlined'}
                            color={i === 0 ? 'primary' : 'default'}
                          />
                        ))}
                      </Box>
                    </Paper>
                  ))}
                </Box>
              ) : (
                <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                  No evolution chains detected
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Run by Domain */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Run Consolidation by Domain
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                {['politics', 'finance', 'science-tech'].map((domain) => (
                  <Button
                    key={domain}
                    variant="outlined"
                    onClick={() => handleRunConsolidation(domain)}
                    disabled={running}
                    startIcon={<PlayArrow />}
                  >
                    {domain}
                  </Button>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ConsolidationPanel;

