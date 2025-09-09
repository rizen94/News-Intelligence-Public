import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
  Collapse,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Avatar,
  Badge
} from '@mui/material';
import {
  Psychology as PsychologyIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

function MLProcessingStatus() {
  const [processingStatus, setProcessingStatus] = useState(null);
  const [queueStatus, setQueueStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(null);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadStatus();
    }, 5000);

    loadStatus();
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      setError(null);
      const [processingData, queueData] = await Promise.all([
        newsSystemService.getAllMLProcessingStatus(),
        newsSystemService.getMLQueueStatus()
      ]);

      setProcessingStatus(processingData.status);
      setQueueStatus(queueData.queue_status);
    } catch (err) {
      setError(err.message);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'success';
      case 'processing': return 'warning';
      case 'failed': return 'error';
      case 'queued': return 'info';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircleIcon />;
      case 'processing': return <PlayArrowIcon />;
      case 'failed': return <ErrorIcon />;
      case 'queued': return <ScheduleIcon />;
      default: return null;
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  // Get current processing tasks
  const getCurrentProcessingTasks = () => {
    if (!processingStatus?.articles) return [];
    
    return processingStatus.articles.filter(article => 
      article.status === 'processing'
    ).slice(0, 3); // Show max 3 current tasks
  };

  // Get queued tasks
  const getQueuedTasks = () => {
    if (!queueStatus?.queue_stats) return [];
    
    return queueStatus.queue_stats.filter(stat => 
      stat.status === 'queued'
    );
  };

  const currentTasks = getCurrentProcessingTasks();
  const queuedTasks = getQueuedTasks();
  const totalQueued = queuedTasks.reduce((sum, task) => sum + task.count, 0);
  const isProcessing = currentTasks.length > 0 || totalQueued > 0;

  // Calculate progress for current tasks
  const getTaskProgress = (task) => {
    if (!task.started_at) return 0;
    
    const startTime = new Date(task.started_at).getTime();
    const currentTime = new Date().getTime();
    const elapsed = (currentTime - startTime) / 1000; // seconds
    
    // Estimate progress based on typical processing times
    // Summarization: ~100s, Key Points: ~25s, Arguments: ~80s, Sentiment: ~15s
    const estimatedDuration = {
      'summarization': 100,
      'key_points': 25,
      'argument_analysis': 80,
      'sentiment': 15,
      'full_analysis': 200
    };
    
    const estimated = estimatedDuration[task.operation_type] || 60;
    return Math.min((elapsed / estimated) * 100, 95); // Cap at 95% until completion
  };

  if (error) {
    return (
      <Card sx={{ mb: 2, border: '1px solid', borderColor: 'error.main' }}>
        <CardContent sx={{ py: 1 }}>
          <Typography variant="body2" color="error">
            ML Status Error: {error}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2, border: '1px solid', borderColor: isProcessing ? 'warning.main' : 'success.main' }}>
      <CardContent sx={{ py: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Badge 
              color={isProcessing ? 'warning' : 'success'} 
              variant="dot"
              invisible={!isProcessing}
            >
              <PsychologyIcon color={isProcessing ? 'warning' : 'success'} />
            </Badge>
            <Typography variant="h6" component="div">
              ML Processing Status
            </Typography>
            {isProcessing && (
              <Chip 
                label={`${currentTasks.length} Active, ${totalQueued} Queued`}
                color="warning"
                size="small"
                icon={<PlayArrowIcon />}
              />
            )}
            {!isProcessing && (
              <Chip 
                label="Idle"
                color="success"
                size="small"
                icon={<CheckCircleIcon />}
              />
            )}
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title="Refresh Status">
              <IconButton 
                size="small" 
                onClick={loadStatus}
                disabled={loading}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <IconButton 
              size="small" 
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>
        </Box>

        {/* Current Processing Tasks */}
        {currentTasks.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Currently Processing:
            </Typography>
            {currentTasks.map((task, index) => (
              <Box key={index} sx={{ mb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Chip 
                    label={task.operation_type}
                    color={getStatusColor(task.status)}
                    size="small"
                    icon={getStatusIcon(task.status)}
                  />
                  <Typography variant="body2" sx={{ flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {task.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDuration((new Date().getTime() - new Date(task.started_at).getTime()) / 1000)}
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={getTaskProgress(task)}
                  sx={{ height: 4, borderRadius: 2 }}
                />
              </Box>
            ))}
          </Box>
        )}

        {/* Queued Tasks Summary */}
        {totalQueued > 0 && currentTasks.length === 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {totalQueued} task{totalQueued > 1 ? 's' : ''} queued for processing
            </Typography>
          </Box>
        )}

        {/* Expanded Details */}
        <Collapse in={expanded}>
          <Box sx={{ mt: 2 }}>
            {/* Worker Statistics */}
            {queueStatus?.worker_stats && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Worker Statistics:
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Chip 
                    label={`${queueStatus.worker_stats.active_workers} Workers`}
                    variant="outlined"
                    size="small"
                  />
                  <Chip 
                    label={`${queueStatus.worker_stats.total_processed} Processed`}
                    variant="outlined"
                    size="small"
                  />
                  <Chip 
                    label={`${queueStatus.worker_stats.successful} Successful`}
                    variant="outlined"
                    size="small"
                    color="success"
                  />
                  {queueStatus.worker_stats.failed > 0 && (
                    <Chip 
                      label={`${queueStatus.worker_stats.failed} Failed`}
                      variant="outlined"
                      size="small"
                      color="error"
                    />
                  )}
                  {queueStatus.worker_stats.avg_processing_time > 0 && (
                    <Chip 
                      label={`Avg: ${formatDuration(queueStatus.worker_stats.avg_processing_time)}`}
                      variant="outlined"
                      size="small"
                    />
                  )}
                </Box>
              </Box>
            )}

            {/* Recent Processing History */}
            {processingStatus?.articles && processingStatus.articles.length > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Recent Activity:
                </Typography>
                <List dense sx={{ maxHeight: 200, overflow: 'auto' }}>
                  {processingStatus.articles.slice(0, 5).map((article, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <Avatar sx={{ width: 24, height: 24, bgcolor: `${getStatusColor(article.status)}.main` }}>
                          {getStatusIcon(article.status)}
                        </Avatar>
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body2" sx={{ flexGrow: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {article.title}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatDuration(article.duration_seconds)}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Chip 
                              label={article.status}
                              color={getStatusColor(article.status)}
                              size="small"
                              sx={{ height: 16, fontSize: '0.7rem' }}
                            />
                            {article.model_used && (
                              <Typography variant="caption" color="text.secondary">
                                {article.model_used.split(':')[0]}
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}

export default MLProcessingStatus;
