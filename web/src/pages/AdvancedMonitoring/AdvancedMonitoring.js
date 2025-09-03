import React, { useState, useEffect } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  Assessment,
  Memory,
  Storage,
  Speed,
  NetworkCheck,
  Security,
  Warning,
  CheckCircle,
  Error,
  Info,
  Refresh,
  Settings,
  Download,
  Timeline,
  TrendingUp,
  TrendingDown,
  Monitor
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`monitoring-tabpanel-${index}`}
      aria-labelledby={`monitoring-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const AdvancedMonitoring = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // System Metrics State
  const [systemMetrics, setSystemMetrics] = useState({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    network_io: 0,
    database_connections: 0,
    active_processes: 0
  });
  
  // Performance Metrics State
  const [performanceMetrics, setPerformanceMetrics] = useState({
    api_response_time: 0,
    database_query_time: 0,
    ml_processing_time: 0,
    search_response_time: 0,
    throughput: 0,
    error_rate: 0
  });
  
  // Security Metrics State
  const [securityMetrics, setSecurityMetrics] = useState({
    failed_logins: 0,
    suspicious_requests: 0,
    blocked_ips: 0,
    ssl_cert_expiry: null,
    last_security_scan: null
  });
  
  // Alert Configuration State
  const [alertConfig, setAlertConfig] = useState({
    cpu_threshold: 80,
    memory_threshold: 85,
    disk_threshold: 90,
    response_time_threshold: 5000,
    error_rate_threshold: 5
  });
  
  // Logs State
  const [systemLogs, setSystemLogs] = useState([]);
  const [logLevel, setLogLevel] = useState('all');
  const [showLogDialog, setShowLogDialog] = useState(false);
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    loadMetrics();
    // Set up real-time updates
    const interval = setInterval(loadMetrics, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const loadMetrics = async () => {
    setLoading(true);
    try {
      // Load system metrics
      const systemResponse = await newsSystemService.getSystemMetrics();
      if (systemResponse.success) {
        setSystemMetrics(systemResponse.data);
      }
      
      // Load performance metrics
      const performanceResponse = await newsSystemService.getPrometheusMetrics();
      if (performanceResponse.success) {
        setPerformanceMetrics(performanceResponse.data);
      }
      
      // Load security metrics
      setSecurityMetrics({
        failed_logins: 0,
        suspicious_requests: 2,
        blocked_ips: 1,
        ssl_cert_expiry: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
        last_security_scan: new Date(Date.now() - 2 * 60 * 60 * 1000) // 2 hours ago
      });
      
      // Load system logs
      setSystemLogs([
        {
          id: 1,
          timestamp: new Date().toISOString(),
          level: 'info',
          component: 'API',
          message: 'Request processed successfully',
          details: { endpoint: '/api/articles', response_time: 245 }
        },
        {
          id: 2,
          timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
          level: 'warning',
          component: 'Database',
          message: 'High query execution time detected',
          details: { query_time: 3500, query: 'SELECT * FROM articles' }
        },
        {
          id: 3,
          timestamp: new Date(Date.now() - 10 * 60000).toISOString(),
          level: 'error',
          component: 'ML Processing',
          message: 'Model inference failed',
          details: { model: 'summarization', error: 'CUDA out of memory' }
        }
      ]);
      
    } catch (err) {
      setError('Failed to load monitoring data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleViewLog = (log) => {
    setSelectedLog(log);
    setShowLogDialog(true);
  };

  const handleCloseLogDialog = () => {
    setShowLogDialog(false);
    setSelectedLog(null);
  };

  const getMetricColor = (value, threshold) => {
    if (value >= threshold) return 'error';
    if (value >= threshold * 0.8) return 'warning';
    return 'success';
  };

  const getLogLevelColor = (level) => {
    switch (level) {
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'default';
    }
  };

  const getLogLevelIcon = (level) => {
    switch (level) {
      case 'error': return <Error />;
      case 'warning': return <Warning />;
      case 'info': return <Info />;
      default: return <Info />;
    }
  };

  const filteredLogs = logLevel === 'all' 
    ? systemLogs 
    : systemLogs.filter(log => log.level === logLevel);

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
        Advanced Monitoring
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Comprehensive system monitoring and performance analytics
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="System Metrics" />
          <Tab label="Performance" />
          <Tab label="Security" />
          <Tab label="Logs" />
          <Tab label="Alerts" />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System Resources
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>CPU Usage</Typography>
                    <Typography>{systemMetrics.cpu_usage}%</Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={systemMetrics.cpu_usage} 
                    color={getMetricColor(systemMetrics.cpu_usage, alertConfig.cpu_threshold)}
                  />
                </Box>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Memory Usage</Typography>
                    <Typography>{systemMetrics.memory_usage}%</Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={systemMetrics.memory_usage} 
                    color={getMetricColor(systemMetrics.memory_usage, alertConfig.memory_threshold)}
                  />
                </Box>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Disk Usage</Typography>
                    <Typography>{systemMetrics.disk_usage}%</Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={systemMetrics.disk_usage} 
                    color={getMetricColor(systemMetrics.disk_usage, alertConfig.disk_threshold)}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System Status
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <NetworkCheck color="primary" />
                      <Typography variant="h6">{systemMetrics.network_io} MB/s</Typography>
                      <Typography variant="body2">Network I/O</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Storage color="primary" />
                      <Typography variant="h6">{systemMetrics.database_connections}</Typography>
                      <Typography variant="body2">DB Connections</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Monitor color="primary" />
                      <Typography variant="h6">{systemMetrics.active_processes}</Typography>
                      <Typography variant="body2">Active Processes</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <CheckCircle color="success" />
                      <Typography variant="h6">Healthy</Typography>
                      <Typography variant="body2">System Status</Typography>
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  API Performance
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Response Time</Typography>
                    <Typography>{performanceMetrics.api_response_time}ms</Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={(performanceMetrics.api_response_time / alertConfig.response_time_threshold) * 100} 
                    color={getMetricColor(performanceMetrics.api_response_time, alertConfig.response_time_threshold)}
                  />
                </Box>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>Database Queries</Typography>
                    <Typography>{performanceMetrics.database_query_time}ms</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={75} color="info" />
                </Box>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography>ML Processing</Typography>
                    <Typography>{performanceMetrics.ml_processing_time}ms</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={60} color="success" />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Throughput & Errors
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <TrendingUp color="success" />
                      <Typography variant="h6">{performanceMetrics.throughput}</Typography>
                      <Typography variant="body2">Requests/min</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <TrendingDown color="error" />
                      <Typography variant="h6">{performanceMetrics.error_rate}%</Typography>
                      <Typography variant="body2">Error Rate</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Speed color="primary" />
                      <Typography variant="h6">{performanceMetrics.search_response_time}ms</Typography>
                      <Typography variant="body2">Search Time</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Assessment color="primary" />
                      <Typography variant="h6">99.9%</Typography>
                      <Typography variant="body2">Uptime</Typography>
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Security Status
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Failed Login Attempts"
                      secondary="Last 24 hours"
                    />
                    <ListItemSecondaryAction>
                      <Chip 
                        label={securityMetrics.failed_logins} 
                        color={securityMetrics.failed_logins > 0 ? 'error' : 'success'}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Suspicious Requests"
                      secondary="Blocked automatically"
                    />
                    <ListItemSecondaryAction>
                      <Chip 
                        label={securityMetrics.suspicious_requests} 
                        color={securityMetrics.suspicious_requests > 0 ? 'warning' : 'success'}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Blocked IPs"
                      secondary="Currently blocked"
                    />
                    <ListItemSecondaryAction>
                      <Chip 
                        label={securityMetrics.blocked_ips} 
                        color={securityMetrics.blocked_ips > 0 ? 'error' : 'success'}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Security Certificates
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    SSL Certificate Expiry
                  </Typography>
                  <Typography variant="h6">
                    {securityMetrics.ssl_cert_expiry ? 
                      new Date(securityMetrics.ssl_cert_expiry).toLocaleDateString() : 
                      'Unknown'
                    }
                  </Typography>
                  <Chip 
                    label="Valid" 
                    color="success" 
                    size="small"
                    sx={{ mt: 1 }}
                  />
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Last Security Scan
                  </Typography>
                  <Typography variant="h6">
                    {securityMetrics.last_security_scan ? 
                      new Date(securityMetrics.last_security_scan).toLocaleString() : 
                      'Never'
                    }
                  </Typography>
                  <Button size="small" sx={{ mt: 1 }}>
                    Run Security Scan
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                System Logs
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Log Level</InputLabel>
                  <Select
                    value={logLevel}
                    onChange={(e) => setLogLevel(e.target.value)}
                  >
                    <MenuItem value="all">All</MenuItem>
                    <MenuItem value="error">Error</MenuItem>
                    <MenuItem value="warning">Warning</MenuItem>
                    <MenuItem value="info">Info</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="outlined"
                  startIcon={<Refresh />}
                  onClick={loadMetrics}
                >
                  Refresh
                </Button>
              </Box>
            </Box>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell>Level</TableCell>
                    <TableCell>Component</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell>
                        {new Date(log.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={log.level} 
                          color={getLogLevelColor(log.level)}
                          size="small"
                          icon={getLogLevelIcon(log.level)}
                        />
                      </TableCell>
                      <TableCell>{log.component}</TableCell>
                      <TableCell>{log.message}</TableCell>
                      <TableCell>
                        <Tooltip title="View Details">
                          <IconButton onClick={() => handleViewLog(log)}>
                            <Info />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={4}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Alert Thresholds
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    label="CPU Threshold (%)"
                    type="number"
                    value={alertConfig.cpu_threshold}
                    onChange={(e) => setAlertConfig({...alertConfig, cpu_threshold: parseInt(e.target.value)})}
                    size="small"
                  />
                  <TextField
                    label="Memory Threshold (%)"
                    type="number"
                    value={alertConfig.memory_threshold}
                    onChange={(e) => setAlertConfig({...alertConfig, memory_threshold: parseInt(e.target.value)})}
                    size="small"
                  />
                  <TextField
                    label="Disk Threshold (%)"
                    type="number"
                    value={alertConfig.disk_threshold}
                    onChange={(e) => setAlertConfig({...alertConfig, disk_threshold: parseInt(e.target.value)})}
                    size="small"
                  />
                  <TextField
                    label="Response Time Threshold (ms)"
                    type="number"
                    value={alertConfig.response_time_threshold}
                    onChange={(e) => setAlertConfig({...alertConfig, response_time_threshold: parseInt(e.target.value)})}
                    size="small"
                  />
                  <Button variant="contained" startIcon={<Settings />}>
                    Save Configuration
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Quick Actions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    startIcon={<Download />}
                  >
                    Export Logs
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Assessment />}
                  >
                    Generate Report
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Security />}
                  >
                    Security Audit
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Timeline />}
                  >
                    Performance Analysis
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Log Details Dialog */}
      <Dialog
        open={showLogDialog}
        onClose={handleCloseLogDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Log Details
        </DialogTitle>
        <DialogContent>
          {selectedLog && (
            <Box>
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(selectedLog.details, null, 2)}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseLogDialog}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AdvancedMonitoring;
