import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Chip,
  IconButton,
  Tooltip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Science as TestIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import { apiService, RSSFeed } from '../../services/apiService';

interface RSSFeedsState {
  feeds: RSSFeed[];
  loading: boolean;
  error: string | null;
  dialogOpen: boolean;
  editingFeed: RSSFeed | null;
  newFeed: Partial<RSSFeed>;
}

const RSSFeeds: React.FC = () => {
  const [state, setState] = useState<RSSFeedsState>({
    feeds: [],
    loading: true,
    error: null,
    dialogOpen: false,
    editingFeed: null,
    newFeed: {
      name: '',
      url: '',
      description: '',
      category: '',
      is_active: true
    }
  });

  useEffect(() => {
    loadFeeds();
  }, []);

  const loadFeeds = async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      const response = await apiService.getRSSFeeds();
      setState(prev => ({
        ...prev,
        feeds: response.data,
        loading: false
      }));
    } catch (error) {
      console.error('Error loading RSS feeds:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load RSS feeds'
      }));
    }
  };

  const handleCreateFeed = () => {
    setState(prev => ({
      ...prev,
      dialogOpen: true,
      editingFeed: null,
      newFeed: {
        name: '',
        url: '',
        description: '',
        category: '',
        is_active: true
      }
    }));
  };

  const handleEditFeed = (feed: RSSFeed) => {
    setState(prev => ({
      ...prev,
      dialogOpen: true,
      editingFeed: feed,
      newFeed: { ...feed }
    }));
  };

  const handleSaveFeed = async () => {
    try {
      if (state.editingFeed) {
        await apiService.updateRSSFeed(state.editingFeed.id, state.newFeed);
      } else {
        await apiService.createRSSFeed(state.newFeed);
      }
      
      setState(prev => ({ ...prev, dialogOpen: false }));
      loadFeeds();
    } catch (error) {
      console.error('Error saving RSS feed:', error);
    }
  };

  const handleDeleteFeed = async (feedId: number) => {
    if (window.confirm('Are you sure you want to delete this RSS feed?')) {
      try {
        await apiService.deleteRSSFeed(feedId);
        loadFeeds();
      } catch (error) {
        console.error('Error deleting RSS feed:', error);
      }
    }
  };

  const handleToggleFeed = async (feedId: number) => {
    try {
      await apiService.toggleRSSFeed(feedId);
      loadFeeds();
    } catch (error) {
      console.error('Error toggling RSS feed:', error);
    }
  };

  const handleTestFeed = async (feedId: number) => {
    try {
      await apiService.testRSSFeed(feedId);
      loadFeeds();
    } catch (error) {
      console.error('Error testing RSS feed:', error);
    }
  };

  const handleRefreshFeed = async (feedId: number) => {
    try {
      await apiService.refreshRSSFeed(feedId);
      loadFeeds();
    } catch (error) {
      console.error('Error refreshing RSS feed:', error);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusIcon = (feed: RSSFeed) => {
    if (feed.error_count > 0) {
      return <ErrorIcon color="error" />;
    }
    if (feed.last_success) {
      return <CheckIcon color="success" />;
    }
    return <PauseIcon color="warning" />;
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          RSS Feeds
        </Typography>
        <Box>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadFeeds}
            disabled={state.loading}
            sx={{ mr: 1 }}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateFeed}
          >
            Add Feed
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {state.error}
        </Alert>
      )}

      {/* Loading Indicator */}
      {state.loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* RSS Feeds Table */}
      {!state.loading && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>URL</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Articles</TableCell>
                <TableCell>Last Check</TableCell>
                <TableCell>Last Success</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {state.feeds.map((feed) => (
                <TableRow key={feed.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {feed.name}
                    </Typography>
                    {feed.description && (
                      <Typography variant="caption" color="text.secondary">
                        {feed.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {feed.url}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getStatusIcon(feed)}
                      <Chip
                        label={feed.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={feed.is_active ? 'success' : 'default'}
                      />
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {feed.article_count}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDate(feed.last_checked)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatDate(feed.last_success)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Tooltip title="Test Feed">
                      <IconButton
                        size="small"
                        onClick={() => handleTestFeed(feed.id)}
                      >
                        <TestIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Refresh Feed">
                      <IconButton
                        size="small"
                        onClick={() => handleRefreshFeed(feed.id)}
                      >
                        <RefreshIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Toggle Status">
                      <IconButton
                        size="small"
                        onClick={() => handleToggleFeed(feed.id)}
                      >
                        {feed.is_active ? <PauseIcon /> : <PlayIcon />}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Edit Feed">
                      <IconButton
                        size="small"
                        onClick={() => handleEditFeed(feed)}
                      >
                        <EditIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Feed">
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteFeed(feed.id)}
                        color="error"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Add/Edit Feed Dialog */}
      <Dialog open={state.dialogOpen} onClose={() => setState(prev => ({ ...prev, dialogOpen: false }))} maxWidth="md" fullWidth>
        <DialogTitle>
          {state.editingFeed ? 'Edit RSS Feed' : 'Add New RSS Feed'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Feed Name"
                value={state.newFeed.name}
                onChange={(e) => setState(prev => ({
                  ...prev,
                  newFeed: { ...prev.newFeed, name: e.target.value }
                }))}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Feed URL"
                value={state.newFeed.url}
                onChange={(e) => setState(prev => ({
                  ...prev,
                  newFeed: { ...prev.newFeed, url: e.target.value }
                }))}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={state.newFeed.description}
                onChange={(e) => setState(prev => ({
                  ...prev,
                  newFeed: { ...prev.newFeed, description: e.target.value }
                }))}
                multiline
                rows={2}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Category"
                value={state.newFeed.category}
                onChange={(e) => setState(prev => ({
                  ...prev,
                  newFeed: { ...prev.newFeed, category: e.target.value }
                }))}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={state.newFeed.is_active}
                    onChange={(e) => setState(prev => ({
                      ...prev,
                      newFeed: { ...prev.newFeed, is_active: e.target.checked }
                    }))}
                  />
                }
                label="Active"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setState(prev => ({ ...prev, dialogOpen: false }))}>
            Cancel
          </Button>
          <Button onClick={handleSaveFeed} variant="contained">
            {state.editingFeed ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RSSFeeds;
