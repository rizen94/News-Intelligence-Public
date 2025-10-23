import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh,
  Timeline as TimelineIcon,
  Speed as SpeedIcon,
  Queue as QueueIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Schedule,
} from '@mui/icons-material';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Tabs,
  Tab,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import newsSystemService from '../../services/newsSystemService';

const TabPanel = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`ml-tabpanel-${index}`}
      aria-labelledby={`ml-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

const MLProcessing = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [queueStatus, setQueueStatus] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [timingStats, setTimingStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [queueDialogOpen, setQueueDialogOpen] = useState(false);
  const [selectedArticleId, setSelectedArticleId] = useState('');
  const [operationType, setOperationType] = useState('full_analysis');
  const [priority, setPriority] = useState(0);
  const [modelName, setModelName] = useState('');

  // Auto-refresh data every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadData();
    }, 10000);

    loadData();
    return () => clearInterval(interval);
  }, []);

  const loadData = async() => {
    try {
      setLoading(true);
      setError(null);

      const [queueData, processingData, timingData] = await Promise.all([
        newsSystemService.getMLQueueStatus(),
        newsSystemService.getAllMLProcessingStatus(),
        newsSystemService.getMLTimingStats(),
      ]);

      setQueueStatus(queueData.queue_status);
      setProcessingStatus(processingData.status);
      setTimingStats(timingData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQueueArticle = async() => {
    if (!selectedArticleId) {
      setError('Please enter an article ID');
      return;
    }

    try {
      setLoading(true);
      await newsSystemService.queueArticleForMLProcessing(
        parseInt(selectedArticleId),
        operationType,
        priority,
        modelName || null,
      );

      setQueueDialogOpen(false);
      setSelectedArticleId('');
      setOperationType('full_analysis');
      setPriority(0);
      setModelName('');

      // Refresh data
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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
    case 'processing': return <CircularProgress size={16} />;
    case 'failed': return <ErrorIcon />;
    case 'queued': return <Schedule />;
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

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          ML Processing Monitor
        </Typography>
        <Box>
          <Tooltip title="Refresh Data">
            <IconButton onClick={loadData} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<PlayIcon />}
            onClick={() => setQueueDialogOpen(true)}
            sx={{ ml: 1 }}
          >
            Queue Article
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Queue Status" icon={<QueueIcon />} />
          <Tab label="Processing Status" icon={<TimelineIcon />} />
          <Tab label="Timing Statistics" icon={<SpeedIcon />} />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          {/* Worker Statistics */}
          {queueStatus?.worker_stats && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Worker Statistics
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography>Status:</Typography>
                      <Chip
                        label={queueStatus.worker_stats.is_running ? 'Running' : 'Stopped'}
                        color={queueStatus.worker_stats.is_running ? 'success' : 'error'}
                        size="small"
                      />
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography>Active Workers:</Typography>
                      <Typography>{queueStatus.worker_stats.active_workers}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography>Queue Size:</Typography>
                      <Typography>{queueStatus.worker_stats.queue_size}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography>Total Processed:</Typography>
                      <Typography>{queueStatus.worker_stats.total_processed}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography>Success Rate:</Typography>
                      <Typography>
                        {queueStatus.worker_stats.total_processed > 0
                          ? ((queueStatus.worker_stats.successful / queueStatus.worker_stats.total_processed) * 100).toFixed(1)
                          : 0}%
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography>Avg Processing Time:</Typography>
                      <Typography>{formatDuration(queueStatus.worker_stats.avg_processing_time)}</Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Queue Statistics */}
          {queueStatus?.queue_stats && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Queue Statistics
                  </Typography>
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Status</TableCell>
                          <TableCell>Operation</TableCell>
                          <TableCell>Count</TableCell>
                          <TableCell>Avg Wait</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {queueStatus.queue_stats.map((stat, index) => (
                          <TableRow key={index}>
                            <TableCell>
                              <Chip
                                label={stat.status}
                                color={getStatusColor(stat.status)}
                                size="small"
                                icon={getStatusIcon(stat.status)}
                              />
                            </TableCell>
                            <TableCell>{stat.operation_type}</TableCell>
                            <TableCell>{stat.count}</TableCell>
                            <TableCell>{formatDuration(stat.avg_wait_time_seconds)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        {processingStatus?.articles && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Processing Activity ({processingStatus.total_count} total)
              </Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Article ID</TableCell>
                      <TableCell>Title</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Model</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell>Started</TableCell>
                      <TableCell>Completed</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {processingStatus.articles.map((article) => (
                      <TableRow key={article.article_id}>
                        <TableCell>{article.article_id}</TableCell>
                        <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {article.title}
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={article.status}
                            color={getStatusColor(article.status)}
                            size="small"
                            icon={getStatusIcon(article.status)}
                          />
                        </TableCell>
                        <TableCell>{article.model_used || 'N/A'}</TableCell>
                        <TableCell>{formatDuration(article.duration_seconds)}</TableCell>
                        <TableCell>{formatDateTime(article.started_at)}</TableCell>
                        <TableCell>{formatDateTime(article.completed_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        )}
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <Grid container spacing={3}>
          {/* Timing Statistics */}
          {timingStats?.timing_stats && (
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Daily Timing Statistics
                  </Typography>
                  <TableContainer component={Paper} variant="outlined">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Date</TableCell>
                          <TableCell>Model</TableCell>
                          <TableCell>Total Processed</TableCell>
                          <TableCell>Avg Duration</TableCell>
                          <TableCell>Min Duration</TableCell>
                          <TableCell>Max Duration</TableCell>
                          <TableCell>Success Rate</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {timingStats.timing_stats.map((stat, index) => (
                          <TableRow key={index}>
                            <TableCell>{stat.processing_date}</TableCell>
                            <TableCell>{stat.model_used}</TableCell>
                            <TableCell>{stat.total_processed}</TableCell>
                            <TableCell>{formatDuration(stat.avg_duration_seconds)}</TableCell>
                            <TableCell>{formatDuration(stat.min_duration_seconds)}</TableCell>
                            <TableCell>{formatDuration(stat.max_duration_seconds)}</TableCell>
                            <TableCell>
                              {stat.total_processed > 0
                                ? ((stat.successful_count / stat.total_processed) * 100).toFixed(1)
                                : 0}%
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Recent Processing Logs */}
          {timingStats?.recent_logs && (
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Recent Processing Logs
                  </Typography>
                  <TableContainer component={Paper} variant="outlined">
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Operation</TableCell>
                          <TableCell>Model</TableCell>
                          <TableCell>Duration</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell>Started</TableCell>
                          <TableCell>Article</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {timingStats.recent_logs.map((log, index) => (
                          <TableRow key={index}>
                            <TableCell>{log.operation_type}</TableCell>
                            <TableCell>{log.model_name}</TableCell>
                            <TableCell>{formatDuration(log.duration_seconds)}</TableCell>
                            <TableCell>
                              <Chip
                                label={log.status}
                                color={getStatusColor(log.status)}
                                size="small"
                                icon={getStatusIcon(log.status)}
                              />
                            </TableCell>
                            <TableCell>{formatDateTime(log.started_at)}</TableCell>
                            <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {log.article_title}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
      </TabPanel>

      {/* Queue Article Dialog */}
      <Dialog open={queueDialogOpen} onClose={() => setQueueDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Queue Article for ML Processing</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Article ID"
              value={selectedArticleId}
              onChange={(e) => setSelectedArticleId(e.target.value)}
              type="number"
              fullWidth
            />
            <FormControl fullWidth>
              <InputLabel>Operation Type</InputLabel>
              <Select
                value={operationType}
                onChange={(e) => setOperationType(e.target.value)}
                label="Operation Type"
              >
                <MenuItem value="summarization">Summarization</MenuItem>
                <MenuItem value="key_points">Key Points</MenuItem>
                <MenuItem value="argument_analysis">Argument Analysis</MenuItem>
                <MenuItem value="sentiment">Sentiment Analysis</MenuItem>
                <MenuItem value="full_analysis">Full Analysis</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Priority"
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value) || 0)}
              type="number"
              fullWidth
              helperText="Higher number = higher priority"
            />
            <TextField
              label="Model Name (Optional)"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              fullWidth
              helperText="Leave empty to use default model"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setQueueDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleQueueArticle}
            variant="contained"
            disabled={loading || !selectedArticleId}
          >
            {loading ? <CircularProgress size={20} /> : 'Queue Article'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MLProcessing;
