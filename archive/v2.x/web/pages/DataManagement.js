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
  TableRow,
  Checkbox
} from '@mui/material';
import {
  Storage,
  Delete,
  Archive,
  Restore,
  Download,
  Upload,
  Backup,
  Database,
  TableChart,
  Assessment,
  Settings,
  Refresh,
  Warning,
  CheckCircle,
  Error,
  Info,
  Timeline,
  TrendingUp,
  DataUsage
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`datamgmt-tabpanel-${index}`}
      aria-labelledby={`datamgmt-tab-${index}`}
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

const DataManagement = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Database Statistics State
  const [dbStats, setDbStats] = useState({
    total_tables: 0,
    total_records: 0,
    database_size: 0,
    index_size: 0,
    last_backup: null,
    backup_frequency: 'daily'
  });
  
  // Table Statistics State
  const [tableStats, setTableStats] = useState([]);
  
  // Backup Management State
  const [backups, setBackups] = useState([]);
  const [backupProgress, setBackupProgress] = useState(0);
  const [showBackupDialog, setShowBackupDialog] = useState(false);
  const [backupConfig, setBackupConfig] = useState({
    name: '',
    description: '',
    include_data: true,
    include_indexes: true,
    compression: true
  });
  
  // Data Cleanup State
  const [cleanupStats, setCleanupStats] = useState({
    old_articles: 0,
    duplicate_records: 0,
    orphaned_records: 0,
    unused_indexes: 0,
    temp_files: 0
  });
  
  // Archive Management State
  const [archives, setArchives] = useState([]);
  const [selectedItems, setSelectedItems] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load database statistics
      setDbStats({
        total_tables: 25,
        total_records: 125000,
        database_size: 2.5, // GB
        index_size: 0.8, // GB
        last_backup: new Date(Date.now() - 6 * 60 * 60 * 1000), // 6 hours ago
        backup_frequency: 'daily'
      });
      
      // Load table statistics
      setTableStats([
        { name: 'articles', records: 45000, size: 1.2, last_updated: new Date() },
        { name: 'stories', records: 1200, size: 0.3, last_updated: new Date() },
        { name: 'entities', records: 8500, size: 0.2, last_updated: new Date() },
        { name: 'rss_feeds', records: 150, size: 0.01, last_updated: new Date() },
        { name: 'duplicate_pairs', records: 2300, size: 0.1, last_updated: new Date() },
        { name: 'rag_dossiers', records: 450, size: 0.15, last_updated: new Date() }
      ]);
      
      // Load backup history
      setBackups([
        {
          id: 1,
          name: 'Daily Backup - 2024-01-15',
          created_at: new Date(Date.now() - 6 * 60 * 60 * 1000),
          size: 2.1,
          status: 'completed',
          type: 'full'
        },
        {
          id: 2,
          name: 'Daily Backup - 2024-01-14',
          created_at: new Date(Date.now() - 30 * 60 * 60 * 1000),
          size: 2.0,
          status: 'completed',
          type: 'full'
        },
        {
          id: 3,
          name: 'Weekly Backup - 2024-01-13',
          created_at: new Date(Date.now() - 48 * 60 * 60 * 1000),
          size: 1.9,
          status: 'completed',
          type: 'full'
        }
      ]);
      
      // Load cleanup statistics
      setCleanupStats({
        old_articles: 12500,
        duplicate_records: 2300,
        orphaned_records: 150,
        unused_indexes: 5,
        temp_files: 45
      });
      
      // Load archives
      setArchives([
        {
          id: 1,
          name: 'Articles Archive - Q4 2023',
          created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          size: 0.8,
          record_count: 15000,
          status: 'active'
        },
        {
          id: 2,
          name: 'Old Stories Archive',
          created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000),
          size: 0.3,
          record_count: 5000,
          status: 'active'
        }
      ]);
      
    } catch (err) {
      setError('Failed to load data management information: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleCreateBackup = async () => {
    try {
      setLoading(true);
      setBackupProgress(0);
      
      // Simulate backup progress
      const interval = setInterval(() => {
        setBackupProgress(prev => {
          if (prev >= 100) {
            clearInterval(interval);
            setShowBackupDialog(false);
            loadData(); // Refresh data
            return 100;
          }
          return prev + 10;
        });
      }, 500);
      
    } catch (err) {
      setError('Failed to create backup: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBackup = async (backupId) => {
    if (window.confirm('Are you sure you want to delete this backup?')) {
      try {
        setBackups(backups.filter(backup => backup.id !== backupId));
      } catch (err) {
        setError('Failed to delete backup: ' + err.message);
      }
    }
  };

  const handleRestoreBackup = async (backupId) => {
    if (window.confirm('Are you sure you want to restore this backup? This will overwrite current data.')) {
      try {
        setLoading(true);
        // Simulate restore process
        setTimeout(() => {
          setLoading(false);
          setError(null);
        }, 3000);
      } catch (err) {
        setError('Failed to restore backup: ' + err.message);
        setLoading(false);
      }
    }
  };

  const handleCleanupData = async (cleanupType) => {
    try {
      setLoading(true);
      const response = await newsSystemService.triggerDatabaseCleanup();
      if (response.success) {
        loadData(); // Refresh data
      }
    } catch (err) {
      setError('Failed to cleanup data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectItem = (itemId) => {
    setSelectedItems(prev => 
      prev.includes(itemId) 
        ? prev.filter(id => id !== itemId)
        : [...prev, itemId]
    );
  };

  const handleSelectAll = () => {
    setSelectedItems(
      selectedItems.length === archives.length 
        ? [] 
        : archives.map(archive => archive.id)
    );
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'success';
      case 'active': return 'success';
      case 'failed': return 'error';
      case 'in_progress': return 'warning';
      default: return 'default';
    }
  };

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
        Data Management
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Database administration, backup management, and data lifecycle
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Database Overview" />
          <Tab label="Backup Management" />
          <Tab label="Data Cleanup" />
          <Tab label="Archive Management" />
          <Tab label="Performance" />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Database Statistics
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Database color="primary" />
                      <Typography variant="h6">{dbStats.total_tables}</Typography>
                      <Typography variant="body2">Tables</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <TableChart color="primary" />
                      <Typography variant="h6">{dbStats.total_records.toLocaleString()}</Typography>
                      <Typography variant="body2">Records</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Storage color="primary" />
                      <Typography variant="h6">{dbStats.database_size} GB</Typography>
                      <Typography variant="body2">Database Size</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <DataUsage color="primary" />
                      <Typography variant="h6">{dbStats.index_size} GB</Typography>
                      <Typography variant="body2">Index Size</Typography>
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Table Statistics
                </Typography>
                <List>
                  {tableStats.map((table) => (
                    <ListItem key={table.name} divider>
                      <ListItemText
                        primary={table.name}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {table.records.toLocaleString()} records • {table.size} GB
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Last updated: {new Date(table.last_updated).toLocaleString()}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Tooltip title="View Details">
                          <IconButton>
                            <Info />
                          </IconButton>
                        </Tooltip>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">
                    Backup History
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<Backup />}
                    onClick={() => setShowBackupDialog(true)}
                  >
                    Create Backup
                  </Button>
                </Box>
                <List>
                  {backups.map((backup) => (
                    <ListItem key={backup.id} divider>
                      <ListItemText
                        primary={backup.name}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              Created: {new Date(backup.created_at).toLocaleString()}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Size: {backup.size} GB • Type: {backup.type}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Chip 
                          label={backup.status} 
                          color={getStatusColor(backup.status)}
                          sx={{ mr: 1 }}
                        />
                        <Tooltip title="Restore">
                          <IconButton onClick={() => handleRestoreBackup(backup.id)}>
                            <Restore />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Download">
                          <IconButton>
                            <Download />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton onClick={() => handleDeleteBackup(backup.id)}>
                            <Delete />
                          </IconButton>
                        </Tooltip>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Backup Settings
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <FormControlLabel
                    control={<Switch defaultChecked />}
                    label="Automatic Daily Backups"
                  />
                  <FormControlLabel
                    control={<Switch defaultChecked />}
                    label="Weekly Full Backups"
                  />
                  <FormControlLabel
                    control={<Switch />}
                    label="Compress Backups"
                  />
                  <FormControlLabel
                    control={<Switch defaultChecked />}
                    label="Retain 30 Days"
                  />
                  <Button variant="outlined" startIcon={<Settings />}>
                    Configure Schedule
                  </Button>
                </Box>
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
                  Data Cleanup Opportunities
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Old Articles"
                      secondary={`${cleanupStats.old_articles.toLocaleString()} articles older than 1 year`}
                    />
                    <ListItemSecondaryAction>
                      <Button 
                        size="small" 
                        color="warning"
                        onClick={() => handleCleanupData('old_articles')}
                      >
                        Cleanup
                      </Button>
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Duplicate Records"
                      secondary={`${cleanupStats.duplicate_records.toLocaleString()} duplicate records found`}
                    />
                    <ListItemSecondaryAction>
                      <Button 
                        size="small" 
                        color="warning"
                        onClick={() => handleCleanupData('duplicates')}
                      >
                        Cleanup
                      </Button>
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Orphaned Records"
                      secondary={`${cleanupStats.orphaned_records.toLocaleString()} orphaned records`}
                    />
                    <ListItemSecondaryAction>
                      <Button 
                        size="small" 
                        color="error"
                        onClick={() => handleCleanupData('orphaned')}
                      >
                        Cleanup
                      </Button>
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Unused Indexes"
                      secondary={`${cleanupStats.unused_indexes} unused indexes`}
                    />
                    <ListItemSecondaryAction>
                      <Button 
                        size="small" 
                        color="info"
                        onClick={() => handleCleanupData('indexes')}
                      >
                        Optimize
                      </Button>
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
                  Cleanup Actions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    startIcon={<Delete />}
                    onClick={() => handleCleanupData('all')}
                  >
                    Full Database Cleanup
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Archive />}
                    onClick={() => handleCleanupData('archive')}
                  >
                    Archive Old Data
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Assessment />}
                    onClick={() => handleCleanupData('analyze')}
                  >
                    Analyze Database
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Settings />}
                    onClick={() => handleCleanupData('optimize')}
                  >
                    Optimize Performance
                  </Button>
                </Box>
                {backupProgress > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" gutterBottom>
                      Cleanup Progress: {backupProgress}%
                    </Typography>
                    <LinearProgress variant="determinate" value={backupProgress} />
                  </Box>
                )}
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
                Archive Management
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="outlined"
                  startIcon={<Archive />}
                  onClick={() => handleSelectAll()}
                >
                  {selectedItems.length === archives.length ? 'Deselect All' : 'Select All'}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Download />}
                  disabled={selectedItems.length === 0}
                >
                  Download Selected
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Delete />}
                  disabled={selectedItems.length === 0}
                  color="error"
                >
                  Delete Selected
                </Button>
              </Box>
            </Box>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedItems.length === archives.length}
                        indeterminate={selectedItems.length > 0 && selectedItems.length < archives.length}
                        onChange={handleSelectAll}
                      />
                    </TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Created</TableCell>
                    <TableCell>Size</TableCell>
                    <TableCell>Records</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {archives.map((archive) => (
                    <TableRow key={archive.id}>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedItems.includes(archive.id)}
                          onChange={() => handleSelectItem(archive.id)}
                        />
                      </TableCell>
                      <TableCell>{archive.name}</TableCell>
                      <TableCell>{new Date(archive.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>{archive.size} GB</TableCell>
                      <TableCell>{archive.record_count.toLocaleString()}</TableCell>
                      <TableCell>
                        <Chip 
                          label={archive.status} 
                          color={getStatusColor(archive.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Tooltip title="Download">
                          <IconButton>
                            <Download />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Restore">
                          <IconButton>
                            <Restore />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton>
                            <Delete />
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
                  Performance Metrics
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Timeline color="primary" />
                      <Typography variant="h6">245ms</Typography>
                      <Typography variant="body2">Avg Query Time</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <TrendingUp color="success" />
                      <Typography variant="h6">99.9%</Typography>
                      <Typography variant="body2">Uptime</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <DataUsage color="primary" />
                      <Typography variant="h6">85%</Typography>
                      <Typography variant="body2">Cache Hit Rate</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={6}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <CheckCircle color="success" />
                      <Typography variant="h6">Healthy</Typography>
                      <Typography variant="body2">Status</Typography>
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Maintenance Actions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    startIcon={<Refresh />}
                    onClick={() => handleCleanupData('vacuum')}
                  >
                    Vacuum Database
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Assessment />}
                    onClick={() => handleCleanupData('analyze')}
                  >
                    Update Statistics
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Settings />}
                    onClick={() => handleCleanupData('reindex')}
                  >
                    Reindex Tables
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Timeline />}
                    onClick={() => handleCleanupData('optimize')}
                  >
                    Optimize Queries
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Backup Creation Dialog */}
      <Dialog
        open={showBackupDialog}
        onClose={() => setShowBackupDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Create New Backup
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
            <TextField
              label="Backup Name"
              value={backupConfig.name}
              onChange={(e) => setBackupConfig({...backupConfig, name: e.target.value})}
              fullWidth
            />
            <TextField
              label="Description"
              value={backupConfig.description}
              onChange={(e) => setBackupConfig({...backupConfig, description: e.target.value})}
              fullWidth
              multiline
              rows={3}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={backupConfig.include_data}
                  onChange={(e) => setBackupConfig({...backupConfig, include_data: e.target.checked})}
                />
              }
              label="Include Data"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={backupConfig.include_indexes}
                  onChange={(e) => setBackupConfig({...backupConfig, include_indexes: e.target.checked})}
                />
              }
              label="Include Indexes"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={backupConfig.compression}
                  onChange={(e) => setBackupConfig({...backupConfig, compression: e.target.checked})}
                />
              }
              label="Compress Backup"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowBackupDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateBackup}>
            Create Backup
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DataManagement;
