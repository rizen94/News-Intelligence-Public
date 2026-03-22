import React, { useState, useEffect, useCallback } from 'react';
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
  Paper,
  LinearProgress,
  Slider,
  FormControlLabel,
  Switch,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Tooltip,
  Badge,
  Collapse,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  AutoAwesome as AIIcon,
  Refresh,
  TrendingUp,
  Article,
  Schedule,
  ExpandMore,
  ExpandLess,
  Add,
  Merge,
  Visibility,
  CheckCircle,
  Warning,
  LocalFireDepartment,
} from '@mui/icons-material';
import apiService from '../../services/apiService';

const StorylineDiscovery = () => {
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredStorylines, setDiscoveredStorylines] = useState([]);
  const [breakingNews, setBreakingNews] = useState([]);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Discovery parameters
  const [hours, setHours] = useState(48);
  const [minClusterSize, setMinClusterSize] = useState(3);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.6);
  const [autoSave, setAutoSave] = useState(false);

  // UI state
  const [expandedCluster, setExpandedCluster] = useState(null);
  const [selectedForMerge, setSelectedForMerge] = useState([]);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);

  const fetchBreakingNews = useCallback(async() => {
    try {
      const response = await apiService.getBreakingNews(24);
      if (response.success) {
        setBreakingNews(response.breaking_storylines || []);
      }
    } catch (err) {
      console.error('Error fetching breaking news:', err);
    }
  }, []);

  useEffect(() => {
    fetchBreakingNews();
  }, [fetchBreakingNews]);

  const handleDiscover = async() => {
    try {
      setDiscovering(true);
      setError(null);
      setSuccess(null);

      const response = await apiService.discoverStorylines({
        hours,
        min_cluster_size: minClusterSize,
        similarity_threshold: similarityThreshold,
        save: autoSave,
      });

      if (response.success) {
        setDiscoveredStorylines(response.storylines || []);
        setSuccess(`Discovered ${response.clusters_found || 0} potential storylines from ${response.articles_analyzed || 0} articles`);
        if (autoSave) {
          fetchBreakingNews();
        }
      } else {
        setError(response.error || 'Discovery failed');
      }
    } catch (err) {
      setError(err.message || 'Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSaveStoryline = async(storyline) => {
    try {
      const response = await apiService.createStoryline({
        title: storyline.suggested_title,
        description: storyline.suggested_description,
      });

      if (response.success) {
        setSuccess(`Storyline "${storyline.suggested_title}" saved successfully!`);
        fetchBreakingNews();
      }
    } catch (err) {
      setError('Failed to save storyline');
    }
  };

  const handleMergeSelected = async() => {
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
    } catch (err) {
      setError('Failed to merge storylines');
    }
  };

  const toggleExpanded = (id) => {
    setExpandedCluster(expandedCluster === id ? null : id);
  };

  const toggleSelect = (storyline) => {
    if (selectedForMerge.find(s => s.id === storyline.id)) {
      setSelectedForMerge(selectedForMerge.filter(s => s.id !== storyline.id));
    } else {
      setSelectedForMerge([...selectedForMerge, storyline]);
    }
  };

  const formatDate = (dateString) => {
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
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            <AIIcon color="primary" fontSize="large" />
            AI Storyline Discovery
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Use AI to automatically discover related article clusters and suggest new storylines
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={discovering ? <CircularProgress size={20} color="inherit" /> : <AIIcon />}
          onClick={handleDiscover}
          disabled={discovering}
          size="large"
        >
          {discovering ? 'Discovering...' : 'Run Discovery'}
        </Button>
      </Box>

      {/* Alerts */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Discovery Controls */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Discovery Settings
              </Typography>

              <Box sx={{ mb: 3 }}>
                <Typography gutterBottom>Time Window: {hours} hours</Typography>
                <Slider
                  value={hours}
                  onChange={(e, v) => setHours(v)}
                  min={12}
                  max={168}
                  step={12}
                  marks={[
                    { value: 24, label: '24h' },
                    { value: 72, label: '3d' },
                    { value: 168, label: '7d' },
                  ]}
                />
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography gutterBottom>Min Articles per Cluster: {minClusterSize}</Typography>
                <Slider
                  value={minClusterSize}
                  onChange={(e, v) => setMinClusterSize(v)}
                  min={2}
                  max={10}
                  step={1}
                  marks
                />
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography gutterBottom>Similarity Threshold: {(similarityThreshold * 100).toFixed(0)}%</Typography>
                <Slider
                  value={similarityThreshold}
                  onChange={(e, v) => setSimilarityThreshold(v)}
                  min={0.3}
                  max={0.9}
                  step={0.05}
                />
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={autoSave}
                    onChange={(e) => setAutoSave(e.target.checked)}
                  />
                }
                label="Auto-save discovered storylines"
              />
            </CardContent>
          </Card>

          {/* Breaking News */}
          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LocalFireDepartment color="error" />
                Breaking News
              </Typography>
              {breakingNews.length > 0 ? (
                <List dense>
                  {breakingNews.slice(0, 5).map((story, idx) => (
                    <ListItem key={idx}>
                      <ListItemIcon>
                        <Badge badgeContent={story.article_count} color="primary">
                          <TrendingUp color="error" />
                        </Badge>
                      </ListItemIcon>
                      <ListItemText
                        primary={story.suggested_title || 'Breaking Story'}
                        secondary={`${story.article_count} articles • Importance: ${(story.importance_score * 100).toFixed(0)}%`}
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No breaking news detected
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Discovered Storylines */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">
                  Discovered Storylines ({discoveredStorylines.length})
                </Typography>
                {selectedForMerge.length >= 2 && (
                  <Button
                    variant="outlined"
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
                  <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
                    Analyzing articles and clustering by similarity...
                  </Typography>
                </Box>
              )}

              {discoveredStorylines.length > 0 ? (
                <List>
                  {discoveredStorylines.map((storyline, idx) => (
                    <Paper key={idx} sx={{ mb: 2, p: 2 }}>
                      <Box display="flex" alignItems="flex-start" gap={2}>
                        <Box flex={1}>
                          <Box display="flex" alignItems="center" gap={1} mb={1}>
                            <Typography variant="h6">
                              {storyline.suggested_title || `Cluster ${idx + 1}`}
                            </Typography>
                            {storyline.is_breaking && (
                              <Chip
                                icon={<LocalFireDepartment />}
                                label="Breaking"
                                color="error"
                                size="small"
                              />
                            )}
                            <Chip
                              icon={<Article />}
                              label={`${storyline.article_count} articles`}
                              size="small"
                              variant="outlined"
                            />
                            {storyline.avg_similarity && (
                              <Chip
                                label={`${(storyline.avg_similarity * 100).toFixed(0)}% similar`}
                                size="small"
                                color="primary"
                                variant="outlined"
                              />
                            )}
                          </Box>

                          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            {storyline.suggested_description || 'No description available'}
                          </Typography>

                          {/* Common entities */}
                          {storyline.common_entities && storyline.common_entities.length > 0 && (
                            <Box display="flex" flexWrap="wrap" gap={0.5} mb={1}>
                              {storyline.common_entities.slice(0, 5).map((entity, i) => (
                                <Chip key={i} label={entity} size="small" />
                              ))}
                            </Box>
                          )}

                          {/* Expandable article list */}
                          <Collapse in={expandedCluster === idx}>
                            <Divider sx={{ my: 1 }} />
                            <Typography variant="subtitle2" gutterBottom>
                              Articles in this cluster:
                            </Typography>
                            <List dense>
                              {(storyline.articles || []).slice(0, 5).map((article, i) => (
                                <ListItem key={i}>
                                  <ListItemText
                                    primary={article.title}
                                    secondary={formatDate(article.created_at)}
                                  />
                                </ListItem>
                              ))}
                            </List>
                          </Collapse>
                        </Box>

                        <Box display="flex" flexDirection="column" gap={1}>
                          <Tooltip title="Save as storyline">
                            <IconButton
                              color="primary"
                              onClick={() => handleSaveStoryline(storyline)}
                            >
                              <Add />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="View details">
                            <IconButton onClick={() => toggleExpanded(idx)}>
                              {expandedCluster === idx ? <ExpandLess /> : <ExpandMore />}
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Select for merge">
                            <IconButton
                              color={selectedForMerge.find(s => s.id === storyline.id) ? 'primary' : 'default'}
                              onClick={() => toggleSelect(storyline)}
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
                  <AIIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No storylines discovered yet
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Click "Run Discovery" to analyze articles and find potential storylines
                  </Typography>
                </Paper>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Merge Dialog */}
      <Dialog open={mergeDialogOpen} onClose={() => setMergeDialogOpen(false)}>
        <DialogTitle>Merge Storylines</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Are you sure you want to merge these {selectedForMerge.length} storylines?
          </Typography>
          <List dense>
            {selectedForMerge.map((s, i) => (
              <ListItem key={i}>
                <ListItemIcon>{i === 0 ? <CheckCircle color="primary" /> : <Merge />}</ListItemIcon>
                <ListItemText
                  primary={s.suggested_title}
                  secondary={i === 0 ? 'Primary (will keep)' : 'Will merge into primary'}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMergeDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleMergeSelected}>
            Confirm Merge
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StorylineDiscovery;

