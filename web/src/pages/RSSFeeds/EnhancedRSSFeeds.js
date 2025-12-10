import {
  Search,
  FilterList,
  Refresh,
  RssFeed as RssFeedIcon,
  Add,
  Edit,
  Delete,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Schedule,
  Visibility,
  Settings as SettingsIcon,
  ExpandMore,
  Link as LinkIcon,
  Update as UpdateIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  NetworkCheck as NetworkIcon,
  ViewModule,
  ViewList,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  Chip,
  LinearProgress,
  Button,
  IconButton,
  Tooltip,
  Alert,
  CircularProgress,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Badge,
  Avatar,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';

import { apiService } from '../../services/apiService';
import { useDomainRoute } from '../../hooks/useDomainRoute';

const EnhancedRSSFeeds = () => {
  const { domain } = useDomainRoute();
  const [feeds, setFeeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [viewMode, setViewMode] = useState('grid');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedFeed, setSelectedFeed] = useState(null);
  const [newFeed, setNewFeed] = useState({
    name: '',
    url: '',
    category: '',
    description: '',
    enabled: true,
    update_frequency: 30,
  });

  const loadFeeds = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getRSSFeeds({
        page,
        limit: 12,
        search: searchQuery,
        status: filterStatus,
        category: filterCategory,
        sort: sortBy,
      }, domain);

      if (response.success) {
        const items = (response.data.feeds || []).map(f => ({
          id: f.id,
          name: f.feed_name || f.name,
          url: f.feed_url || f.url,
          status: f.is_active ? 'active' : 'disabled',
          enabled: !!f.is_active,
          update_frequency: f.fetch_interval_seconds
            ? Math.round(f.fetch_interval_seconds / 60)
            : undefined,
          last_update: f.last_fetched_at || f.last_update || null,
          category: f.category,
          description: f.description,
          article_count: f.article_count,
        }));
        setFeeds(items);
        setTotalPages(Math.ceil((response.data.total || items.length) / 12));
      } else {
        setFeeds([]);
        setTotalPages(1);
      }
    } catch (err) {
      console.error('Error loading RSS feeds:', err);
      setError('Failed to load RSS feeds');
      setFeeds([]);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, filterStatus, filterCategory, sortBy]);

  useEffect(() => {
    loadFeeds();
  }, [loadFeeds]);

  const handleSearch = event => {
    setSearchQuery(event.target.value);
    setPage(1);
  };

  const handleFilterChange = (filterType, value) => {
    switch (filterType) {
    case 'status':
      setFilterStatus(value);
      break;
    case 'category':
      setFilterCategory(value);
      break;
    case 'sort':
      setSortBy(value);
      break;
    default:
      console.warn('Unknown filter type:', filterType);
      break;
    }
    setPage(1);
  };

  const handleRefresh = async() => {
    try {
      setLoading(true);
      setError(null);

      // Call the RSS update API
      const result = await apiService.updateRSSFeeds();

      if (result.success) {
        // Show success message
        console.log('RSS feeds updated:', result.message);

        // Reload the feeds list to show updated data
        await loadFeeds();
      } else {
        setError('Failed to update RSS feeds');
      }
    } catch (err) {
      console.error('Error updating RSS feeds:', err);
      setError('Failed to update RSS feeds: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddFeed = () => {
    setNewFeed({
      name: '',
      url: '',
      category: '',
      description: '',
      enabled: true,
      update_frequency: 30,
    });
    setAddDialogOpen(true);
  };

  const handleEditFeed = feed => {
    setSelectedFeed(feed);
    setNewFeed({
      name: feed.name || '',
      url: feed.url || '',
      category: feed.category || '',
      description: feed.description || '',
      enabled: feed.enabled !== false,
      update_frequency: feed.update_frequency || 30,
    });
    setEditDialogOpen(true);
  };

  const handleSaveFeed = async() => {
    try {
      // Here you would call the API to save the feed
      console.log('Saving feed:', newFeed);
      setAddDialogOpen(false);
      setEditDialogOpen(false);
      loadFeeds();
    } catch (err) {
      console.error('Error saving feed:', err);
    }
  };

  const handleDeleteFeed = async feedId => {
    if (window.confirm('Are you sure you want to delete this RSS feed?')) {
      try {
        // Here you would call the API to delete the feed
        console.log('Deleting feed:', feedId);
        loadFeeds();
      } catch (err) {
        console.error('Error deleting feed:', err);
      }
    }
  };

  const handleToggleFeed = async(feedId, enabled) => {
    try {
      // Here you would call the API to toggle the feed status
      console.log('Toggling feed:', feedId, enabled);
      loadFeeds();
    } catch (err) {
      console.error('Error toggling feed:', err);
    }
  };

  const getStatusColor = status => {
    switch (status?.toLowerCase()) {
    case 'active':
      return 'success';
    case 'error':
      return 'error';
    case 'paused':
      return 'warning';
    case 'disabled':
      return 'default';
    default:
      return 'default';
    }
  };

  const getStatusIcon = status => {
    switch (status?.toLowerCase()) {
    case 'active':
      return <CheckCircleIcon />;
    case 'error':
      return <ErrorIcon />;
    case 'paused':
      return <PauseIcon />;
    case 'disabled':
      return <PauseIcon />;
    default:
      return <WarningIcon />;
    }
  };

  const getCategoryIcon = category => {
    switch (category?.toLowerCase()) {
    case 'news':
      return <RssFeedIcon />;
    case 'politics':
      return <LinkIcon />;
    case 'business':
      return <LinkIcon />;
    case 'technology':
      return <LinkIcon />;
    case 'health':
      return <LinkIcon />;
    case 'sports':
      return <LinkIcon />;
    default:
      return <RssFeedIcon />;
    }
  };

  const formatDate = dateString => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateText = (text, maxLength = 100) => {
    if (!text) return '';
    return text.length > maxLength
      ? text.substring(0, maxLength) + '...'
      : text;
  };

  const FeedCard = ({ feed }) => (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box
          display='flex'
          justifyContent='space-between'
          alignItems='flex-start'
          mb={2}
        >
          <Typography
            variant='h6'
            component='h3'
            sx={{
              fontWeight: 'bold',
              lineHeight: 1.2,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {feed.name || 'Unnamed Feed'}
          </Typography>
          <Box display='flex' gap={1}>
            <IconButton
              size='small'
              onClick={() => handleToggleFeed(feed.id, !feed.enabled)}
            >
              {feed.enabled ? <PauseIcon /> : <PlayIcon />}
            </IconButton>
            <IconButton size='small' onClick={() => handleEditFeed(feed)}>
              <Edit />
            </IconButton>
            <IconButton
              size='small'
              onClick={() => handleDeleteFeed(feed.id)}
              color='error'
            >
              <Delete />
            </IconButton>
          </Box>
        </Box>

        <Typography
          variant='body2'
          color='text.secondary'
          sx={{
            mb: 2,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {truncateText(feed.description || feed.url)}
        </Typography>

        <Box display='flex' flexWrap='wrap' gap={1} mb={2}>
          <Chip
            icon={getStatusIcon(feed.status)}
            label={feed.status || 'Unknown'}
            color={getStatusColor(feed.status)}
            size='small'
          />
          {feed.category && (
            <Chip
              icon={getCategoryIcon(feed.category)}
              label={feed.category}
              color='secondary'
              size='small'
            />
          )}
          {feed.update_frequency && (
            <Chip
              label={`${feed.update_frequency}m`}
              color='primary'
              size='small'
            />
          )}
        </Box>

        <Box
          display='flex'
          alignItems='center'
          justifyContent='space-between'
          mb={1}
        >
          <Box display='flex' alignItems='center' gap={1}>
            <RssFeedIcon fontSize='small' color='action' />
            <Typography variant='caption' color='text.secondary'>
              {feed.article_count || 0} articles
            </Typography>
          </Box>
          <Typography variant='caption' color='text.secondary'>
            Last: {formatDate(feed.last_update)}
          </Typography>
        </Box>

        {feed.url && (
          <Box mt={1}>
            <Typography
              variant='caption'
              color='text.secondary'
              display='block'
            >
              URL: {truncateText(feed.url, 50)}
            </Typography>
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button
          size='small'
          startIcon={<Visibility />}
          onClick={() => window.open(feed.url, '_blank')}
        >
          View Feed
        </Button>
        <Button
          size='small'
          startIcon={<UpdateIcon />}
          onClick={() => handleRefresh()}
        >
          Update Now
        </Button>
        <Button size='small' startIcon={<SettingsIcon />}>
          Settings
        </Button>
      </CardActions>
    </Card>
  );

  const FeedListItem = ({ feed }) => (
    <ListItem
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        mb: 1,
        bgcolor: 'background.paper',
      }}
    >
      <ListItemText
        primary={
          <Box display='flex' alignItems='center' gap={1} mb={1}>
            <Typography variant='h6' sx={{ flexGrow: 1 }}>
              {feed.name || 'Unnamed Feed'}
            </Typography>
            <Box display='flex' gap={1}>
              <Chip
                icon={getStatusIcon(feed.status)}
                label={feed.status || 'Unknown'}
                color={getStatusColor(feed.status)}
                size='small'
              />
              {feed.category && (
                <Chip
                  icon={getCategoryIcon(feed.category)}
                  label={feed.category}
                  color='secondary'
                  size='small'
                />
              )}
              {feed.update_frequency && (
                <Chip
                  label={`${feed.update_frequency}m`}
                  color='primary'
                  size='small'
                />
              )}
            </Box>
          </Box>
        }
        secondary={
          <Box>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
              {truncateText(feed.description || feed.url, 200)}
            </Typography>
            <Box display='flex' alignItems='center' gap={2}>
              <Box display='flex' alignItems='center' gap={0.5}>
                <RssFeedIcon fontSize='small' />
                <Typography variant='caption'>
                  {feed.article_count || 0} articles
                </Typography>
              </Box>
              <Typography variant='caption'>
                Last update: {formatDate(feed.last_update)}
              </Typography>
              {feed.url && (
                <Typography variant='caption' color='text.secondary'>
                  URL: {truncateText(feed.url, 50)}
                </Typography>
              )}
            </Box>
          </Box>
        }
      />
      <ListItemSecondaryAction>
        <Box display='flex' gap={1}>
          <IconButton
            size='small'
            onClick={() => handleToggleFeed(feed.id, !feed.enabled)}
          >
            {feed.enabled ? <PauseIcon /> : <PlayIcon />}
          </IconButton>
          <IconButton size='small' onClick={() => handleEditFeed(feed)}>
            <Edit />
          </IconButton>
          <IconButton
            size='small'
            onClick={() => handleDeleteFeed(feed.id)}
            color='error'
          >
            <Delete />
          </IconButton>
        </Box>
      </ListItemSecondaryAction>
    </ListItem>
  );

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
          RSS Feeds
        </Typography>
        <Box display='flex' gap={2} alignItems='center'>
          <Button
            variant='contained'
            startIcon={<Add />}
            onClick={handleAddFeed}
          >
            Add Feed
          </Button>
          <Tooltip title='Refresh Feeds'>
            <IconButton onClick={handleRefresh} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button
            variant={viewMode === 'grid' ? 'contained' : 'outlined'}
            startIcon={<ViewModule />}
            onClick={() => setViewMode('grid')}
            size='small'
          >
            Grid
          </Button>
          <Button
            variant={viewMode === 'list' ? 'contained' : 'outlined'}
            startIcon={<ViewList />}
            onClick={() => setViewMode('list')}
            size='small'
          >
            List
          </Button>
        </Box>
      </Box>

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems='center'>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder='Search RSS feeds by name or URL...'
              value={searchQuery}
              onChange={handleSearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position='start'>
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
                value={filterStatus}
                label='Status'
                onChange={e => handleFilterChange('status', e.target.value)}
              >
                <MenuItem value=''>All Statuses</MenuItem>
                <MenuItem value='active'>Active</MenuItem>
                <MenuItem value='error'>Error</MenuItem>
                <MenuItem value='paused'>Paused</MenuItem>
                <MenuItem value='disabled'>Disabled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={filterCategory}
                label='Category'
                onChange={e => handleFilterChange('category', e.target.value)}
              >
                <MenuItem value=''>All Categories</MenuItem>
                <MenuItem value='news'>News</MenuItem>
                <MenuItem value='politics'>Politics</MenuItem>
                <MenuItem value='business'>Business</MenuItem>
                <MenuItem value='technology'>Technology</MenuItem>
                <MenuItem value='health'>Health</MenuItem>
                <MenuItem value='sports'>Sports</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label='Sort By'
                onChange={e => handleFilterChange('sort', e.target.value)}
              >
                <MenuItem value='name'>Name</MenuItem>
                <MenuItem value='last_update'>Last Update</MenuItem>
                <MenuItem value='article_count'>Article Count</MenuItem>
                <MenuItem value='status'>Status</MenuItem>
                <MenuItem value='created_at'>Created Date</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant='outlined'
              startIcon={<FilterList />}
              onClick={() => {
                setSearchQuery('');
                setFilterStatus('');
                setFilterCategory('');
                setSortBy('name');
                setPage(1);
              }}
            >
              Clear Filters
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Feeds Display */}
      {feeds.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <RssFeedIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant='h6' color='text.secondary' gutterBottom>
            No RSS feeds found
          </Typography>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 3 }}>
            {searchQuery || filterStatus || filterCategory
              ? 'Try adjusting your search criteria or filters'
              : 'Add your first RSS feed to start collecting news articles'}
          </Typography>
          <Button
            variant='contained'
            startIcon={<Add />}
            onClick={handleAddFeed}
          >
            Add Your First Feed
          </Button>
        </Paper>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {feeds.map(feed => (
                <Grid item xs={12} sm={6} md={4} key={feed.id}>
                  <FeedCard feed={feed} />
                </Grid>
              ))}
            </Grid>
          ) : (
            <List>
              {feeds.map(feed => (
                <FeedListItem key={feed.id} feed={feed} />
              ))}
            </List>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Box display='flex' justifyContent='center' mt={4}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(event, value) => setPage(value)}
                color='primary'
                size='large'
              />
            </Box>
          )}
        </>
      )}

      {/* Add/Edit Feed Dialog */}
      <Dialog
        open={addDialogOpen || editDialogOpen}
        onClose={() => {
          setAddDialogOpen(false);
          setEditDialogOpen(false);
        }}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>
          {addDialogOpen ? 'Add New RSS Feed' : 'Edit RSS Feed'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label='Feed Name'
                value={newFeed.name}
                onChange={e => setNewFeed({ ...newFeed, name: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label='Feed URL'
                value={newFeed.url}
                onChange={e => setNewFeed({ ...newFeed, url: e.target.value })}
                placeholder='https://feeds.bbci.co.uk/news/rss.xml'
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={newFeed.category}
                  label='Category'
                  onChange={e =>
                    setNewFeed({ ...newFeed, category: e.target.value })
                  }
                >
                  <MenuItem value='news'>News</MenuItem>
                  <MenuItem value='politics'>Politics</MenuItem>
                  <MenuItem value='business'>Business</MenuItem>
                  <MenuItem value='technology'>Technology</MenuItem>
                  <MenuItem value='health'>Health</MenuItem>
                  <MenuItem value='sports'>Sports</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label='Update Frequency (minutes)'
                type='number'
                value={newFeed.update_frequency}
                onChange={e =>
                  setNewFeed({
                    ...newFeed,
                    update_frequency: parseInt(e.target.value),
                  })
                }
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label='Description'
                multiline
                rows={3}
                value={newFeed.description}
                onChange={e =>
                  setNewFeed({ ...newFeed, description: e.target.value })
                }
              />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={newFeed.enabled}
                    onChange={e =>
                      setNewFeed({ ...newFeed, enabled: e.target.checked })
                    }
                  />
                }
                label='Enable this feed'
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setAddDialogOpen(false);
              setEditDialogOpen(false);
            }}
          >
            Cancel
          </Button>
          <Button onClick={handleSaveFeed} variant='contained'>
            {addDialogOpen ? 'Add Feed' : 'Save Changes'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* RSS Management Features */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant='h6' gutterBottom>
          <RssFeedIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          RSS Feed Management Features
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <SpeedIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Automated Collection</Typography>
              <Typography variant='body2' color='text.secondary'>
                Automatic RSS feed monitoring and article collection
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <NetworkIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Health Monitoring</Typography>
              <Typography variant='body2' color='text.secondary'>
                Real-time feed health monitoring and error detection
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <MemoryIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Smart Caching</Typography>
              <Typography variant='body2' color='text.secondary'>
                Intelligent caching and deduplication of articles
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default EnhancedRSSFeeds;
