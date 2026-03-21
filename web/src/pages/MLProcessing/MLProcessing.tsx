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

import apiService from '../../services/apiService';

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

const TabPanel: React.FC<TabPanelProps> = ({
  children,
  value,
  index,
  ...other
}) => {
  return (
    <div
      role='tabpanel'
      hidden={value !== index}
      id={`ml-tabpanel-${index}`}
      aria-labelledby={`ml-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
};

const MLProcessing: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [queueStatus, setQueueStatus] = useState<any>(null);
  const [processingStatus, setProcessingStatus] = useState<any>(null);
  const [timingStats, setTimingStats] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [queueDialogOpen, setQueueDialogOpen] = useState<boolean>(false);
  const [selectedArticleId, setSelectedArticleId] = useState<string>('');
  const [operationType, setOperationType] = useState<string>('full_analysis');
  const [priority, setPriority] = useState<string>('normal');
  const [modelName, setModelName] = useState<string>('');
  const [eventPipelineStats, setEventPipelineStats] = useState<any>(null);

  // Auto-refresh data every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadData();
    }, 10000);

    loadData();
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [queueData, processingData, timingData, eventStats] =
        await Promise.all([
          apiService.getMLQueueStatus(),
          apiService.getAllMLProcessingStatus(),
          apiService.getMLTimingStats(),
          apiService.getPipelineStatus().catch(() => null),
        ]);

      setQueueStatus(queueData.queue_status);
      setProcessingStatus(processingData.status);
      setTimingStats(timingData);
      if (eventStats?.data) setEventPipelineStats(eventStats.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQueueArticle = async () => {
    if (!selectedArticleId) {
      setError('Please enter an article ID');
      return;
    }

    try {
      setLoading(true);
      await apiService.queueArticleForMLProcessing(
        parseInt(selectedArticleId),
        operationType,
        priority,
        modelName || null
      );

      setQueueDialogOpen(false);
      setSelectedArticleId('');
      setOperationType('full_analysis');
      setPriority('normal');
      setModelName('');

      // Refresh data
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'processing':
        return 'warning';
      case 'failed':
        return 'error';
      case 'queued':
        return 'info';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon />;
      case 'processing':
        return <CircularProgress size={16} />;
      case 'failed':
        return <ErrorIcon />;
      case 'queued':
        return <Schedule />;
      default:
        return null;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Typography variant='h4' component='h1'>
          ML Processing Monitor
        </Typography>
        <Box>
          <Tooltip title='Refresh Data'>
            <span>
              <IconButton onClick={loadData} disabled={loading}>
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
          <Button
            variant='contained'
            startIcon={<PlayIcon />}
            onClick={() => setQueueDialogOpen(true)}
            sx={{ ml: 1 }}
          >
            Queue Article
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
        >
          <Tab label='Queue Status' icon={<QueueIcon />} />
          <Tab label='Processing Status' icon={<TimelineIcon />} />
          <Tab label='Timing Statistics' icon={<SpeedIcon />} />
          <Tab label='Event Pipeline' icon={<TimelineIcon />} />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          {/* Worker Statistics */}
          {queueStatus?.worker_stats && (
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant='h6' gutterBottom>
                    Worker Statistics
                  </Typography>
                  <Box
                    sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}
                  >
                    <Box
                      sx={{ display: 'flex', justifyContent: 'space-between' }}
                    >
                      <Typography>Status:</Typography>
                      <Chip
                        label={
                          queueStatus.worker_stats.is_running
                            ? 'Running'
                            : 'Stopped'
                        }
                        color={
                          queueStatus.worker_stats.is_running
                            ? 'success'
                            : 'error'
                        }
                        size='small'
                      />
                    </Box>
                    <Box
                      sx={{ display: 'flex', justifyContent: 'space-between' }}
                    >
                      <Typography>Active Workers:</Typography>
                      <Typography>
                        {queueStatus.worker_stats.active_workers}
                      </Typography>
                    </Box>
                    <Box
                      sx={{ display: 'flex', justifyContent: 'space-between' }}
                    >
                      <Typography>Queue Size:</Typography>
                      <Typography>
                        {queueStatus.worker_stats.queue_size}
                      </Typography>
                    </Box>
                    <Box
                      sx={{ display: 'flex', justifyContent: 'space-between' }}
                    >
                      <Typography>Total Processed:</Typography>
                      <Typography>
                        {queueStatus.worker_stats.total_processed}
                      </Typography>
                    </Box>
                    <Box
                      sx={{ display: 'flex', justifyContent: 'space-between' }}
                    >
                      <Typography>Success Rate:</Typography>
                      <Typography>
                        {queueStatus.worker_stats.total_processed > 0
                          ? (
                              (queueStatus.worker_stats.successful /
                                queueStatus.worker_stats.total_processed) *
                              100
                            ).toFixed(1)
                          : 0}
                        %
                      </Typography>
                    </Box>
                    <Box
                      sx={{ display: 'flex', justifyContent: 'space-between' }}
                    >
                      <Typography>Avg Processing Time:</Typography>
                      <Typography>
                        {formatDuration(
                          queueStatus.worker_stats.avg_processing_time
                        )}
                      </Typography>
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
                  <Typography variant='h6' gutterBottom>
                    Queue Statistics
                  </Typography>
                  <TableContainer component={Paper} variant='outlined'>
                    <Table size='small'>
                      <TableHead>
                        <TableRow>
                          <TableCell>Status</TableCell>
                          <TableCell>Operation</TableCell>
                          <TableCell>Count</TableCell>
                          <TableCell>Avg Wait</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {queueStatus.queue_stats.map(
                          (stat: any, index: number) => (
                            <TableRow key={index}>
                              <TableCell>
                                <Chip
                                  label={stat.status}
                                  color={getStatusColor(stat.status)}
                                  size='small'
                                  icon={getStatusIcon(stat.status)}
                                />
                              </TableCell>
                              <TableCell>{stat.operation_type}</TableCell>
                              <TableCell>{stat.count}</TableCell>
                              <TableCell>
                                {formatDuration(stat.avg_wait_time_seconds)}
                              </TableCell>
                            </TableRow>
                          )
                        )}
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
              <Typography variant='h6' gutterBottom>
                Recent Processing Activity ({processingStatus.total_count}{' '}
                total)
              </Typography>
              <TableContainer component={Paper} variant='outlined'>
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
                    {processingStatus.articles.map((article: any) => (
                      <TableRow key={article.article_id}>
                        <TableCell>{article.article_id}</TableCell>
                        <TableCell
                          sx={{
                            maxWidth: 300,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {article.title}
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={article.status}
                            color={getStatusColor(article.status)}
                            size='small'
                            icon={getStatusIcon(article.status)}
                          />
                        </TableCell>
                        <TableCell>{article.model_used || 'N/A'}</TableCell>
                        <TableCell>
                          {formatDuration(article.duration_seconds)}
                        </TableCell>
                        <TableCell>
                          {formatDateTime(article.started_at)}
                        </TableCell>
                        <TableCell>
                          {formatDateTime(article.completed_at)}
                        </TableCell>
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
                  <Typography variant='h6' gutterBottom>
                    Daily Timing Statistics
                  </Typography>
                  <TableContainer component={Paper} variant='outlined'>
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
                        {timingStats.timing_stats.map(
                          (stat: any, index: number) => (
                            <TableRow key={index}>
                              <TableCell>{stat.processing_date}</TableCell>
                              <TableCell>{stat.model_used}</TableCell>
                              <TableCell>{stat.total_processed}</TableCell>
                              <TableCell>
                                {formatDuration(stat.avg_duration_seconds)}
                              </TableCell>
                              <TableCell>
                                {formatDuration(stat.min_duration_seconds)}
                              </TableCell>
                              <TableCell>
                                {formatDuration(stat.max_duration_seconds)}
                              </TableCell>
                              <TableCell>
                                {stat.total_processed > 0
                                  ? (
                                      (stat.successful_count /
                                        stat.total_processed) *
                                      100
                                    ).toFixed(1)
                                  : 0}
                                %
                              </TableCell>
                            </TableRow>
                          )
                        )}
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
                  <Typography variant='h6' gutterBottom>
                    Recent Processing Logs
                  </Typography>
                  <TableContainer component={Paper} variant='outlined'>
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
                        {timingStats.recent_logs.map(
                          (log: any, index: number) => (
                            <TableRow key={index}>
                              <TableCell>{log.operation_type}</TableCell>
                              <TableCell>{log.model_name}</TableCell>
                              <TableCell>
                                {formatDuration(log.duration_seconds)}
                              </TableCell>
                              <TableCell>
                                <Chip
                                  label={log.status}
                                  color={getStatusColor(log.status)}
                                  size='small'
                                  icon={getStatusIcon(log.status)}
                                />
                              </TableCell>
                              <TableCell>
                                {formatDateTime(log.started_at)}
                              </TableCell>
                              <TableCell
                                sx={{
                                  maxWidth: 200,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                              >
                                {log.article_title}
                              </TableCell>
                            </TableRow>
                          )
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
      </TabPanel>

      {/* Event Pipeline Tab (v5.0) */}
      <TabPanel value={activeTab} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  Event Extraction & Deduplication Pipeline
                </Typography>
                {eventPipelineStats ? (
                  <Grid container spacing={2}>
                    <Grid item xs={6} md={3}>
                      <Typography variant='h4' color='primary'>
                        {eventPipelineStats.pipeline_status === 'running'
                          ? 'RUNNING'
                          : 'IDLE'}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Pipeline Status
                      </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Typography variant='h4' color='primary'>
                        {eventPipelineStats.success_rate || 0}%
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Success Rate
                      </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Typography variant='h4' color='primary'>
                        {eventPipelineStats.active_traces || 0}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Active Traces
                      </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Typography variant='h4' color='primary'>
                        {eventPipelineStats.total_traces || 0}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Total Traces
                      </Typography>
                    </Grid>
                  </Grid>
                ) : (
                  <Typography variant='body2' color='text.secondary'>
                    Event pipeline statistics unavailable. The event extraction,
                    deduplication, and story continuation tasks run on a
                    schedule via the automation manager.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  v5.0 Automated Tasks
                </Typography>
                <Table size='small'>
                  <TableHead>
                    <TableRow>
                      <TableCell>Task</TableCell>
                      <TableCell>Interval</TableCell>
                      <TableCell>Description</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>Event Extraction</TableCell>
                      <TableCell>10 min</TableCell>
                      <TableCell>
                        Extracts structured events from new articles
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Event Deduplication</TableCell>
                      <TableCell>15 min</TableCell>
                      <TableCell>
                        Cross-source dedup via fingerprint + semantic similarity
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Story Continuation</TableCell>
                      <TableCell>20 min</TableCell>
                      <TableCell>
                        Matches new events to existing storylines
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Watchlist Alerts</TableCell>
                      <TableCell>30 min</TableCell>
                      <TableCell>
                        Generates alerts for watched storyline changes
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  Pipeline Stages
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {[
                    'Event Extraction',
                    'Fingerprint Dedup',
                    'Semantic Dedup',
                    'Story Matching',
                    'Entity Indexing',
                  ].map((stage, i) => (
                    <Box
                      key={i}
                      sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
                    >
                      <CheckCircleIcon color='success' fontSize='small' />
                      <Typography variant='body2'>{stage}</Typography>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Queue Article Dialog */}
      <Dialog
        open={queueDialogOpen}
        onClose={() => setQueueDialogOpen(false)}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>Queue Article for ML Processing</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label='Article ID'
              value={selectedArticleId}
              onChange={e => setSelectedArticleId(e.target.value)}
              type='number'
              fullWidth
            />
            <FormControl fullWidth>
              <InputLabel>Operation Type</InputLabel>
              <Select
                value={operationType}
                onChange={e => setOperationType(e.target.value)}
                label='Operation Type'
              >
                <MenuItem value='summarization'>Summarization</MenuItem>
                <MenuItem value='key_points'>Key Points</MenuItem>
                <MenuItem value='argument_analysis'>Argument Analysis</MenuItem>
                <MenuItem value='sentiment'>Sentiment Analysis</MenuItem>
                <MenuItem value='full_analysis'>Full Analysis</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={priority}
                onChange={e => setPriority(e.target.value as string)}
                label='Priority'
              >
                <MenuItem value='low'>Low</MenuItem>
                <MenuItem value='normal'>Normal</MenuItem>
                <MenuItem value='high'>High</MenuItem>
                <MenuItem value='urgent'>Urgent</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label='Model Name (Optional)'
              value={modelName}
              onChange={e => setModelName(e.target.value)}
              fullWidth
              helperText='Leave empty to use default model'
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setQueueDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleQueueArticle}
            variant='contained'
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
