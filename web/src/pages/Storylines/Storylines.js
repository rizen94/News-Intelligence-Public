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
  Alert,
  Snackbar,
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
import apiService from '../../services/apiService';
import StorylineCreationDialog from '../../components/StorylineCreationDialog';
import StorylineConfirmationDialog from '../../components/StorylineConfirmationDialog';

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
  const [confirmationDialog, setConfirmationDialog] = useState({
    open: false,
    action: null,
    storyline: null
  });
  const [selectedStoryline, setSelectedStoryline] = useState(null);
  const [newStoryline, setNewStoryline] = useState({
    title: '',
    description: '',
    category: '',
    priority: 'medium',
    targets: [],
    quality_filters: []
  });
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  const [actionLoading, setActionLoading] = useState(false);
  const navigate = useNavigate();

  const fetchStorylines = useCallback(async () => {
    try {
      setLoading(true);
        const response = await apiService.get('/api/storylines');
        
        if (response.success) {
          const storylinesData = response.data?.storylines || [];
        setStorylines(storylinesData);
        setTotalStorylines(response.data?.total_count || storylinesData.length);
        setTotalPages(Math.ceil((response.data?.total_count || storylinesData.length) / 12));
        showSnackbar(`Loaded ${storylinesData.length} storylines`, 'success');
      } else {
        console.error('Storylines API Error:', response);
        throw new Error(response.message || 'Failed to fetch storylines');
      }
    } catch (error) {
      console.error('Error fetching storylines:', error);
      showSnackbar('Failed to load storylines. Please try refreshing the page.', 'error');
      
      // Set empty state
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

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({
      open: true,
      message,
      severity
    });
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  const handleCreateStoryline = () => {
    setCreateDialogOpen(true);
  };

  const handleCreateSuccess = (newStoryline) => {
    setStorylines(prev => [newStoryline, ...prev]);
    setTotalStorylines(prev => prev + 1);
    showSnackbar('Storyline created successfully!', 'success');
    setCreateDialogOpen(false);
  };

  const handleEditStoryline = (storyline) => {
    setSelectedStoryline(storyline);
    setEditDialogOpen(true);
  };

  const handleDeleteStoryline = (storyline) => {
    setConfirmationDialog({
      open: true,
      action: 'delete',
      storyline
    });
  };

  const handleConfirmAction = async () => {
    const { action, storyline } = confirmationDialog;
    setActionLoading(true);

    try {
      if (action === 'delete') {
        const response = await apiService.delete(`/storylines/${storyline.id}`);
        if (response.success) {
          setStorylines(prev => prev.filter(s => s.id !== storyline.id));
          setTotalStorylines(prev => prev - 1);
          showSnackbar('Storyline deleted successfully!', 'success');
        } else {
          throw new Error(response.message || 'Failed to delete storyline');
        }
      }
    } catch (error) {
      console.error(`Error ${action}ing storyline:`, error);
      showSnackbar(`Failed to ${action} storyline: ${error.message}`, 'error');
    } finally {
      setActionLoading(false);
      setConfirmationDialog({ open: false, action: null, storyline: null });
    }
  };

  const handleCloseConfirmation = () => {
    if (!actionLoading) {
      setConfirmationDialog({ open: false, action: null, storyline: null });
    }
  };

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


  const handleEditSuccess = () => {
    fetchStorylines();
  };

  const handleStorylineClick = (storylineId) => {
    navigate(`/storylines/${storylineId}/report`);
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
                  storyline.status === 'active' ? '#2e7d32' : '#757575'
                }`
              }}
              onClick={() => handleStorylineClick(storyline.id)}
            >
              <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                {/* Header */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Typography variant="h6" component="h3" noWrap sx={{ flexGrow: 1, mr: 1 }}>
                    {storyline.title}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Chip 
                      label={storyline.status} 
                      size="small" 
                      color={storyline.status === 'active' ? 'success' : 'default'}
                    />
                    <Chip 
                      label={`${storyline.article_count} articles`} 
                      size="small" 
                      color="info"
                    />
                    {storyline.ml_processing_status && (
                      <Chip 
                        label={storyline.ml_processing_status} 
                        size="small" 
                        color={
                          storyline.ml_processing_status === 'completed' ? 'success' :
                          storyline.ml_processing_status === 'processing' ? 'warning' :
                          storyline.ml_processing_status === 'queued' ? 'info' : 'default'
                        }
                      />
                    )}
                  </Box>
                </Box>
                
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
                        {storyline.article_count} articles
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

                {/* Master Summary Preview */}
                {storyline.master_summary && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}>
                      AI Summary:
                    </Typography>
                    <Typography 
                      variant="body2" 
                      color="text.secondary" 
                      sx={{ 
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        fontSize: '0.8rem'
                      }}
                    >
                      {storyline.master_summary}
                    </Typography>
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
                          handleDeleteStoryline(storyline.id);
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
        onClick={handleCreateStoryline}
      >
        <AddIcon />
      </Fab>

      {/* Storyline Creation Dialog */}
      <StorylineCreationDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onSuccess={handleCreateSuccess}
      />

      {/* Confirmation Dialog */}
      <StorylineConfirmationDialog
        open={confirmationDialog.open}
        onClose={handleCloseConfirmation}
        onConfirm={handleConfirmAction}
        action={confirmationDialog.action}
        storyline={confirmationDialog.storyline}
        loading={actionLoading}
      />

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={handleCloseSnackbar} 
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Storylines;
