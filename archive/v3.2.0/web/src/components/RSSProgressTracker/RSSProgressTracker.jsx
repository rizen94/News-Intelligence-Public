import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
  IconButton,
  Tooltip,
  Collapse,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Alert,
  Button,
  Grid,
  Paper
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  Timer as TimerIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

const RSSProgressTracker = ({ onCollectionStart, onCollectionComplete }) => {
  const [activeCollections, setActiveCollections] = useState({});
  const [expandedCollections, setExpandedCollections] = useState(new Set());
  const [isCollecting, setIsCollecting] = useState(false);
  const [currentCollectionId, setCurrentCollectionId] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  // Start progress polling
  const startPolling = () => {
    if (intervalRef.current) return;
    
    intervalRef.current = setInterval(async () => {
      try {
        const response = await newsSystemService.getAllRSSCollectionProgress();
        if (response.success) {
          setActiveCollections(response.active_collections);
          
          // Check if any collections completed
          const completedCollections = Object.values(response.active_collections)
            .filter(progress => progress.status === 'completed' || progress.status === 'failed');
          
          if (completedCollections.length > 0 && onCollectionComplete) {
            onCollectionComplete(completedCollections);
          }
        }
      } catch (err) {
        console.error('Error polling RSS progress:', err);
      }
    }, 2000); // Poll every 2 seconds
  };

  // Stop progress polling
  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  // Start RSS collection
  const handleStartCollection = async () => {
    try {
      setError(null);
      setIsCollecting(true);
      
      const response = await newsSystemService.collectRSSFeeds();
      
      if (response.data && response.data.collection_id) {
        setCurrentCollectionId(response.data.collection_id);
        startPolling();
        
        if (onCollectionStart) {
          onCollectionStart(response.data);
        }
      }
    } catch (err) {
      setError(`Failed to start RSS collection: ${err.message}`);
      setIsCollecting(false);
    }
  };

  // Cancel RSS collection
  const handleCancelCollection = async (collectionId) => {
    try {
      await newsSystemService.cancelRSSCollection(collectionId);
      stopPolling();
      setIsCollecting(false);
      setCurrentCollectionId(null);
    } catch (err) {
      setError(`Failed to cancel collection: ${err.message}`);
    }
  };

  // Toggle collection details
  const toggleCollectionDetails = (collectionId) => {
    const newExpanded = new Set(expandedCollections);
    if (newExpanded.has(collectionId)) {
      newExpanded.delete(collectionId);
    } else {
      newExpanded.add(collectionId);
    }
    setExpandedCollections(newExpanded);
  };

  // Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'primary';
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'cancelled': return 'warning';
      default: return 'default';
    }
  };

  // Get status icon
  const getStatusIcon = (status) => {
    switch (status) {
      case 'running': return <ScheduleIcon />;
      case 'completed': return <CheckCircleIcon />;
      case 'failed': return <ErrorIcon />;
      case 'cancelled': return <StopIcon />;
      default: return <ScheduleIcon />;
    }
  };

  // Format duration
  const formatDuration = (seconds) => {
    if (!seconds) return '0s';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  // Calculate progress percentage
  const getProgressPercentage = (progress) => {
    if (progress.total_feeds === 0) return 0;
    return Math.round((progress.processed_feeds / progress.total_feeds) * 100);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);

  // Auto-start polling if there are active collections
  useEffect(() => {
    if (Object.keys(activeCollections).length > 0) {
      startPolling();
    } else {
      stopPolling();
      setIsCollecting(false);
      setCurrentCollectionId(null);
    }
  }, [activeCollections]);

  const hasActiveCollections = Object.keys(activeCollections).length > 0;

  return (
    <Box>
      {/* Collection Controls */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6" component="h2">
              RSS Collection Progress
            </Typography>
            <Box display="flex" gap={1}>
              {!isCollecting ? (
                <Button
                  variant="contained"
                  startIcon={<PlayIcon />}
                  onClick={handleStartCollection}
                  disabled={hasActiveCollections}
                >
                  Start Collection
                </Button>
              ) : (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={() => handleCancelCollection(currentCollectionId)}
                >
                  Cancel Collection
                </Button>
              )}
            </Box>
          </Box>
          
          {error && (
            <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Active Collections */}
      {hasActiveCollections && (
        <Box>
          {Object.entries(activeCollections).map(([collectionId, progress]) => (
            <Card key={collectionId} sx={{ mb: 2 }}>
              <CardContent>
                {/* Collection Header */}
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Box display="flex" alignItems="center" gap={2}>
                    {getStatusIcon(progress.status)}
                    <Box>
                      <Typography variant="h6">
                        RSS Collection {collectionId.substring(0, 8)}...
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Started: {new Date(progress.start_time).toLocaleTimeString()}
                      </Typography>
                    </Box>
                  </Box>
                  
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip
                      label={progress.status.toUpperCase()}
                      color={getStatusColor(progress.status)}
                      size="small"
                    />
                    <IconButton
                      onClick={() => toggleCollectionDetails(collectionId)}
                      size="small"
                    >
                      {expandedCollections.has(collectionId) ? 
                        <ExpandLessIcon /> : <ExpandMoreIcon />
                      }
                    </IconButton>
                  </Box>
                </Box>

                {/* Progress Bar */}
                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">
                      Feeds: {progress.processed_feeds}/{progress.total_feeds}
                    </Typography>
                    <Typography variant="body2">
                      {getProgressPercentage(progress)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={getProgressPercentage(progress)}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                </Box>

                {/* Quick Stats */}
                <Grid container spacing={2} mb={2}>
                  <Grid item xs={6} sm={3}>
                    <Paper sx={{ p: 1, textAlign: 'center' }}>
                      <Typography variant="h6" color="primary">
                        {progress.successful_feeds}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Successful
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Paper sx={{ p: 1, textAlign: 'center' }}>
                      <Typography variant="h6" color="error">
                        {progress.failed_feeds}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Failed
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Paper sx={{ p: 1, textAlign: 'center' }}>
                      <Typography variant="h6" color="success">
                        {progress.new_articles}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        New Articles
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Paper sx={{ p: 1, textAlign: 'center' }}>
                      <Typography variant="h6" color="warning">
                        {progress.duplicate_articles}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Duplicates
                      </Typography>
                    </Paper>
                  </Grid>
                </Grid>

                {/* Current Feed */}
                {progress.current_feed && progress.status === 'running' && (
                  <Box mb={2}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Currently processing: {progress.current_feed}
                    </Typography>
                    <LinearProgress
                      variant="indeterminate"
                      sx={{ height: 4, borderRadius: 2 }}
                    />
                  </Box>
                )}

                {/* Duration */}
                {progress.duration_seconds && (
                  <Box display="flex" alignItems="center" gap={1} mb={2}>
                    <TimerIcon fontSize="small" color="action" />
                    <Typography variant="body2" color="text.secondary">
                      Duration: {formatDuration(progress.duration_seconds)}
                    </Typography>
                  </Box>
                )}

                {/* Detailed Information */}
                <Collapse in={expandedCollections.has(collectionId)}>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Collection Details
                    </Typography>
                    
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <List dense>
                          <ListItem>
                            <ListItemIcon>
                              <SourceIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText
                              primary="Total Feeds"
                              secondary={progress.total_feeds}
                            />
                          </ListItem>
                          <ListItem>
                            <ListItemIcon>
                              <ArticleIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText
                              primary="Total Articles"
                              secondary={progress.total_articles}
                            />
                          </ListItem>
                        </List>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <List dense>
                          <ListItem>
                            <ListItemIcon>
                              <CheckCircleIcon fontSize="small" color="success" />
                            </ListItemIcon>
                            <ListItemText
                              primary="Successful Feeds"
                              secondary={progress.successful_feeds}
                            />
                          </ListItem>
                          <ListItem>
                            <ListItemIcon>
                              <ErrorIcon fontSize="small" color="error" />
                            </ListItemIcon>
                            <ListItemText
                              primary="Failed Feeds"
                              secondary={progress.failed_feeds}
                            />
                          </ListItem>
                        </List>
                      </Grid>
                    </Grid>

                    {/* Errors */}
                    {progress.errors && progress.errors.length > 0 && (
                      <Box mt={2}>
                        <Typography variant="subtitle2" gutterBottom>
                          Errors ({progress.errors.length})
                        </Typography>
                        <List dense>
                          {progress.errors.slice(0, 5).map((error, index) => (
                            <ListItem key={index}>
                              <ListItemIcon>
                                <ErrorIcon fontSize="small" color="error" />
                              </ListItemIcon>
                              <ListItemText
                                primary={error.message}
                                secondary={new Date(error.timestamp).toLocaleTimeString()}
                              />
                            </ListItem>
                          ))}
                          {progress.errors.length > 5 && (
                            <ListItem>
                              <ListItemText
                                primary={`... and ${progress.errors.length - 5} more errors`}
                                color="text.secondary"
                              />
                            </ListItem>
                          )}
                        </List>
                      </Box>
                    )}
                  </Box>
                </Collapse>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      {/* No Active Collections */}
      {!hasActiveCollections && !isCollecting && (
        <Card>
          <CardContent>
            <Box textAlign="center" py={4}>
              <ScheduleIcon sx={{ fontSize: 48, color: 'action.disabled', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No Active Collections
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Click "Start Collection" to begin RSS feed collection with real-time progress tracking
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default RSSProgressTracker;
