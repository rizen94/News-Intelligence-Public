import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
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

const UnifiedLivingStoryNarrator = () => {
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
      const response = await newsSystemService.startPipeline();
      if (response.success) {
        setSuccess('Pipeline started successfully!');
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
      const response = await newsSystemService.stopPipeline();
      if (response.success) {
        setSuccess('Pipeline stopped successfully!');
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
        setSuccess('Story consolidation completed successfully!');
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
        setSuccess('Daily digest generated successfully!');
        loadDailyDigests();
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

  return (
    <div className="unified-container">
      {/* Header */}
      <div className="unified-section">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Living Story Narrator
          </Typography>
          <Tooltip title="Refresh All Data">
            <IconButton onClick={() => {
              loadNarratorStatus();
              loadDailyDigests();
              loadMasterArticles();
              loadPreprocessingStatus();
            }} color="primary">
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>

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
      </div>

      {/* Pipeline Control */}
      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <Settings sx={{ mr: 1 }} />
            <div className="unified-content-title">Pipeline Control</div>
          </div>
          <div className="unified-content-body">
            <div className="unified-content-text">
              {narratorStatus?.pipeline?.running ? (
                <div className="unified-status unified-status-success">
                  <CheckCircle sx={{ mr: 1, fontSize: 16 }} />
                  Pipeline Running
                </div>
              ) : (
                <div className="unified-status unified-status-neutral">
                  <Stop sx={{ mr: 1, fontSize: 16 }} />
                  Pipeline Stopped
                </div>
              )}
            </div>
            <div className="unified-content-actions">
              <Button
                variant="contained"
                color="success"
                startIcon={<PlayArrow />}
                onClick={handleStartPipeline}
                disabled={loading || narratorStatus?.pipeline?.running}
                className="unified-button"
              >
                Start Pipeline
              </Button>
              <Button
                variant="contained"
                color="error"
                startIcon={<Stop />}
                onClick={handleStopPipeline}
                disabled={loading || !narratorStatus?.pipeline?.running}
                className="unified-button"
              >
                Stop Pipeline
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="unified-section">
        <div className="unified-grid unified-grid-4">
          {/* Pipeline Statistics */}
          <div className="unified-stat-card unified-fade-in">
            <TrendingUp sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#1976d2' }}>
              {narratorStatus?.statistics?.articles_processed || 0}
            </div>
            <div className="unified-stat-label">Articles Processed</div>
          </div>

          <div className="unified-stat-card unified-fade-in">
            <AutoAwesome sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#9c27b0' }}>
              {narratorStatus?.statistics?.stories_consolidated || 0}
            </div>
            <div className="unified-stat-label">Stories Consolidated</div>
          </div>

          <div className="unified-stat-card unified-fade-in">
            <Article sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#2e7d32' }}>
              {narratorStatus?.statistics?.daily_digests_generated || 0}
            </div>
            <div className="unified-stat-label">Daily Digests</div>
          </div>

          <div className="unified-stat-card unified-fade-in">
            <Storage sx={{ fontSize: 40, mb: 1 }} />
            <div className="unified-stat-number" style={{ color: '#f57c00' }}>
              {narratorStatus?.statistics?.database_cleanups || 0}
            </div>
            <div className="unified-stat-label">Database Cleanups</div>
          </div>
        </div>
      </div>

      {/* Preprocessing Status */}
      {preprocessingStatus && (
        <div className="unified-section">
          <div className="unified-grid unified-grid-4">
            <div className="unified-stat-card unified-fade-in">
              <Article sx={{ fontSize: 40, mb: 1 }} />
              <div className="unified-stat-number" style={{ color: '#0288d1' }}>
                {preprocessingStatus.total_master_articles || 0}
              </div>
              <div className="unified-stat-label">Master Articles</div>
            </div>

            <div className="unified-stat-card unified-fade-in">
              <AutoAwesome sx={{ fontSize: 40, mb: 1 }} />
              <div className="unified-stat-number" style={{ color: '#1976d2' }}>
                {preprocessingStatus.consolidated_articles || 0}
              </div>
              <div className="unified-stat-label">Consolidated</div>
            </div>

            <div className="unified-stat-card unified-fade-in">
              <Article sx={{ fontSize: 40, mb: 1 }} />
              <div className="unified-stat-number" style={{ color: '#9c27b0' }}>
                {preprocessingStatus.single_source_articles || 0}
              </div>
              <div className="unified-stat-label">Single Source</div>
            </div>

            <div className="unified-stat-card unified-fade-in">
              <Timeline sx={{ fontSize: 40, mb: 1 }} />
              <div className="unified-stat-number" style={{ color: '#2e7d32' }}>
                {preprocessingStatus.processing_statistics?.tags_extracted || 0}
              </div>
              <div className="unified-stat-label">Tags Extracted</div>
            </div>
          </div>
        </div>
      )}

      {/* Manual Actions */}
      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <Settings sx={{ mr: 1 }} />
            <div className="unified-content-title">Manual Actions</div>
          </div>
          <div className="unified-content-body">
            <div className="unified-grid unified-grid-5">
              <Button
                variant="outlined"
                startIcon={<AutoAwesome />}
                onClick={handleTriggerConsolidation}
                disabled={loading}
                className="unified-button"
              >
                Consolidate Stories
              </Button>
              <Button
                variant="outlined"
                startIcon={<Article />}
                onClick={handleGenerateDigest}
                disabled={loading}
                className="unified-button"
              >
                Generate Digest
              </Button>
              <Button
                variant="outlined"
                startIcon={<Storage />}
                onClick={handleTriggerCleanup}
                disabled={loading}
                className="unified-button"
              >
                Database Cleanup
              </Button>
              <Button
                variant="outlined"
                startIcon={<Timeline />}
                onClick={handleRunPreprocessing}
                disabled={loading}
                className="unified-button"
              >
                Run Preprocessing
              </Button>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={() => {
                  loadNarratorStatus();
                  loadDailyDigests();
                  loadMasterArticles();
                  loadPreprocessingStatus();
                }}
                disabled={loading}
                className="unified-button"
              >
                Refresh All
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Scheduled Tasks */}
      {narratorStatus?.next_scheduled_tasks && (
        <div className="unified-section">
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <Schedule sx={{ mr: 1 }} />
              <div className="unified-content-title">Scheduled Tasks</div>
            </div>
            <div className="unified-content-body">
              <List dense>
                {Object.entries(narratorStatus.next_scheduled_tasks).map(([task, time]) => (
                  <ListItem key={task}>
                    <ListItemIcon>
                      <Schedule fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={task.replace(/_/g, ' ').toUpperCase()}
                      secondary={formatDateTime(time)}
                    />
                  </ListItem>
                ))}
              </List>
            </div>
          </div>
        </div>
      )}

      {/* Recent Daily Digests */}
      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <Article sx={{ mr: 1 }} />
            <div className="unified-content-title">Recent Daily Digests</div>
          </div>
          <div className="unified-content-body">
            {dailyDigests.length > 0 ? (
              <div className="unified-grid unified-grid-2">
                {dailyDigests.slice(0, 4).map((digest) => (
                  <div key={digest.id} className="unified-content-card unified-scale-in">
                    <div className="unified-content-header">
                      <div className="unified-content-title">{digest.title}</div>
                    </div>
                    <div className="unified-content-body">
                      <div className="unified-content-text">
                        {digest.content.substring(0, 200)}...
                      </div>
                      <div className="unified-content-actions">
                        <Button 
                          variant="text" 
                          size="small"
                          onClick={() => {
                            window.open(`/digest/${digest.id}`, '_blank');
                          }}
                          className="unified-button-sm"
                        >
                          Read Full Digest
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="unified-content-text">
                No daily digests available yet. Generate one using the manual actions above.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Master Articles */}
      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <Timeline sx={{ mr: 1 }} />
            <div className="unified-content-title">Recent Master Articles</div>
          </div>
          <div className="unified-content-body">
            {masterArticles.length > 0 ? (
              <div className="unified-grid unified-grid-2">
                {masterArticles.slice(0, 4).map((article) => (
                  <div key={article.id} className="unified-content-card unified-scale-in">
                    <div className="unified-content-header">
                      <div className="unified-content-title">{article.title}</div>
                    </div>
                    <div className="unified-content-body">
                      <div className="unified-content-text">
                        {article.summary || article.content?.substring(0, 200) + '...'}
                      </div>
                      <div className="unified-content-actions">
                        <Button 
                          variant="outlined" 
                          size="small"
                          onClick={() => {
                            window.open(`/article/${article.id}`, '_blank');
                          }}
                          className="unified-button-sm"
                        >
                          Read Full Article
                        </Button>
                        <Button 
                          variant="outlined" 
                          size="small"
                          onClick={() => {
                            alert(`Sources: ${article.sources.join(', ')}`);
                          }}
                          className="unified-button-sm"
                        >
                          View Sources ({article.source_count})
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="unified-content-text">
                No master articles available yet. Run preprocessing to create consolidated articles.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default UnifiedLivingStoryNarrator;
