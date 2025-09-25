import {
  Settings,
  PlayArrow,
  Stop,
  Pause,
  Refresh,
  Timeline,
  AutoAwesome,
  Assessment,
  Schedule,
  CheckCircle,
  Error,
  Warning,
  Info,
  Save,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Tooltip,
  Paper,
  Divider,
  LinearProgress,
  Switch,
  FormControlLabel,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import newsSystemService from '../../services/newsSystemService';

const TabPanel = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`automation-tabpanel-${index}`}
      aria-labelledby={`automation-tab-${index}`}
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

const AutomationPipeline = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Pipeline Status State
  const [pipelineStatus, setPipelineStatus] = useState({
    status: 'stopped',
    last_started: null,
    last_stopped: null,
    total_runs: 0,
    successful_runs: 0,
    failed_runs: 0,
    avg_processing_time: 0,
  });

  // Automation Tasks State
  const [automationTasks, setAutomationTasks] = useState([]);
  const [taskSettings, setTaskSettings] = useState({});

  // Pipeline Logs State
  const [pipelineLogs, setPipelineLogs] = useState([]);
  const [logLevel, setLogLevel] = useState('all');

  useEffect(() => {
    loadData();
    // Set up real-time updates
    const interval = setInterval(loadData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadData = async() => {
    setLoading(true);
    try {
      // Load pipeline status
      const statusResponse = await newsSystemService.getPipelineStatus();
      if (statusResponse.success) {
        setPipelineStatus(statusResponse.data);
      }

      // Load automation tasks
      setAutomationTasks([
        {
          id: 1,
          name: 'RSS Collection',
          description: 'Collect articles from RSS feeds',
          enabled: true,
          schedule: 'every 15 minutes',
          last_run: new Date().toISOString(),
          status: 'success',
          next_run: new Date(Date.now() + 15 * 60000).toISOString(),
        },
        {
          id: 2,
          name: 'ML Processing',
          description: 'Process articles with ML models',
          enabled: true,
          schedule: 'every 30 minutes',
          last_run: new Date().toISOString(),
          status: 'running',
          next_run: new Date(Date.now() + 30 * 60000).toISOString(),
        },
        {
          id: 3,
          name: 'Deduplication',
          description: 'Detect and remove duplicate articles',
          enabled: true,
          schedule: 'every hour',
          last_run: new Date().toISOString(),
          status: 'success',
          next_run: new Date(Date.now() + 60 * 60000).toISOString(),
        },
        {
          id: 4,
          name: 'Story Consolidation',
          description: 'Consolidate related articles into stories',
          enabled: false,
          schedule: 'every 2 hours',
          last_run: new Date(Date.now() - 2 * 60 * 60000).toISOString(),
          status: 'failed',
          next_run: new Date(Date.now() + 2 * 60 * 60000).toISOString(),
        },
      ]);

      // Load pipeline logs
      setPipelineLogs([
        {
          id: 1,
          timestamp: new Date().toISOString(),
          level: 'info',
          message: 'Pipeline started successfully',
          task: 'RSS Collection',
        },
        {
          id: 2,
          timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
          level: 'success',
          message: 'ML processing completed for 25 articles',
          task: 'ML Processing',
        },
        {
          id: 3,
          timestamp: new Date(Date.now() - 10 * 60000).toISOString(),
          level: 'warning',
          message: 'High memory usage detected',
          task: 'System Monitor',
        },
        {
          id: 4,
          timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
          level: 'error',
          message: 'Failed to connect to external API',
          task: 'Story Consolidation',
        },
      ]);

    } catch (err) {
      setError('Failed to load automation data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleStartPipeline = async() => {
    try {
      setLoading(true);
      const response = await newsSystemService.startPipeline();
      if (response.success) {
        setPipelineStatus(prev => ({ ...prev, status: 'running' }));
      }
    } catch (err) {
      setError('Failed to start pipeline: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStopPipeline = async() => {
    try {
      setLoading(true);
      const response = await newsSystemService.stopPipeline();
      if (response.success) {
        setPipelineStatus(prev => ({ ...prev, status: 'stopped' }));
      }
    } catch (err) {
      setError('Failed to stop pipeline: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleTask = async(taskId) => {
    try {
      setAutomationTasks(tasks =>
        tasks.map(task =>
          task.id === taskId ? { ...task, enabled: !task.enabled } : task,
        ),
      );
      // Here you would call the API to update the task status
    } catch (err) {
      setError('Failed to toggle task: ' + err.message);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
    case 'running': return 'primary';
    case 'success': return 'success';
    case 'failed': return 'error';
    case 'stopped': return 'default';
    default: return 'default';
    }
  };

  const getLogLevelColor = (level) => {
    switch (level) {
    case 'error': return 'error';
    case 'warning': return 'warning';
    case 'success': return 'success';
    case 'info': return 'info';
    default: return 'default';
    }
  };

  const getLogLevelIcon = (level) => {
    switch (level) {
    case 'error': return <Error />;
    case 'warning': return <Warning />;
    case 'success': return <CheckCircle />;
    case 'info': return <Info />;
    default: return <Info />;
    }
  };

  const filteredLogs = logLevel === 'all'
    ? pipelineLogs
    : pipelineLogs.filter(log => log.level === logLevel);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Automation Pipeline
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Manage automated data processing and system tasks
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Pipeline Status" />
          <Tab label="Automation Tasks" />
          <Tab label="Logs" />
          <Tab label="Settings" />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">
                    Pipeline Status
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      variant="contained"
                      color="success"
                      startIcon={<PlayArrow />}
                      onClick={handleStartPipeline}
                      disabled={pipelineStatus.status === 'running'}
                    >
                      Start
                    </Button>
                    <Button
                      variant="contained"
                      color="error"
                      startIcon={<Stop />}
                      onClick={handleStopPipeline}
                      disabled={pipelineStatus.status === 'stopped'}
                    >
                      Stop
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<Refresh />}
                      onClick={loadData}
                    >
                      Refresh
                    </Button>
                  </Box>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                    <Chip
                      label={pipelineStatus.status.toUpperCase()}
                      color={getStatusColor(pipelineStatus.status)}
                      icon={pipelineStatus.status === 'running' ? <PlayArrow /> : <Stop />}
                    />
                    {pipelineStatus.status === 'running' && (
                      <LinearProgress sx={{ flexGrow: 1 }} />
                    )}
                  </Box>
                </Box>

                <Grid container spacing={2}>
                  <Grid item xs={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="primary">
                        {pipelineStatus.total_runs}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Runs
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="success.main">
                        {pipelineStatus.successful_runs}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Successful
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="error.main">
                        {pipelineStatus.failed_runs}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Failed
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="info.main">
                        {pipelineStatus.avg_processing_time.toFixed(1)}s
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Avg Time
                      </Typography>
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Quick Actions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    startIcon={<AutoAwesome />}
                    onClick={() => newsSystemService.triggerStoryConsolidation()}
                  >
                    Trigger Story Consolidation
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Timeline />}
                    onClick={() => newsSystemService.generateDailyDigest()}
                  >
                    Generate Daily Digest
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Assessment />}
                    onClick={() => newsSystemService.triggerDatabaseCleanup()}
                  >
                    Database Cleanup
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Automation Tasks
            </Typography>
            <List>
              {automationTasks.map((task) => (
                <ListItem key={task.id} divider>
                  <ListItemText
                    primary={task.name}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {task.description}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Schedule: {task.schedule}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Last run: {new Date(task.last_run).toLocaleString()}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Next run: {new Date(task.next_run).toLocaleString()}
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                          <Chip
                            label={task.status}
                            color={getStatusColor(task.status)}
                            size="small"
                            sx={{ mr: 1 }}
                          />
                          <Chip
                            label={task.enabled ? 'Enabled' : 'Disabled'}
                            color={task.enabled ? 'success' : 'default'}
                            size="small"
                          />
                        </Box>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={task.enabled}
                          onChange={() => handleToggleTask(task.id)}
                        />
                      }
                      label=""
                    />
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Pipeline Logs
              </Typography>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Log Level</InputLabel>
                <Select
                  value={logLevel}
                  onChange={(e) => setLogLevel(e.target.value)}
                >
                  <MenuItem value="all">All</MenuItem>
                  <MenuItem value="error">Error</MenuItem>
                  <MenuItem value="warning">Warning</MenuItem>
                  <MenuItem value="success">Success</MenuItem>
                  <MenuItem value="info">Info</MenuItem>
                </Select>
              </FormControl>
            </Box>
            <List sx={{ maxHeight: 400, overflow: 'auto' }}>
              {filteredLogs.map((log) => (
                <ListItem key={log.id} divider>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getLogLevelIcon(log.level)}
                        <Typography variant="body2" color="text.secondary">
                          {new Date(log.timestamp).toLocaleString()}
                        </Typography>
                        <Chip
                          label={log.task}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    }
                    secondary={
                      <Typography
                        variant="body2"
                        color={getLogLevelColor(log.level)}
                        sx={{ mt: 1 }}
                      >
                        {log.message}
                      </Typography>
                    }
                  />
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Pipeline Settings
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <FormControlLabel
                    control={<Switch defaultChecked />}
                    label="Auto-start on system boot"
                  />
                  <FormControlLabel
                    control={<Switch defaultChecked />}
                    label="Enable error notifications"
                  />
                  <FormControlLabel
                    control={<Switch />}
                    label="Enable debug logging"
                  />
                  <FormControlLabel
                    control={<Switch defaultChecked />}
                    label="Auto-retry failed tasks"
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Performance Settings
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    label="Max Concurrent Tasks"
                    type="number"
                    defaultValue={4}
                    size="small"
                  />
                  <TextField
                    label="Task Timeout (minutes)"
                    type="number"
                    defaultValue={30}
                    size="small"
                  />
                  <TextField
                    label="Retry Attempts"
                    type="number"
                    defaultValue={3}
                    size="small"
                  />
                  <Button variant="contained" startIcon={<Save />}>
                    Save Settings
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};

export default AutomationPipeline;
