import React, { useCallback, useEffect, useState } from 'react';
import {
  Add,
  Article,
  AutoAwesome as AIIcon,
  CheckCircle,
  ExpandLess,
  ExpandMore,
  LocalFireDepartment,
  Merge,
  TrendingUp,
} from '@mui/icons-material';
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Grid,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Slider,
  Switch,
  Tooltip,
  Typography,
} from '@mui/material';

import apiService from '../../services/apiService';
import { sanitizeSnippet } from '../../utils/sanitizeSnippet';

type DiscoveryStoryline = Record<string, any>;

const StorylineDiscovery: React.FC = () => {
  const [discovering, setDiscovering] = useState(false);
  const [discoveredStorylines, setDiscoveredStorylines] = useState<
    DiscoveryStoryline[]
  >([]);
  const [breakingNews, setBreakingNews] = useState<DiscoveryStoryline[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  /** When true, omit `hours` so the API uses full backlog (server-capped). */
  const [useFullBacklog, setUseFullBacklog] = useState(true);
  const [hours, setHours] = useState<number>(168);
  const [minClusterSize, setMinClusterSize] = useState<number>(3);
  const [similarityThreshold, setSimilarityThreshold] = useState<number>(0.6);
  const [autoSave, setAutoSave] = useState(false);
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);
  const [selectedForMerge, setSelectedForMerge] = useState<
    DiscoveryStoryline[]
  >([]);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);

  const fetchBreakingNews = useCallback(async () => {
    try {
      const response = await apiService.getBreakingNews(24);
      if (response?.success)
        setBreakingNews(response.breaking_storylines || []);
    } catch {
      // Non-blocking dashboard data.
    }
  }, []);

  useEffect(() => {
    fetchBreakingNews();
  }, [fetchBreakingNews]);

  const handleDiscover = async () => {
    try {
      setDiscovering(true);
      setError(null);
      setSuccess(null);
      const response = await apiService.discoverStorylines({
        ...(useFullBacklog ? {} : { hours }),
        minArticles: minClusterSize,
        minSimilarity: similarityThreshold,
        save: autoSave,
      });
      if (response?.success) {
        const suggested =
          response.suggested_storylines || response.storylines || [];
        setDiscoveredStorylines(suggested);
        const sum = response.summary || {};
        setSuccess(
          `Discovered ${
            sum.clusters_found ?? response.clusters_found ?? 0
          } potential storylines from ${
            sum.articles_analyzed ?? response.articles_analyzed ?? 0
          } articles`
        );
        if (autoSave) fetchBreakingNews();
      } else {
        setError(response?.error || 'Discovery failed');
      }
    } catch (err: any) {
      setError(err?.message || 'Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSaveStoryline = async (storyline: DiscoveryStoryline) => {
    try {
      const response = await apiService.createStoryline({
        title: storyline.suggested_title,
        description: storyline.suggested_description,
      });
      if (response?.success) {
        setSuccess(
          `Storyline "${storyline.suggested_title}" saved successfully`
        );
        fetchBreakingNews();
      }
    } catch {
      setError('Failed to save storyline');
    }
  };

  const handleMergeSelected = async () => {
    if (selectedForMerge.length < 2) return;
    try {
      const [primary, ...others] = selectedForMerge;
      for (const secondary of others) {
        await apiService.mergeStorylines(primary.id, secondary.id);
      }
      setSuccess(`Merged ${selectedForMerge.length} storylines`);
      setSelectedForMerge([]);
      setMergeDialogOpen(false);
      fetchBreakingNews();
    } catch {
      setError('Failed to merge storylines');
    }
  };

  const formatDate = (dateString?: string | null): string => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Box>
          <Typography
            variant='h4'
            component='h1'
            sx={{
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <AIIcon color='primary' fontSize='large' />
            AI Storyline Discovery
          </Typography>
          <Typography variant='body1' color='text.secondary'>
            Discover related article clusters and propose storyline candidates
          </Typography>
        </Box>
        <Button
          variant='contained'
          startIcon={
            discovering ? (
              <CircularProgress size={20} color='inherit' />
            ) : (
              <AIIcon />
            )
          }
          onClick={handleDiscover}
          disabled={discovering}
          size='large'
        >
          {discovering ? 'Discovering...' : 'Run Discovery'}
        </Button>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert
          severity='success'
          sx={{ mb: 2 }}
          onClose={() => setSuccess(null)}
        >
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant='h6' gutterBottom>
                Discovery Settings
              </Typography>
              <Box sx={{ mb: 3 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={useFullBacklog}
                      onChange={e => setUseFullBacklog(e.target.checked)}
                    />
                  }
                  label='Full historical backlog (server cap; default)'
                />
                {!useFullBacklog && (
                  <>
                    <Typography gutterBottom sx={{ mt: 1 }}>
                      Time window: {hours} hours (created_at)
                    </Typography>
                    <Slider
                      value={hours}
                      onChange={(_, v) => setHours(v as number)}
                      min={12}
                      max={720}
                      step={12}
                    />
                  </>
                )}
              </Box>
              <Box sx={{ mb: 3 }}>
                <Typography gutterBottom>
                  Min Articles per Cluster: {minClusterSize}
                </Typography>
                <Slider
                  value={minClusterSize}
                  onChange={(_, v) => setMinClusterSize(v as number)}
                  min={2}
                  max={10}
                  step={1}
                  marks
                />
              </Box>
              <Box sx={{ mb: 3 }}>
                <Typography gutterBottom>
                  Similarity Threshold: {(similarityThreshold * 100).toFixed(0)}
                  %
                </Typography>
                <Slider
                  value={similarityThreshold}
                  onChange={(_, v) => setSimilarityThreshold(v as number)}
                  min={0.3}
                  max={0.9}
                  step={0.05}
                />
              </Box>
              <FormControlLabel
                control={
                  <Switch
                    checked={autoSave}
                    onChange={e => setAutoSave(e.target.checked)}
                  />
                }
                label='Auto-save discovered storylines'
              />
            </CardContent>
          </Card>

          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography
                variant='h6'
                gutterBottom
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <LocalFireDepartment color='error' />
                Breaking News
              </Typography>
              {breakingNews.length > 0 ? (
                <List dense>
                  {breakingNews.slice(0, 5).map((story, idx) => (
                    <ListItem key={idx}>
                      <ListItemIcon>
                        <Badge
                          badgeContent={story.article_count}
                          color='primary'
                        >
                          <TrendingUp color='error' />
                        </Badge>
                      </ListItemIcon>
                      <ListItemText
                        primary={story.suggested_title || 'Breaking story'}
                        secondary={`${
                          story.article_count
                        } articles • Importance: ${(
                          (story.importance_score || 0) * 100
                        ).toFixed(0)}%`}
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  No breaking news detected
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box
                display='flex'
                justifyContent='space-between'
                alignItems='center'
                mb={2}
              >
                <Typography variant='h6'>
                  Discovered Storylines ({discoveredStorylines.length})
                </Typography>
                {selectedForMerge.length >= 2 && (
                  <Button
                    variant='outlined'
                    startIcon={<Merge />}
                    onClick={() => setMergeDialogOpen(true)}
                  >
                    Merge Selected ({selectedForMerge.length})
                  </Button>
                )}
              </Box>

              {discovering && (
                <Box sx={{ mb: 2 }}>
                  <LinearProgress />
                  <Typography
                    variant='body2'
                    color='text.secondary'
                    align='center'
                    sx={{ mt: 1 }}
                  >
                    Analyzing articles and clustering by similarity...
                  </Typography>
                </Box>
              )}

              {discoveredStorylines.length > 0 ? (
                <List>
                  {discoveredStorylines.map((storyline, idx) => (
                    <Paper key={idx} sx={{ mb: 2, p: 2 }}>
                      <Box display='flex' alignItems='flex-start' gap={2}>
                        <Box flex={1}>
                          <Box
                            display='flex'
                            alignItems='center'
                            gap={1}
                            mb={1}
                          >
                            <Typography variant='h6'>
                              {storyline.suggested_title ||
                                `Cluster ${idx + 1}`}
                            </Typography>
                            {storyline.is_breaking && (
                              <Chip
                                icon={<LocalFireDepartment />}
                                label='Breaking'
                                color='error'
                                size='small'
                              />
                            )}
                            <Chip
                              icon={<Article />}
                              label={`${storyline.article_count} articles`}
                              size='small'
                              variant='outlined'
                            />
                          </Box>
                          <Typography
                            variant='body2'
                            color='text.secondary'
                            sx={{ mb: 1 }}
                          >
                            {sanitizeSnippet(
                              storyline.suggested_description,
                              'No description available'
                            )}
                          </Typography>
                          <Collapse in={expandedCluster === idx}>
                            <Divider sx={{ my: 1 }} />
                            <Typography variant='subtitle2' gutterBottom>
                              Articles in this cluster
                            </Typography>
                            <List dense>
                              {(storyline.articles || [])
                                .slice(0, 5)
                                .map((article: any, i: number) => (
                                  <ListItem key={i}>
                                    <ListItemText
                                      primary={sanitizeSnippet(
                                        article.title,
                                        'Untitled article'
                                      )}
                                      secondary={formatDate(article.created_at)}
                                    />
                                  </ListItem>
                                ))}
                            </List>
                          </Collapse>
                        </Box>
                        <Box display='flex' flexDirection='column' gap={1}>
                          <Tooltip title='Save as storyline'>
                            <IconButton
                              color='primary'
                              onClick={() => handleSaveStoryline(storyline)}
                            >
                              <Add />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title='View details'>
                            <IconButton
                              onClick={() =>
                                setExpandedCluster(
                                  expandedCluster === idx ? null : idx
                                )
                              }
                            >
                              {expandedCluster === idx ? (
                                <ExpandLess />
                              ) : (
                                <ExpandMore />
                              )}
                            </IconButton>
                          </Tooltip>
                          <Tooltip title='Select for merge'>
                            <IconButton
                              color={
                                selectedForMerge.find(
                                  s => s.id === storyline.id
                                )
                                  ? 'primary'
                                  : 'default'
                              }
                              onClick={() =>
                                setSelectedForMerge(prev =>
                                  prev.find(s => s.id === storyline.id)
                                    ? prev.filter(s => s.id !== storyline.id)
                                    : [...prev, storyline]
                                )
                              }
                            >
                              <CheckCircle />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>
                    </Paper>
                  ))}
                </List>
              ) : (
                <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'grey.50' }}>
                  <AIIcon
                    sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }}
                  />
                  <Typography variant='h6' color='text.secondary' gutterBottom>
                    No storylines discovered yet
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Click "Run Discovery" to analyze articles and find potential
                    storylines.
                  </Typography>
                </Paper>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={mergeDialogOpen} onClose={() => setMergeDialogOpen(false)}>
        <DialogTitle>Merge Storylines</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Merge these {selectedForMerge.length} storylines?
          </Typography>
          <List dense>
            {selectedForMerge.map((s, i) => (
              <ListItem key={i}>
                <ListItemIcon>
                  {i === 0 ? <CheckCircle color='primary' /> : <Merge />}
                </ListItemIcon>
                <ListItemText
                  primary={s.suggested_title}
                  secondary={i === 0 ? 'Primary (kept)' : 'Merged into primary'}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMergeDialogOpen(false)}>Cancel</Button>
          <Button variant='contained' onClick={handleMergeSelected}>
            Confirm Merge
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StorylineDiscovery;
