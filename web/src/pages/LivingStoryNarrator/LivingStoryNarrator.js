import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  Chip,
  LinearProgress,
  Alert,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  IconButton,
  Tooltip,
  Badge
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Refresh,
  Schedule,
  Article,
  Timeline,
  AutoAwesome,
  Storage,
  TrendingUp,
  History,
  Notifications,
  CheckCircle,
  Error,
  Warning,
  Info,
  Settings
} from '@mui/icons-material';
import { newsSystemService } from '../../services/newsSystemService';
import './LivingStoryNarrator.css';

const LivingStoryNarrator = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [narratorStatus, setNarratorStatus] = useState(null);
  const [dailyDigests, setDailyDigests] = useState([]);
  const [masterArticles, setMasterArticles] = useState([]);
  const [preprocessingStatus, setPreprocessingStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    loadNarratorStatus();
    loadDailyDigests();
    loadMasterArticles();
    loadPreprocessingStatus();
  }, []);

  const loadNarratorStatus = async () => {
    try {
      const response = await newsSystemService.getLivingNarratorStatus();
      if (response.success) {
        setNarratorStatus(response.data);
      }
    } catch (error) {
      console.error('Error loading narrator status:', error);
    }
  };

  const loadDailyDigests = async () => {
    try {
      const response = await newsSystemService.getDailyDigests();
      if (response.success) {
        setDailyDigests(response.data);
      }
    } catch (error) {
      console.error('Error loading daily digests:', error);
    }
  };

  const loadMasterArticles = async () => {
    try {
      const response = await newsSystemService.getMasterArticles();
      if (response.success) {
        setMasterArticles(response.data);
      }
    } catch (error) {
      console.error('Error loading master articles:', error);
    }
  };

  const loadPreprocessingStatus = async () => {
    try {
      const response = await newsSystemService.getPreprocessingStatus();
      if (response.success) {
        setPreprocessingStatus(response.data);
      }
    } catch (error) {
      console.error('Error loading preprocessing status:', error);
    }
  };

  const handleStartPipeline = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await newsSystemService.startAutomatedPipeline();
      if (response.success) {
        setSuccess('Living Story Narrator started successfully!');
        loadNarratorStatus();
      } else {
        setError(response.error || 'Failed to start pipeline');
      }
    } catch (error) {
      setError('Error starting pipeline: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStopPipeline = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await newsSystemService.stopAutomatedPipeline();
      if (response.success) {
        setSuccess('Living Story Narrator stopped successfully!');
        loadNarratorStatus();
      } else {
        setError(response.error || 'Failed to stop pipeline');
      }
    } catch (error) {
      setError('Error stopping pipeline: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerConsolidation = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await newsSystemService.triggerStoryConsolidation();
      if (response.success) {
        setSuccess(`Story consolidation completed: ${response.data.stories_consolidated} stories consolidated`);
        loadNarratorStatus();
        loadMasterArticles();
      } else {
        setError(response.error || 'Failed to trigger consolidation');
      }
    } catch (error) {
      setError('Error triggering consolidation: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateDigest = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await newsSystemService.generateDailyDigest();
      if (response.success) {
        setSuccess(`Daily digest generated: ${response.data.stories_included} stories included`);
        loadDailyDigests();
        loadNarratorStatus();
      } else {
        setError(response.error || 'Failed to generate digest');
      }
    } catch (error) {
      setError('Error generating digest: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerCleanup = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await newsSystemService.triggerDatabaseCleanup();
      if (response.success) {
        setSuccess('Database cleanup completed successfully!');
        loadNarratorStatus();
      } else {
        setError(response.error || 'Failed to trigger cleanup');
      }
    } catch (error) {
      setError('Error triggering cleanup: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunPreprocessing = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await newsSystemService.runPreprocessing({ batch_size: 20 });
      if (response.success) {
        setSuccess(`Preprocessing completed: ${response.data.articles_processed} articles processed`);
        loadPreprocessingStatus();
        loadMasterArticles();
      } else {
        setError(response.error || 'Failed to run preprocessing');
      }
    } catch (error) {
      setError('Error running preprocessing: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running': return <CheckCircle color="success" />;
      case 'error': return <Error color="error" />;
      case 'warning': return <Warning color="warning" />;
      default: return <Info color="info" />;
    }
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const formatNextRun = (nextRun) => {
    if (!nextRun) return 'Not scheduled';
    const date = new Date(nextRun);
    const now = new Date();
    const diff = date - now;
    
    if (diff < 0) return 'Overdue';
    if (diff < 60000) return 'In less than a minute';
    if (diff < 3600000) return `In ${Math.floor(diff / 60000)} minutes`;
    if (diff < 86400000) return `In ${Math.floor(diff / 3600000)} hours`;
    return date.toLocaleString();
  };

  const renderDashboard = () => (
    <Grid container spacing={3}>
      {/* Pipeline Status */}
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">Living Story Narrator Status</Typography>
              <Box>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<PlayArrow />}
                  onClick={handleStartPipeline}
                  disabled={loading || narratorStatus?.running}
                  sx={{ mr: 1 }}
                >
                  Start Pipeline
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<Stop />}
                  onClick={handleStopPipeline}
                  disabled={loading || !narratorStatus?.running}
                >
                  Stop Pipeline
                </Button>
              </Box>
            </Box>
            
            {narratorStatus && (
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2, bgcolor: narratorStatus.running ? 'success.light' : 'grey.100' }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Pipeline Status
                    </Typography>
                    <Box display="flex" alignItems="center">
                      {getStatusIcon(narratorStatus.running ? 'running' : 'stopped')}
                      <Typography variant="h6" sx={{ ml: 1 }}>
                        {narratorStatus.running ? 'Running' : 'Stopped'}
                      </Typography>
                    </Box>
                  </Paper>
                </Grid>
                
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Total Pipeline Runs
                    </Typography>
                    <Typography variant="h6">
                      {narratorStatus.statistics?.total_pipeline_runs || 0}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>
            )}
          </CardContent>
        </Card>
      </Grid>

      {/* Statistics */}
      {narratorStatus && (
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Pipeline Statistics</Typography>
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">
                      {narratorStatus.statistics?.articles_processed || 0}
                    </Typography>
                    <Typography variant="body2">Articles Processed</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="secondary">
                      {narratorStatus.statistics?.stories_consolidated || 0}
                    </Typography>
                    <Typography variant="body2">Stories Consolidated</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      {narratorStatus.statistics?.daily_digests_generated || 0}
                    </Typography>
                    <Typography variant="body2">Daily Digests</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="warning.main">
                      {narratorStatus.statistics?.database_cleanups || 0}
                    </Typography>
                    <Typography variant="body2">Database Cleanups</Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Preprocessing Status */}
      {preprocessingStatus && (
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Enhanced Preprocessing Status</Typography>
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="info.main">
                      {preprocessingStatus.total_master_articles || 0}
                    </Typography>
                    <Typography variant="body2">Master Articles</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">
                      {preprocessingStatus.consolidated_articles || 0}
                    </Typography>
                    <Typography variant="body2">Consolidated</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="secondary">
                      {preprocessingStatus.single_source_articles || 0}
                    </Typography>
                    <Typography variant="body2">Single Source</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      {preprocessingStatus.processing_statistics?.tags_extracted || 0}
                    </Typography>
                    <Typography variant="body2">Tags Extracted</Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Scheduled Tasks */}
      {narratorStatus?.next_scheduled_tasks && (
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Scheduled Tasks</Typography>
              <List>
                {narratorStatus.next_scheduled_tasks.map((task, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <Schedule />
                    </ListItemIcon>
                    <ListItemText
                      primary={task.job.split(' ')[0] || 'Unknown Task'}
                      secondary={`Next run: ${formatNextRun(task.next_run)}`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Manual Actions */}
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Manual Actions</Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={2.4}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<AutoAwesome />}
                  onClick={handleTriggerConsolidation}
                  disabled={loading}
                >
                  Consolidate Stories
                </Button>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<Article />}
                  onClick={handleGenerateDigest}
                  disabled={loading}
                >
                  Generate Digest
                </Button>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<Storage />}
                  onClick={handleTriggerCleanup}
                  disabled={loading}
                >
                  Database Cleanup
                </Button>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<Timeline />}
                  onClick={handleRunPreprocessing}
                  disabled={loading}
                >
                  Run Preprocessing
                </Button>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<Refresh />}
                  onClick={() => {
                    loadNarratorStatus();
                    loadDailyDigests();
                    loadMasterArticles();
                    loadPreprocessingStatus();
                  }}
                  disabled={loading}
                >
                  Refresh All
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const renderDailyDigests = () => (
    <Grid container spacing={3}>
      {dailyDigests.map((digest) => (
        <Grid item xs={12} key={digest.id}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
                <Typography variant="h6">{digest.title}</Typography>
                <Chip 
                  label={`${digest.stories_included} stories`} 
                  color="primary" 
                  size="small" 
                />
              </Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {formatDateTime(digest.created_at)}
              </Typography>
              <Typography variant="body1" sx={{ mt: 2 }}>
                {digest.content.substring(0, 500)}...
              </Typography>
              <Button 
                variant="text" 
                sx={{ mt: 1 }}
                onClick={() => {
                  // Open full digest in new tab
                  window.open(`/digest/${digest.id}`, '_blank');
                }}
              >
                Read Full Digest
              </Button>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );

  const renderMasterArticles = () => (
    <Grid container spacing={3}>
      {masterArticles.map((article) => (
        <Grid item xs={12} key={article.id}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
                <Typography variant="h6">{article.title}</Typography>
                <Box>
                  <Chip 
                    label={`${article.source_count} sources`} 
                    color="secondary" 
                    size="small" 
                    sx={{ mr: 1 }}
                  />
                  <Chip 
                    label={`Priority: ${article.source_priority}`} 
                    color="primary" 
                    size="small" 
                  />
                </Box>
              </Box>
              
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {article.source} • {formatDateTime(article.published_at)}
              </Typography>
              
              {article.tags && article.tags.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  {article.tags.slice(0, 5).map((tag, index) => (
                    <Chip
                      key={index}
                      label={tag.text}
                      size="small"
                      sx={{ mr: 1, mb: 1 }}
                    />
                  ))}
                </Box>
              )}
              
              <Typography variant="body1" sx={{ mb: 2 }}>
                {article.summary || article.content?.substring(0, 300) + '...'}
              </Typography>
              
              <Box display="flex" gap={1}>
                <Button 
                  variant="outlined" 
                  size="small"
                  onClick={() => {
                    // Open full article view
                    window.open(`/article/${article.id}`, '_blank');
                  }}
                >
                  Read Full Article
                </Button>
                <Button 
                  variant="outlined" 
                  size="small"
                  onClick={() => {
                    // Show sources in alert for now
                    alert(`Sources: ${article.sources.join(', ')}`);
                  }}
                >
                  View Sources ({article.source_count})
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Living Story Narrator
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Automated pipeline for continuous story consolidation, evolution, and intelligence generation.
      </Typography>

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

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Dashboard" icon={<TrendingUp />} />
          <Tab label="Daily Digests" icon={<Article />} />
          <Tab label="Master Articles" icon={<Timeline />} />
        </Tabs>
      </Box>

      {activeTab === 0 && renderDashboard()}
      {activeTab === 1 && renderDailyDigests()}
      {activeTab === 2 && renderMasterArticles()}
    </Box>
  );
};

export default LivingStoryNarrator;
