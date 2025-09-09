import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  RssFeed as RssIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
} from '@mui/icons-material';

// Import services
import { rssService } from '../../services/rssService';

interface RSSFeed {
  id: number;
  name: string;
  url: string;
  description?: string;
  category?: string;
  is_active: boolean;
  last_checked?: string;
  created_at: string;
  updated_at: string;
  status?: 'healthy' | 'error' | 'warning';
  error_message?: string;
}

const RSSManagement: React.FC = () => {
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingFeed, setEditingFeed] = useState<RSSFeed | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    description: '',
    category: '',
    is_active: true,
  });

  const fetchFeeds = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await rssService.getFeeds();
      
      if (response.success) {
        setFeeds(response.data || []);
      } else {
        setError('Failed to load RSS feeds');
      }
    } catch (err) {
      setError('Failed to load RSS feeds');
      console.error('RSS feeds error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeeds();
  }, []);

  const handleAddFeed = () => {
    setEditingFeed(null);
    setFormData({
      name: '',
      url: '',
      description: '',
      category: '',
      is_active: true,
    });
    setDialogOpen(true);
  };

  const handleEditFeed = (feed: RSSFeed) => {
    setEditingFeed(feed);
    setFormData({
      name: feed.name,
      url: feed.url,
      description: feed.description || '',
      category: feed.category || '',
      is_active: feed.is_active,
    });
    setDialogOpen(true);
  };

  const handleSaveFeed = async () => {
    try {
      if (editingFeed) {
        // Update existing feed
        const response = await rssService.updateFeed(editingFeed.id, formData);
        if (response.success) {
          await fetchFeeds();
          setDialogOpen(false);
        } else {
          setError('Failed to update RSS feed');
        }
      } else {
        // Create new feed
        const response = await rssService.createFeed(formData);
        if (response.success) {
          await fetchFeeds();
          setDialogOpen(false);
        } else {
          setError('Failed to create RSS feed');
        }
      }
    } catch (err) {
      setError('Failed to save RSS feed');
      console.error('Save feed error:', err);
    }
  };

  const handleDeleteFeed = async (feedId: number) => {
    if (window.confirm('Are you sure you want to delete this RSS feed?')) {
      try {
        const response = await rssService.deleteFeed(feedId);
        if (response.success) {
          await fetchFeeds();
        } else {
          setError('Failed to delete RSS feed');
        }
      } catch (err) {
        setError('Failed to delete RSS feed');
        console.error('Delete feed error:', err);
      }
    }
  };

  const handleToggleFeed = async (feed: RSSFeed) => {
    try {
      const response = await rssService.updateFeed(feed.id, {
        ...feed,
        is_active: !feed.is_active,
      });
      if (response.success) {
        await fetchFeeds();
      } else {
        setError('Failed to toggle RSS feed');
      }
    } catch (err) {
      setError('Failed to toggle RSS feed');
      console.error('Toggle feed error:', err);
    }
  };

  const handleTestFeed = async (feed: RSSFeed) => {
    try {
      const response = await rssService.testFeed(feed.id);
      if (response.success) {
        // Show success message
        console.log('Feed test successful');
      } else {
        setError('Feed test failed');
      }
    } catch (err) {
      setError('Feed test failed');
      console.error('Test feed error:', err);
    }
  };

  const getStatusIcon = (feed: RSSFeed) => {
    if (feed.status === 'error') return <ErrorIcon color="error" />;
    if (feed.status === 'warning') return <WarningIcon color="warning" />;
    return <CheckCircleIcon color="success" />;
  };

  const getStatusColor = (feed: RSSFeed) => {
    if (feed.status === 'error') return 'error';
    if (feed.status === 'warning') return 'warning';
    return 'success';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          RSS Feed Management
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchFeeds}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddFeed}
          >
            Add Feed
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Total Feeds
                  </Typography>
                  <Typography variant="h4" component="div">
                    {feeds.length}
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
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Active Feeds
                  </Typography>
                  <Typography variant="h4" component="div">
                    {feeds.filter(feed => feed.is_active).length}
                  </Typography>
                </Box>
                <CheckCircleIcon sx={{ fontSize: 40, color: 'success.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Healthy Feeds
                  </Typography>
                  <Typography variant="h4" component="div">
                    {feeds.filter(feed => feed.status === 'healthy' || !feed.status).length}
                  </Typography>
                </Box>
                <CheckCircleIcon sx={{ fontSize: 40, color: 'success.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="h6">
                    Error Feeds
                  </Typography>
                  <Typography variant="h4" component="div">
                    {feeds.filter(feed => feed.status === 'error').length}
                  </Typography>
                </Box>
                <ErrorIcon sx={{ fontSize: 40, color: 'error.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Feeds Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            RSS Feeds
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>URL</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Last Checked</TableCell>
                  <TableCell>Active</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {feeds.map((feed) => (
                  <TableRow key={feed.id}>
                    <TableCell>
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 500 }}>
                          {feed.name}
                        </Typography>
                        {feed.description && (
                          <Typography variant="body2" color="textSecondary">
                            {feed.description}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                        {feed.url}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {feed.category && (
                        <Chip label={feed.category} size="small" variant="outlined" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getStatusIcon(feed)}
                        <Typography variant="body2" color={`${getStatusColor(feed)}.main`}>
                          {feed.status || 'Unknown'}
                        </Typography>
                      </Box>
                      {feed.error_message && (
                        <Typography variant="caption" color="error" sx={{ display: 'block' }}>
                          {feed.error_message}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="textSecondary">
                        {feed.last_checked ? formatDate(feed.last_checked) : 'Never'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={feed.is_active}
                        onChange={() => handleToggleFeed(feed)}
                        color="primary"
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Tooltip title="Test Feed">
                          <IconButton
                            size="small"
                            onClick={() => handleTestFeed(feed)}
                          >
                            <PlayIcon />
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
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Add/Edit Feed Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingFeed ? 'Edit RSS Feed' : 'Add RSS Feed'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Feed Name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    label="Category"
                  >
                    <MenuItem value="">Select Category</MenuItem>
                    <MenuItem value="general">General</MenuItem>
                    <MenuItem value="technology">Technology</MenuItem>
                    <MenuItem value="politics">Politics</MenuItem>
                    <MenuItem value="business">Business</MenuItem>
                    <MenuItem value="science">Science</MenuItem>
                    <MenuItem value="health">Health</MenuItem>
                    <MenuItem value="sports">Sports</MenuItem>
                    <MenuItem value="entertainment">Entertainment</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="RSS URL"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  required
                  placeholder="https://example.com/rss.xml"
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  multiline
                  rows={3}
                />
              </Grid>
              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    />
                  }
                  label="Active"
                />
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveFeed}
            disabled={!formData.name || !formData.url}
          >
            {editingFeed ? 'Update' : 'Add'} Feed
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RSSManagement;

