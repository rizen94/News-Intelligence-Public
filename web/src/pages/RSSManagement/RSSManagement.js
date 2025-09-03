import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Paper,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  Badge,
  Avatar,
  Tabs,
  Tab,
  InputAdornment
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  RssFeed as RssIcon,
  Visibility as VisibilityIcon,
  Link as LinkIcon,
  Schedule as ScheduleIcon,
  TrendingUp as TrendingUpIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
  Settings as SettingsIcon,
  Analytics as AnalyticsIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  ExpandMore as ExpandMoreIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  Assessment as AssessmentIcon,
  Timeline as TimelineIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  Category as CategoryIcon,
  Language as LanguageIcon,
  Public as PublicIcon,
  Security as SecurityIcon,
  CloudDownload as CloudDownloadIcon,
  CloudOff as CloudOffIcon,
  Sync as SyncIcon,
  SyncProblem as SyncProblemIcon,
  CheckCircleOutline as CheckCircleOutlineIcon,
  Cancel as CancelIcon,
  Update as UpdateIcon,
  History as HistoryIcon,
  BarChart as BarChartIcon,
  PieChart as PieChartIcon,
  ShowChart as ShowChartIcon
} from '@mui/icons-material';
import { newsSystemService } from '../../services/newsSystemService';

const RSSManagement = () => {
  const [feeds, setFeeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [sortBy, setSortBy] = useState('last_updated');
  const [sortOrder, setSortOrder] = useState('desc');
  const [activeTab, setActiveTab] = useState(0);
  const [selectedFeed, setSelectedFeed] = useState(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showStatsDialog, setShowStatsDialog] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState(null);

  // Form state for add/edit
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    description: '',
    category: '',
    language: 'en',
    update_frequency: '30',
    is_active: true,
    max_articles_per_update: 50,
    tags: [],
    custom_headers: {},
    filters: {
      keywords: [],
      exclude_keywords: [],
      min_length: 100,
      max_length: 10000
    }
  });

  useEffect(() => {
    fetchFeeds();
    fetchStats();
    const interval = setInterval(() => {
      fetchFeeds();
      fetchStats();
    }, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchFeeds = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await newsSystemService.getRSSFeeds();
      setFeeds(response.feeds || []);
    } catch (err) {
      console.error('Error fetching RSS feeds:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await newsSystemService.getRSSStats();
      setStats(response);
    } catch (err) {
      console.error('Error fetching RSS stats:', err);
    }
  };

  const handleAddFeed = async () => {
    try {
      setRefreshing(true);
      await newsSystemService.addRSSFeed(formData);
      setShowAddDialog(false);
      resetForm();
      fetchFeeds();
      fetchStats();
    } catch (err) {
      console.error('Error adding RSS feed:', err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleEditFeed = async () => {
    try {
      setRefreshing(true);
      await newsSystemService.updateRSSFeed(selectedFeed.id, formData);
      setShowEditDialog(false);
      setSelectedFeed(null);
      resetForm();
      fetchFeeds();
      fetchStats();
    } catch (err) {
      console.error('Error updating RSS feed:', err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleDeleteFeed = async (feedId) => {
    if (window.confirm('Are you sure you want to delete this RSS feed?')) {
      try {
        setRefreshing(true);
        await newsSystemService.deleteRSSFeed(feedId);
        fetchFeeds();
        fetchStats();
      } catch (err) {
        console.error('Error deleting RSS feed:', err);
        setError(err.message);
      } finally {
        setRefreshing(false);
      }
    }
  };

  const handleTestFeed = async (feedId) => {
    try {
      setRefreshing(true);
      await newsSystemService.testRSSFeed(feedId);
      fetchFeeds();
    } catch (err) {
      console.error('Error testing RSS feed:', err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRefreshFeed = async (feedId) => {
    try {
      setRefreshing(true);
      await newsSystemService.refreshRSSFeed(feedId);
      fetchFeeds();
      fetchStats();
    } catch (err) {
      console.error('Error refreshing RSS feed:', err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleToggleFeed = async (feedId, isActive) => {
    try {
      setRefreshing(true);
      await newsSystemService.toggleRSSFeed(feedId, isActive);
      fetchFeeds();
      fetchStats();
    } catch (err) {
      console.error('Error toggling RSS feed:', err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      url: '',
      description: '',
      category: '',
      language: 'en',
      update_frequency: '30',
      is_active: true,
      max_articles_per_update: 50,
      tags: [],
      custom_headers: {},
      filters: {
        keywords: [],
        exclude_keywords: [],
        min_length: 100,
        max_length: 10000
      }
    });
  };

  const openEditDialog = (feed) => {
    setSelectedFeed(feed);
    setFormData({
      name: feed.name,
      url: feed.url,
      description: feed.description,
      category: feed.category,
      language: feed.language,
      update_frequency: feed.update_frequency.toString(),
      is_active: feed.is_active,
      max_articles_per_update: feed.max_articles_per_update,
      tags: feed.tags || [],
      custom_headers: feed.custom_headers || {},
      filters: feed.filters || {
        keywords: [],
        exclude_keywords: [],
        min_length: 100,
        max_length: 10000
      }
    });
    setShowEditDialog(true);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active': return <CheckCircleIcon color="success" />;
      case 'error': return <ErrorIcon color="error" />;
      case 'warning': return <WarningIcon color="warning" />;
      case 'inactive': return <CancelIcon color="disabled" />;
      default: return <InfoIcon color="info" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'success';
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'inactive': return 'default';
      default: return 'info';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatFrequency = (minutes) => {
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h`;
    return `${Math.floor(minutes / 1440)}d`;
  };

  const filteredFeeds = feeds.filter(feed => {
    const matchesSearch = !searchQuery || 
      feed.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      feed.url.toLowerCase().includes(searchQuery.toLowerCase()) ||
      feed.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = !filterStatus || feed.status === filterStatus;
    const matchesCategory = !filterCategory || feed.category === filterCategory;
    return matchesSearch && matchesStatus && matchesCategory;
  }).sort((a, b) => {
    const aValue = a[sortBy];
    const bValue = b[sortBy];
    if (sortOrder === 'asc') {
      return aValue > bValue ? 1 : -1;
    } else {
      return aValue < bValue ? 1 : -1;
    }
  });

  const getCategoryStats = () => {
    const stats = {};
    feeds.forEach(feed => {
      stats[feed.category] = (stats[feed.category] || 0) + 1;
    });
    return stats;
  };

  const categoryStats = getCategoryStats();

  if (loading && feeds.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" ml={2}>
          Loading RSS feeds...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            RSS Feed Management
          </Typography>
          <Typography variant="subtitle1" color="textSecondary">
            Manage RSS feeds, monitor collection status, and configure feed settings
          </Typography>
        </Box>
        <Box display="flex" gap={2}>
          <Tooltip title="Refresh All Feeds">
            <IconButton onClick={fetchFeeds} disabled={refreshing}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setShowAddDialog(true)}
          >
            Add Feed
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Stats Overview */}
      {stats && (
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Total Feeds
                    </Typography>
                    <Typography variant="h4">
                      {stats.total_feeds}
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      {stats.active_feeds} active
                    </Typography>
                  </Box>
                  <RssIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Articles Today
                    </Typography>
                    <Typography variant="h4" color="success.main">
                      {stats.articles_today}
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      {stats.articles_this_hour} this hour
                    </Typography>
                  </Box>
                  <ArticleIcon sx={{ fontSize: 40, color: 'success.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Success Rate
                    </Typography>
                    <Typography variant="h4" color="info.main">
                      {stats.success_rate}%
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      Last 24 hours
                    </Typography>
                  </Box>
                  <AssessmentIcon sx={{ fontSize: 40, color: 'info.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Avg Response Time
                    </Typography>
                    <Typography variant="h4" color="warning.main">
                      {stats.avg_response_time}ms
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      Last update
                    </Typography>
                  </Box>
                  <SpeedIcon sx={{ fontSize: 40, color: 'warning.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Feed List" icon={<RssIcon />} />
          <Tab label="Statistics" icon={<BarChartIcon />} />
          <Tab label="Categories" icon={<CategoryIcon />} />
          <Tab label="Health Monitor" icon={<AssessmentIcon />} />
        </Tabs>
      </Box>

      {/* Feed List Tab */}
      {activeTab === 0 && (
        <Box>
          {/* Filters */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Search feeds"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  InputProps={{
                    startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  }}
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Status</InputLabel>
                  <Select
                    value={filterStatus}
                    label="Status"
                    onChange={(e) => setFilterStatus(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="active">Active</MenuItem>
                    <MenuItem value="inactive">Inactive</MenuItem>
                    <MenuItem value="error">Error</MenuItem>
                    <MenuItem value="warning">Warning</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={filterCategory}
                    label="Category"
                    onChange={(e) => setFilterCategory(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    {Object.keys(categoryStats).map(category => (
                      <MenuItem key={category} value={category}>
                        {category}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Sort By</InputLabel>
                  <Select
                    value={sortBy}
                    label="Sort By"
                    onChange={(e) => setSortBy(e.target.value)}
                  >
                    <MenuItem value="name">Name</MenuItem>
                    <MenuItem value="last_updated">Last Updated</MenuItem>
                    <MenuItem value="articles_count">Articles</MenuItem>
                    <MenuItem value="success_rate">Success Rate</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <Button
                  fullWidth
                  variant="contained"
                  startIcon={<FilterIcon />}
                  onClick={fetchFeeds}
                >
                  Filter
                </Button>
              </Grid>
            </Grid>
          </Paper>

          {/* Feeds Table */}
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Feed</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Articles</TableCell>
                  <TableCell>Frequency</TableCell>
                  <TableCell>Last Updated</TableCell>
                  <TableCell>Success Rate</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredFeeds.map((feed) => (
                  <TableRow key={feed.id}>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={2}>
                        <Avatar sx={{ bgcolor: 'primary.main' }}>
                          <RssIcon />
                        </Avatar>
                        <Box>
                          <Typography variant="subtitle2" fontWeight="medium">
                            {feed.name}
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            {feed.url}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        icon={getStatusIcon(feed.status)}
                        label={feed.status}
                        color={getStatusColor(feed.status)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip label={feed.category} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="body2">
                          {feed.articles_count || 0}
                        </Typography>
                        {feed.articles_today > 0 && (
                          <Chip
                            label={`+${feed.articles_today}`}
                            size="small"
                            color="success"
                            variant="outlined"
                          />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <ScheduleIcon fontSize="small" />
                        <Typography variant="body2">
                          {formatFrequency(feed.update_frequency)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {feed.last_updated ? formatDate(feed.last_updated) : 'Never'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <LinearProgress
                          variant="determinate"
                          value={feed.success_rate || 0}
                          color={feed.success_rate >= 90 ? 'success' : feed.success_rate >= 70 ? 'warning' : 'error'}
                          sx={{ width: 60 }}
                        />
                        <Typography variant="body2">
                          {feed.success_rate || 0}%
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" gap={1}>
                        <Tooltip title="View Details">
                          <IconButton size="small" onClick={() => setShowStatsDialog(true)}>
                            <VisibilityIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Edit Feed">
                          <IconButton size="small" onClick={() => openEditDialog(feed)}>
                            <EditIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Test Feed">
                          <IconButton size="small" onClick={() => handleTestFeed(feed.id)}>
                            <PlayIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Refresh Now">
                          <IconButton size="small" onClick={() => handleRefreshFeed(feed.id)}>
                            <SyncIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Feed">
                          <IconButton size="small" onClick={() => handleDeleteFeed(feed.id)} color="error">
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {filteredFeeds.length === 0 && (
            <Box textAlign="center" py={4}>
              <RssIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="textSecondary">
                No RSS feeds found
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Add your first RSS feed to start collecting news articles
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Statistics Tab */}
      {activeTab === 1 && stats && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Feed Performance" />
                <CardContent>
                  <List>
                    <ListItem>
                      <ListItemIcon>
                        <TrendingUpIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Most Active Feed"
                        secondary={`${stats.most_active_feed?.name || 'N/A'} (${stats.most_active_feed?.articles_today || 0} articles today)`}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <SpeedIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Fastest Response"
                        secondary={`${stats.fastest_feed?.name || 'N/A'} (${stats.fastest_feed?.avg_response_time || 0}ms)`}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <AssessmentIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Most Reliable"
                        secondary={`${stats.most_reliable_feed?.name || 'N/A'} (${stats.most_reliable_feed?.success_rate || 0}% success)`}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Collection Trends" />
                <CardContent>
                  <List>
                    <ListItem>
                      <ListItemText
                        primary="Articles Last 24h"
                        secondary={stats.articles_last_24h || 0}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Articles Last 7d"
                        secondary={stats.articles_last_7d || 0}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Average per Feed"
                        secondary={stats.avg_articles_per_feed || 0}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Categories Tab */}
      {activeTab === 2 && (
        <Box>
          <Grid container spacing={3}>
            {Object.entries(categoryStats).map(([category, count]) => (
              <Grid item xs={12} sm={6} md={4} key={category}>
                <Card>
                  <CardContent>
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                      <Box>
                        <Typography variant="h6">{category}</Typography>
                        <Typography color="textSecondary">
                          {count} feeds
                        </Typography>
                      </Box>
                      <CategoryIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Health Monitor Tab */}
      {activeTab === 3 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Feed Health Status" />
                <CardContent>
                  <List>
                    {feeds.filter(f => f.status === 'error').map(feed => (
                      <ListItem key={feed.id}>
                        <ListItemIcon>
                          <ErrorIcon color="error" />
                        </ListItemIcon>
                        <ListItemText
                          primary={feed.name}
                          secondary={`Last error: ${feed.last_error || 'Unknown'}`}
                        />
                      </ListItem>
                    ))}
                    {feeds.filter(f => f.status === 'warning').map(feed => (
                      <ListItem key={feed.id}>
                        <ListItemIcon>
                          <WarningIcon color="warning" />
                        </ListItemIcon>
                        <ListItemText
                          primary={feed.name}
                          secondary={`Warning: ${feed.warning_message || 'Performance issue'}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="System Health" />
                <CardContent>
                  <Box display="flex" flexDirection="column" gap={2}>
                    <Box>
                      <Box display="flex" justifyContent="space-between" mb={1}>
                        <Typography variant="body2">Overall Health</Typography>
                        <Typography variant="body2">{stats?.overall_health || 0}%</Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={stats?.overall_health || 0}
                        color={stats?.overall_health >= 90 ? 'success' : stats?.overall_health >= 70 ? 'warning' : 'error'}
                      />
                    </Box>
                    <Box>
                      <Box display="flex" justifyContent="space-between" mb={1}>
                        <Typography variant="body2">Active Feeds</Typography>
                        <Typography variant="body2">{stats?.active_feeds || 0}/{stats?.total_feeds || 0}</Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={((stats?.active_feeds || 0) / (stats?.total_feeds || 1)) * 100}
                        color="success"
                      />
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Add Feed Dialog */}
      <Dialog open={showAddDialog} onClose={() => setShowAddDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Add New RSS Feed</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Feed Name"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              fullWidth
              required
            />
            <TextField
              label="Feed URL"
              value={formData.url}
              onChange={(e) => setFormData({...formData, url: e.target.value})}
              fullWidth
              required
              placeholder="https://example.com/rss"
            />
            <TextField
              label="Description"
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              fullWidth
              multiline
              rows={2}
            />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={formData.category}
                    label="Category"
                    onChange={(e) => setFormData({...formData, category: e.target.value})}
                  >
                    <MenuItem value="news">News</MenuItem>
                    <MenuItem value="technology">Technology</MenuItem>
                    <MenuItem value="business">Business</MenuItem>
                    <MenuItem value="politics">Politics</MenuItem>
                    <MenuItem value="sports">Sports</MenuItem>
                    <MenuItem value="entertainment">Entertainment</MenuItem>
                    <MenuItem value="science">Science</MenuItem>
                    <MenuItem value="health">Health</MenuItem>
                    <MenuItem value="other">Other</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Language</InputLabel>
                  <Select
                    value={formData.language}
                    label="Language"
                    onChange={(e) => setFormData({...formData, language: e.target.value})}
                  >
                    <MenuItem value="en">English</MenuItem>
                    <MenuItem value="es">Spanish</MenuItem>
                    <MenuItem value="fr">French</MenuItem>
                    <MenuItem value="de">German</MenuItem>
                    <MenuItem value="it">Italian</MenuItem>
                    <MenuItem value="pt">Portuguese</MenuItem>
                    <MenuItem value="ru">Russian</MenuItem>
                    <MenuItem value="zh">Chinese</MenuItem>
                    <MenuItem value="ja">Japanese</MenuItem>
                    <MenuItem value="ko">Korean</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Update Frequency (minutes)</InputLabel>
                  <Select
                    value={formData.update_frequency}
                    label="Update Frequency (minutes)"
                    onChange={(e) => setFormData({...formData, update_frequency: e.target.value})}
                  >
                    <MenuItem value="15">15 minutes</MenuItem>
                    <MenuItem value="30">30 minutes</MenuItem>
                    <MenuItem value="60">1 hour</MenuItem>
                    <MenuItem value="120">2 hours</MenuItem>
                    <MenuItem value="240">4 hours</MenuItem>
                    <MenuItem value="480">8 hours</MenuItem>
                    <MenuItem value="720">12 hours</MenuItem>
                    <MenuItem value="1440">24 hours</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Max Articles per Update"
                  type="number"
                  value={formData.max_articles_per_update}
                  onChange={(e) => setFormData({...formData, max_articles_per_update: parseInt(e.target.value)})}
                  fullWidth
                />
              </Grid>
            </Grid>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                />
              }
              label="Active"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAddFeed} variant="contained" disabled={refreshing}>
            {refreshing ? <CircularProgress size={20} /> : 'Add Feed'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Feed Dialog */}
      <Dialog open={showEditDialog} onClose={() => setShowEditDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Edit RSS Feed</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Feed Name"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              fullWidth
              required
            />
            <TextField
              label="Feed URL"
              value={formData.url}
              onChange={(e) => setFormData({...formData, url: e.target.value})}
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              fullWidth
              multiline
              rows={2}
            />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={formData.category}
                    label="Category"
                    onChange={(e) => setFormData({...formData, category: e.target.value})}
                  >
                    <MenuItem value="news">News</MenuItem>
                    <MenuItem value="technology">Technology</MenuItem>
                    <MenuItem value="business">Business</MenuItem>
                    <MenuItem value="politics">Politics</MenuItem>
                    <MenuItem value="sports">Sports</MenuItem>
                    <MenuItem value="entertainment">Entertainment</MenuItem>
                    <MenuItem value="science">Science</MenuItem>
                    <MenuItem value="health">Health</MenuItem>
                    <MenuItem value="other">Other</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Language</InputLabel>
                  <Select
                    value={formData.language}
                    label="Language"
                    onChange={(e) => setFormData({...formData, language: e.target.value})}
                  >
                    <MenuItem value="en">English</MenuItem>
                    <MenuItem value="es">Spanish</MenuItem>
                    <MenuItem value="fr">French</MenuItem>
                    <MenuItem value="de">German</MenuItem>
                    <MenuItem value="it">Italian</MenuItem>
                    <MenuItem value="pt">Portuguese</MenuItem>
                    <MenuItem value="ru">Russian</MenuItem>
                    <MenuItem value="zh">Chinese</MenuItem>
                    <MenuItem value="ja">Japanese</MenuItem>
                    <MenuItem value="ko">Korean</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Update Frequency (minutes)</InputLabel>
                  <Select
                    value={formData.update_frequency}
                    label="Update Frequency (minutes)"
                    onChange={(e) => setFormData({...formData, update_frequency: e.target.value})}
                  >
                    <MenuItem value="15">15 minutes</MenuItem>
                    <MenuItem value="30">30 minutes</MenuItem>
                    <MenuItem value="60">1 hour</MenuItem>
                    <MenuItem value="120">2 hours</MenuItem>
                    <MenuItem value="240">4 hours</MenuItem>
                    <MenuItem value="480">8 hours</MenuItem>
                    <MenuItem value="720">12 hours</MenuItem>
                    <MenuItem value="1440">24 hours</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Max Articles per Update"
                  type="number"
                  value={formData.max_articles_per_update}
                  onChange={(e) => setFormData({...formData, max_articles_per_update: parseInt(e.target.value)})}
                  fullWidth
                />
              </Grid>
            </Grid>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                />
              }
              label="Active"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowEditDialog(false)}>Cancel</Button>
          <Button onClick={handleEditFeed} variant="contained" disabled={refreshing}>
            {refreshing ? <CircularProgress size={20} /> : 'Update Feed'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RSSManagement;
