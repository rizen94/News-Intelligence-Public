import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Alert,
  CircularProgress,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  LinearProgress
} from '@mui/material';
import {
  AutoAwesome as AutoAwesomeIcon,
  Refresh as RefreshIcon,
  Analytics as AnalyticsIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  Tag as TagIcon,
  TrendingUp as TrendingUpIcon,
  NewReleases as NewReleasesIcon,
  Update as UpdateIcon
} from '@mui/icons-material';

const IntelligentTags = ({ threadId, onTagsUpdated }) => {
  const [tags, setTags] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [analysisDialogOpen, setAnalysisDialogOpen] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  useEffect(() => {
    if (threadId) {
      fetchTagAnalytics();
    }
  }, [threadId]);

  const fetchTagAnalytics = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/tags/thread/${threadId}/analytics`);
      const data = await response.json();
      
      if (data.success) {
        setTags(data.analytics.tags || []);
        setAnalytics(data.analytics.statistics || {});
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to fetch tag analytics');
    } finally {
      setLoading(false);
    }
  };

  const analyzeAndUpdateTags = async () => {
    try {
      setAnalyzing(true);
      setError(null);
      
      const response = await fetch(`/api/tags/update-thread/${threadId}`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setAnalysisResult(data);
        setAnalysisDialogOpen(true);
        // Refresh the tags
        fetchTagAnalytics();
        onTagsUpdated && onTagsUpdated();
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to analyze and update tags');
    } finally {
      setAnalyzing(false);
    }
  };

  const getTagColor = (weight) => {
    if (weight >= 0.8) return 'error';
    if (weight >= 0.6) return 'warning';
    if (weight >= 0.4) return 'info';
    return 'default';
  };

  const getTagVariant = (weight) => {
    if (weight >= 0.6) return 'filled';
    return 'outlined';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Box display="flex" alignItems="center" gap={2}>
              <AutoAwesomeIcon color="primary" />
              <Typography variant="h6">Intelligent Tags</Typography>
            </Box>
            <Box display="flex" gap={1}>
              <Button
                variant="outlined"
                startIcon={<AnalyticsIcon />}
                onClick={fetchTagAnalytics}
                disabled={loading}
              >
                Refresh
              </Button>
              <Button
                variant="contained"
                startIcon={analyzing ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
                onClick={analyzeAndUpdateTags}
                disabled={analyzing}
              >
                {analyzing ? 'Analyzing...' : 'Auto-Analyze'}
              </Button>
            </Box>
          </Box>
          
          {/* Statistics */}
          <Box display="flex" gap={2} mt={2}>
            <Chip 
              label={`${analytics.total_tags || 0} Tags`} 
              color="primary" 
              size="small" 
            />
            <Chip 
              label={`Avg Weight: ${(analytics.avg_weight || 0).toFixed(2)}`} 
              color="info" 
              size="small" 
            />
            <Chip 
              label={`Max Weight: ${(analytics.max_weight || 0).toFixed(2)}`} 
              color="success" 
              size="small" 
            />
          </Box>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Tags Display */}
      {tags.length === 0 ? (
        <Card>
          <CardContent>
            <Box textAlign="center" py={4}>
              <TagIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary">
                No Tags Found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Click "Auto-Analyze" to extract intelligent tags from your story thread content.
              </Typography>
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={2}>
          {/* Tags by Weight */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Tags by Relevance
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {tags
                    .sort((a, b) => b.weight - a.weight)
                    .slice(0, 20)
                    .map((tag, index) => (
                      <Tooltip 
                        key={tag.keyword} 
                        title={`Weight: ${tag.weight.toFixed(3)} | Articles: ${tag.article_count} | Created: ${formatDate(tag.created_at)}`}
                      >
                        <Chip
                          label={tag.keyword}
                          color={getTagColor(tag.weight)}
                          variant={getTagVariant(tag.weight)}
                          size="small"
                          icon={index < 5 ? <TrendingUpIcon /> : undefined}
                        />
                      </Tooltip>
                    ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Tag Analytics */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Tag Analytics
                </Typography>
                
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1">Top Tags by Weight</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <List dense>
                      {tags
                        .sort((a, b) => b.weight - a.weight)
                        .slice(0, 10)
                        .map((tag) => (
                          <ListItem key={tag.keyword}>
                            <ListItemText
                              primary={tag.keyword}
                              secondary={
                                <Box>
                                  <LinearProgress 
                                    variant="determinate" 
                                    value={tag.weight * 100} 
                                    sx={{ mb: 1 }}
                                  />
                                  <Typography variant="caption">
                                    Weight: {tag.weight.toFixed(3)} | Articles: {tag.article_count}
                                  </Typography>
                                </Box>
                              }
                            />
                          </ListItem>
                        ))}
                    </List>
                  </AccordionDetails>
                </Accordion>

                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1">Recent Tags</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <List dense>
                      {tags
                        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
                        .slice(0, 10)
                        .map((tag) => (
                          <ListItem key={tag.keyword}>
                            <ListItemText
                              primary={tag.keyword}
                              secondary={`Created: ${formatDate(tag.created_at)} | Weight: ${tag.weight.toFixed(3)}`}
                            />
                          </ListItem>
                        ))}
                    </List>
                  </AccordionDetails>
                </Accordion>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Analysis Results Dialog */}
      <Dialog 
        open={analysisDialogOpen} 
        onClose={() => setAnalysisDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <AutoAwesomeIcon color="primary" />
            Tag Analysis Results
          </Box>
        </DialogTitle>
        
        <DialogContent>
          {analysisResult && (
            <Box>
              <Alert severity="success" sx={{ mb: 2 }}>
                Analysis completed successfully! {analysisResult.update_result?.updates_made || 0} tags updated.
              </Alert>
              
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        <NewReleasesIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        New Tags ({analysisResult.analysis?.new_tags?.length || 0})
                      </Typography>
                      {analysisResult.analysis?.new_tags?.slice(0, 5).map((tag) => (
                        <Chip
                          key={tag.keyword}
                          label={tag.keyword}
                          color="success"
                          size="small"
                          sx={{ m: 0.5 }}
                        />
                      ))}
                    </CardContent>
                  </Card>
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        <UpdateIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Updated Tags ({analysisResult.analysis?.updated_tags?.length || 0})
                      </Typography>
                      {analysisResult.analysis?.updated_tags?.slice(0, 5).map((tag) => (
                        <Chip
                          key={tag.keyword}
                          label={tag.keyword}
                          color="warning"
                          size="small"
                          sx={{ m: 0.5 }}
                        />
                      ))}
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
              
              <Box mt={2}>
                <Typography variant="body2" color="text.secondary">
                  Articles analyzed: {analysisResult.analysis?.articles_analyzed || 0} | 
                  Analysis date: {new Date(analysisResult.analysis?.analysis_date).toLocaleString()}
                </Typography>
              </Box>
            </Box>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setAnalysisDialogOpen(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default IntelligentTags;
