import {
  RssFeed as RssFeedIcon,
  Add,
  Refresh,
  Settings as SettingsIcon,
  Delete,
  Edit,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Schedule,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  FilterList,
  Search,
  Download as DownloadIcon,
  Upload as UploadIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  CircularProgress,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Tooltip,
  Badge,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../../services/apiService.ts';

const RSSFeeds = () => {
  const [feeds, setFeeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalFeeds, setTotalFeeds] = useState(0);
  const [categories, setCategories] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    inactive: 0,
    error: 0,
    lastUpdate: null,
  });
  const [selectedFeed, setSelectedFeed] = useState(null);
  const [feedDialogOpen, setFeedDialogOpen] = useState(false);
  const [newFeed, setNewFeed] = useState({
    name: '',
    url: '',
    category: '',
    updateInterval: 30,
    isActive: true,
    description: '',
  });

  const fetchFeeds = useCallback(async() => {
    try {
      setLoading(true);

      const params = {
        page,
        limit: 20,
        search: searchTerm || undefined,
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
        sort_by: sortBy,
      };

      const response = await apiService.rssFeeds.getFeeds(params);

      if (response.success) {
        setFeeds(response.data.feeds || []);
        setTotalPages(response.data.total_pages || 1);
        setTotalFeeds(response.data.total_count || 0);

        // Calculate statistics
        const feeds = response.data.feeds || [];
        const stats = {
          total: feeds.length,
          active: feeds.filter(f => f.is_active).length,
          inactive: feeds.filter(f => !f.is_active).length,
          error: feeds.filter(f => f.last_error).length,
          lastUpdate: feeds.reduce((latest, feed) => {
            const feedTime = new Date(feed.last_fetched_at || 0);
            return feedTime > latest ? feedTime : latest;
          }, new Date(0)),
        };
        setStats(stats);
      }
    } catch (error) {
      console.error('Error fetching feeds:', error);
    } finally {
      setLoading(false);
    }
  }, [page, searchTerm, statusFilter, categoryFilter, sortBy]);

  const fetchCategories = useCallback(async() => {
    try {
      const response = await apiService.rssFeeds.getCategories();
      if (response.success) {
        setCategories(response.data.categories || []);
      }
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  }, []);

  useEffect(() => {
    fetchFeeds();
  }, [fetchFeeds]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const getStatusColor = (feed) => {
    if (!feed.is_active) return 'default';
    if (feed.last_error) return 'error';
    if (feed.last_fetched_at) {
      const lastFetch = new Date(feed.last_fetched_at);
      const now = new Date();
      const hoursSinceFetch = (now - lastFetch) / (1000 * 60 * 60);
      if (hoursSinceFetch > 24) return 'warning';
    }
    return 'success';
  };

  const getStatusLabel = (feed) => {
    if (!feed.is_active) return 'Inactive';
    if (feed.last_error) return 'Error';
    if (feed.last_fetched_at) {
      const lastFetch = new Date(feed.last_fetched_at);
      const now = new Date();
      const hoursSinceFetch = (now - lastFetch) / (1000 * 60 * 60);
      if (hoursSinceFetch > 24) return 'Stale';
    }
    return 'Active';
  };

  const getStatusIcon = (feed) => {
    if (!feed.is_active) return <PauseIcon />;
    if (feed.last_error) return <ErrorIcon />;
    return <CheckCircleIcon />;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleAddFeed = async() => {
    try {
      const response = await apiService.rssFeeds.createFeed(newFeed);
      if (response.success) {
        setFeedDialogOpen(false);
        setNewFeed({
          name: '',
          url: '',
          category: '',
          updateInterval: 30,
          isActive: true,
          description: '',
        });
        fetchFeeds();
      }
    } catch (error) {
      console.error('Error creating feed:', error);
    }
  };

  const handleToggleFeed = async(feedId, isActive) => {
    try {
      const response = await apiService.rssFeeds.updateFeed(feedId, { is_active: !isActive });
      if (response.success) {
        fetchFeeds();
      }
    } catch (error) {
      console.error('Error toggling feed:', error);
    }
  };

  const handleDeleteFeed = async(feedId) => {
    try {
      const response = await apiService.rssFeeds.deleteFeed(feedId);
      if (response.success) {
        fetchFeeds();
      }
    } catch (error) {
      console.error('Error deleting feed:', error);
    }
  };

  const handleRefreshFeed = async(feedId) => {
    try {
      const response = await apiService.rssFeeds.refreshFeed(feedId);
      if (response.success) {
        fetchFeeds();
      }
    } catch (error) {
      console.error('Error refreshing feed:', error);
    }
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          📡 RSS Feeds Management
        </Typography>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={() => fetchFeeds()}
            disabled={loading}
          >
            Refresh All
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => setFeedDialogOpen(true)}
          >
            Add Feed
          </Button>
        </Box>
      </Box>

      {/* Statistics Overview */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="primary">
                {stats.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Feeds
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="success">
                {stats.active}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="default">
                {stats.inactive}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Inactive
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="error">
                {stats.error}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Errors
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="info">
                {stats.total > 0 ? Math.round((stats.active / stats.total) * 100) : 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="primary">
                {stats.lastUpdate ? formatDate(stats.lastUpdate) : 'Never'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Last Update
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              placeholder="Search feeds..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                label="Status"
              >
                <MenuItem value="">All Status</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
                <MenuItem value="error">Error</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                label="Category"
              >
                <MenuItem value="">All Categories</MenuItem>
                {categories.map((category) => (
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
                onChange={(e) => setSortBy(e.target.value)}
                label="Sort By"
              >
                <MenuItem value="name">Name</MenuItem>
                <MenuItem value="last_fetched_at">Last Update</MenuItem>
                <MenuItem value="created_at">Created Date</MenuItem>
                <MenuItem value="article_count">Article Count</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              variant="contained"
              startIcon={<FilterList />}
              onClick={() => fetchFeeds()}
              disabled={loading}
              fullWidth
            >
              Filter
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Feeds List */}
      {loading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={2}>
          {feeds.map((feed) => (
            <Grid item xs={12} key={feed.id}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Box flex={1}>
                      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
                        {feed.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {feed.description || feed.url}
                      </Typography>
                      <Box display="flex" alignItems="center" gap={1} mb={1}>
                        <Chip
                          icon={<Schedule />}
                          label={`${feed.update_interval || 30}min interval`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          icon={<RssFeedIcon />}
                          label={`${feed.article_count || 0} articles`}
                          size="small"
                          variant="outlined"
                        />
                        {feed.category && (
                          <Chip
                            label={feed.category}
                            size="small"
                            color="primary"
                          />
                        )}
                      </Box>
                    </Box>
                    <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
                      {/* Status */}
                      <Chip
                        icon={getStatusIcon(feed)}
                        label={getStatusLabel(feed)}
                        color={getStatusColor(feed)}
                        size="small"
                      />

                      {/* Last Update */}
                      <Typography variant="caption" color="text.secondary">
                        Last: {formatDate(feed.last_fetched_at)}
                      </Typography>

                      {/* Action Buttons */}
                      <Box display="flex" gap={1}>
                        <Tooltip title="Refresh Feed">
                          <IconButton
                            size="small"
                            onClick={() => handleRefreshFeed(feed.id)}
                          >
                            <Refresh />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={feed.is_active ? 'Pause Feed' : 'Activate Feed'}>
                          <IconButton
                            size="small"
                            onClick={() => handleToggleFeed(feed.id, feed.is_active)}
                          >
                            {feed.is_active ? <PauseIcon /> : <PlayIcon />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Edit Feed">
                          <IconButton
                            size="small"
                            onClick={() => {
                              setSelectedFeed(feed);
                              setFeedDialogOpen(true);
                            }}
                          >
                            <Edit />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Feed">
                          <IconButton
                            size="small"
                            onClick={() => handleDeleteFeed(feed.id)}
                            color="error"
                          >
                            <Delete />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </Box>
                  </Box>

                  {/* Error Display */}
                  {feed.last_error && (
                    <Box mt={2}>
                      <Paper sx={{ p: 1, bgcolor: 'error.light', color: 'error.contrastText' }}>
                        <Typography variant="caption">
                          <strong>Error:</strong> {feed.last_error}
                        </Typography>
                      </Paper>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Add/Edit Feed Dialog */}
      <Dialog
        open={feedDialogOpen}
        onClose={() => setFeedDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {selectedFeed ? 'Edit RSS Feed' : 'Add New RSS Feed'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              fullWidth
              label="Feed Name"
              value={selectedFeed ? selectedFeed.name : newFeed.name}
              onChange={(e) => {
                if (selectedFeed) {
                  setSelectedFeed({ ...selectedFeed, name: e.target.value });
                } else {
                  setNewFeed({ ...newFeed, name: e.target.value });
                }
              }}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Feed URL"
              value={selectedFeed ? selectedFeed.url : newFeed.url}
              onChange={(e) => {
                if (selectedFeed) {
                  setSelectedFeed({ ...selectedFeed, url: e.target.value });
                } else {
                  setNewFeed({ ...newFeed, url: e.target.value });
                }
              }}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Description"
              value={selectedFeed ? selectedFeed.description : newFeed.description}
              onChange={(e) => {
                if (selectedFeed) {
                  setSelectedFeed({ ...selectedFeed, description: e.target.value });
                } else {
                  setNewFeed({ ...newFeed, description: e.target.value });
                }
              }}
              sx={{ mb: 2 }}
            />
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Category</InputLabel>
              <Select
                value={selectedFeed ? selectedFeed.category : newFeed.category}
                onChange={(e) => {
                  if (selectedFeed) {
                    setSelectedFeed({ ...selectedFeed, category: e.target.value });
                  } else {
                    setNewFeed({ ...newFeed, category: e.target.value });
                  }
                }}
                label="Category"
              >
                {categories.map((category) => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label="Update Interval (minutes)"
              type="number"
              value={selectedFeed ? selectedFeed.update_interval : newFeed.updateInterval}
              onChange={(e) => {
                if (selectedFeed) {
                  setSelectedFeed({ ...selectedFeed, update_interval: parseInt(e.target.value) });
                } else {
                  setNewFeed({ ...newFeed, updateInterval: parseInt(e.target.value) });
                }
              }}
              sx={{ mb: 2 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={selectedFeed ? selectedFeed.is_active : newFeed.isActive}
                  onChange={(e) => {
                    if (selectedFeed) {
                      setSelectedFeed({ ...selectedFeed, is_active: e.target.checked });
                    } else {
                      setNewFeed({ ...newFeed, isActive: e.target.checked });
                    }
                  }}
                />
              }
              label="Active"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFeedDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleAddFeed}
          >
            {selectedFeed ? 'Update' : 'Add'} Feed
          </Button>
        </DialogActions>
      </Dialog>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box display="flex" justifyContent="center" mt={3}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(event, value) => setPage(value)}
            color="primary"
          />
        </Box>
      )}

      {/* Results Summary */}
      <Box mt={2}>
        <Typography variant="body2" color="text.secondary">
          Showing {feeds.length} of {totalFeeds} feeds
        </Typography>
      </Box>
    </Box>
  );
};

export default RSSFeeds;
