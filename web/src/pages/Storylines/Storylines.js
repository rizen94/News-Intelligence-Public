import React, { useState, useEffect, useCallback } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Fab,
  Tooltip,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Article as ArticleIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
// import { useNotifications } from '../../components/Notifications/NotificationSystem';
// import newsSystemService from '../../services/newsSystemService';
// import EditStorylineDialog from '../../components/EditStorylineDialog/EditStorylineDialog';

const Storylines = () => {
  const [storylines, setStorylines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('updated_at');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalStorylines, setTotalStorylines] = useState(0);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedStoryline, setSelectedStoryline] = useState(null);
  const [newStoryline, setNewStoryline] = useState({
    title: '',
    description: '',
    category: '',
    priority: 'medium',
    targets: [],
    quality_filters: []
  });
  const navigate = useNavigate();
  // const { showSuccess, showError, showLoading } = useNotifications();

  const fetchStorylines = useCallback(async () => {
    try {
      setLoading(true);
      // showLoading('Loading storylines...');

      // const response = await newsSystemService.getActiveStories();
      const response = { success: true, data: { storylines: [] } };
      
      
      if (response.success) {
        setStorylines(response.data || []);
        // showSuccess(`Loaded ${response.data?.length || 0} storylines`);
      } else {
        console.error('Storylines API Error:', response);
        throw new Error(response.message || 'Failed to fetch storylines');
      }
    } catch (error) {
      console.error('Error fetching storylines:', error);
      // showError('Failed to load storylines. Please try refreshing the page.');
      
      // Set empty state instead of mock data
      setStorylines([]);
      setTotalPages(1);
      setTotalStorylines(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStorylines();
  }, [fetchStorylines]);

  const handleSearch = () => {
    setPage(1);
    fetchStorylines();
  };

  const handleClearFilters = () => {
    setSearchTerm('');
    setCategoryFilter('');
    setStatusFilter('');
    setSortBy('updated_at');
    setPage(1);
  };

  const handleCreateStoryline = async () => {
    try {
      // showLoading('Creating storyline...');
      
      // Convert form data to API format
      const storylineData = {
        name: newStoryline.title,
        description: newStoryline.description,
        priority_level: newStoryline.priority === 'high' ? 8 : newStoryline.priority === 'medium' ? 5 : 3,
        keywords: newStoryline.targets || [],
        entities: [],
        geographic_regions: [],
        quality_threshold: 0.7,
        max_articles_per_day: 50,
        auto_enhance: true,
        is_active: true
      };
      
      // const response = await newsSystemService.createStoryExpectation(storylineData);
      const response = { success: true, data: { id: Date.now() } };
      
      if (response.success) {
        // showSuccess('Storyline created successfully');
        setCreateDialogOpen(false);
        setNewStoryline({
          title: '',
          description: '',
          category: '',
          priority: 'medium',
          targets: [],
          quality_filters: []
        });
        fetchStorylines();
      } else {
        throw new Error(response.message || 'Failed to create storyline');
      }
    } catch (error) {
      console.error('Error creating storyline:', error);
        // showError('Failed to create storyline');
    }
  };

  const handleDeleteStoryline = async (storylineId) => {
    try {
      // showLoading('Deleting storyline...');
      
      // const response = await newsSystemService.deleteStoryline(storylineId);
      const response = { success: true };
      
      if (response.success) {
        // showSuccess('Storyline deleted successfully');
        fetchStorylines();
      } else {
        throw new Error(response.message || 'Failed to delete storyline');
      }
    } catch (error) {
      console.error('Error deleting storyline:', error);
        // showError('Failed to delete storyline');
    }
  };

  const handleEditStoryline = (storyline) => {
    setSelectedStoryline(storyline);
    setEditDialogOpen(true);
  };

  const handleEditSuccess = () => {
    fetchStorylines();
  };

  const handleStorylineClick = (storylineId) => {
    navigate(`/storylines/${storylineId}`);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'error';
      case 'medium': return 'warning';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const getCategoryColor = (category) => {
    switch (category) {
      case 'Global Events': return 'primary';
      case 'Business': return 'secondary';
      case 'Politics': return 'error';
      case 'Technology': return 'info';
      default: return 'default';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'success';
      case 'paused': return 'warning';
      case 'completed': return 'info';
      default: return 'default';
    }
  };

  if (loading && storylines.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={60} />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading storylines...
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          My Storylines
        </Typography>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          {totalStorylines} storylines tracked
        </Typography>
      </Box>

      {/* Search and Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                placeholder="Search storylines..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
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
                  <MenuItem value="Global Events">Global Events</MenuItem>
                  <MenuItem value="Business">Business</MenuItem>
                  <MenuItem value="Politics">Politics</MenuItem>
                  <MenuItem value="Technology">Technology</MenuItem>
                </Select>
              </FormControl>
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
                  <MenuItem value="paused">Paused</MenuItem>
                  <MenuItem value="completed">Completed</MenuItem>
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
                  <MenuItem value="updated_at">Last Updated</MenuItem>
                  <MenuItem value="created_at">Created Date</MenuItem>
                  <MenuItem value="title">Title</MenuItem>
                  <MenuItem value="priority">Priority</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={2}>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="contained"
                  onClick={handleSearch}
                  startIcon={<SearchIcon />}
                  fullWidth
                >
                  Search
                </Button>
                <Button
                  variant="outlined"
                  onClick={handleClearFilters}
                >
                  Clear
                </Button>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Storylines Grid */}
      <Grid container spacing={3}>
        {storylines.map((storyline) => (
          <Grid item xs={12} md={6} lg={4} key={storyline.id}>
            <Card 
              sx={{ 
                height: '100%',
                cursor: 'pointer',
                '&:hover': { 
                  boxShadow: 4,
                  transform: 'translateY(-2px)',
                  transition: 'all 0.2s ease-in-out'
                },
                display: 'flex',
                flexDirection: 'column',
                borderLeft: `4px solid ${
                  storyline.priority_level >= 8 ? '#d32f2f' : 
                  storyline.priority_level >= 5 ? '#ed6c02' : '#2e7d32'
                }`
              }}
              onClick={() => handleStorylineClick(storyline.story_id)}
            >
              <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                {/* Header */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Typography variant="h6" component="h3" noWrap sx={{ flexGrow: 1, mr: 1 }}>
                    {storyline.name}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Chip 
                      label={`Priority ${storyline.priority_level}`} 
                      size="small" 
                      color={storyline.priority_level >= 8 ? 'error' : storyline.priority_level >= 5 ? 'warning' : 'success'}
                    />
                    <Chip 
                      label={storyline.is_active ? 'Active' : 'Inactive'} 
                      size="small" 
                      color={storyline.is_active ? 'success' : 'default'}
                    />
                  </Box>
                </Box>
                
                <Chip 
                  label="Global Events" 
                  size="small" 
                  color="primary"
                  sx={{ mb: 2, alignSelf: 'flex-start' }}
                />
                
                {/* Description */}
                <Typography 
                  variant="body2" 
                  color="text.secondary" 
                  sx={{ 
                    mb: 2,
                    flexGrow: 1,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}
                >
                  {storyline.description}
                </Typography>
                
                {/* Stats */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <ArticleIcon sx={{ fontSize: 16, mr: 0.5, color: 'text.secondary' }} />
                      <Typography variant="caption" color="text.secondary">
                        Max: {storyline.max_articles_per_day}/day
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <ScheduleIcon sx={{ fontSize: 16, mr: 0.5, color: 'text.secondary' }} />
                      <Typography variant="caption" color="text.secondary">
                        Updated: {formatDate(storyline.updated_at)}
                      </Typography>
                    </Box>
                  </Box>
                </Box>

                {/* Keywords */}
                {storyline.keywords && storyline.keywords.length > 0 && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                    {(storyline.keywords || []).slice(0, 3).map((keyword, index) => (
                      <Chip 
                        key={index}
                        label={keyword} 
                        size="small" 
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    ))}
                    {storyline.keywords.length > 3 && (
                      <Chip 
                        label={`+${storyline.keywords.length - 3}`} 
                        size="small" 
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    )}
                  </Box>
                )}

                {/* Actions */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" color="text.secondary">
                    Updated {formatDate(storyline.updated_at)}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Tooltip title="Edit">
                      <IconButton 
                        size="small" 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditStoryline(storyline);
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton 
                        size="small" 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteStoryline(storyline.story_id);
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Create Storyline FAB */}
      <Fab
        color="primary"
        aria-label="add"
        sx={{ position: 'fixed', bottom: 16, right: 16 }}
        onClick={() => setCreateDialogOpen(true)}
      >
        <AddIcon />
      </Fab>

      {/* Create Storyline Dialog */}
      <Dialog 
        open={createDialogOpen} 
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Create New Storyline</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Title"
                value={newStoryline.title}
                onChange={(e) => setNewStoryline({...newStoryline, title: e.target.value})}
                placeholder="e.g., Ukraine-Russia Conflict"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                multiline
                rows={3}
                value={newStoryline.description}
                onChange={(e) => setNewStoryline({...newStoryline, description: e.target.value})}
                placeholder="Describe what this storyline tracks..."
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={newStoryline.category}
                  onChange={(e) => setNewStoryline({...newStoryline, category: e.target.value})}
                  label="Category"
                >
                  <MenuItem value="Global Events">Global Events</MenuItem>
                  <MenuItem value="Business">Business</MenuItem>
                  <MenuItem value="Politics">Politics</MenuItem>
                  <MenuItem value="Technology">Technology</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Priority</InputLabel>
                <Select
                  value={newStoryline.priority}
                  onChange={(e) => setNewStoryline({...newStoryline, priority: e.target.value})}
                  label="Priority"
                >
                  <MenuItem value="low">Low</MenuItem>
                  <MenuItem value="medium">Medium</MenuItem>
                  <MenuItem value="high">High</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateStoryline} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>

      {/* Edit Storyline Dialog */}
      {/* <EditStorylineDialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        storyline={selectedStoryline}
        onSuccess={handleEditSuccess}
      /> */}
    </Box>
  );
};

export default Storylines;
