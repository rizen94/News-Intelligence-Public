import {
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  Schedule as ScheduleIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  FilterList as FilterIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
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
  Divider,
  Tooltip,
  Badge,
  LinearProgress,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../../services/apiService.ts';

const Storylines = () => {
  const [storylines, setStorylines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalStorylines, setTotalStorylines] = useState(0);
  const [categories, setCategories] = useState([]);
  const [timelineData, setTimelineData] = useState([]);
  const [selectedStoryline, setSelectedStoryline] = useState(null);
  const [timelineDialogOpen, setTimelineDialogOpen] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    completed: 0,
    paused: 0,
    highPriority: 0,
  });

  const fetchStorylines = useCallback(async() => {
    try {
      setLoading(true);

      const params = {
        page,
        limit: 20,
        search: searchTerm || undefined,
        category: categoryFilter || undefined,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        sort_by: sortBy,
      };

      const response = await apiService.storylines.getStorylines(params);

      if (response.success) {
        setStorylines(response.data.storylines || []);
        setTotalPages(response.data.total_pages || 1);
        setTotalStorylines(response.data.total_count || 0);

        // Calculate statistics
        const storylines = response.data.storylines || [];
        const stats = {
          total: storylines.length,
          active: storylines.filter(s => s.status === 'active').length,
          completed: storylines.filter(s => s.status === 'completed').length,
          paused: storylines.filter(s => s.status === 'paused').length,
          highPriority: storylines.filter(s => s.priority === 'high').length,
        };
        setStats(stats);
      }
    } catch (error) {
      console.error('Error fetching storylines:', error);
    } finally {
      setLoading(false);
    }
  }, [page, searchTerm, categoryFilter, statusFilter, priorityFilter, sortBy]);

  const fetchCategories = useCallback(async() => {
    try {
      const response = await apiService.storylines.getCategories();
      if (response.success) {
        setCategories(response.data.categories || []);
      }
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  }, []);

  const fetchTimelineData = useCallback(async(storylineId) => {
    try {
      const response = await apiService.storylines.getTimeline(storylineId);
      if (response.success) {
        setTimelineData(response.data.timeline || []);
      }
    } catch (error) {
      console.error('Error fetching timeline data:', error);
    }
  }, []);

  useEffect(() => {
    fetchStorylines();
  }, [fetchStorylines]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const getStatusColor = (status) => {
    switch (status) {
    case 'active': return 'success';
    case 'completed': return 'info';
    case 'paused': return 'warning';
    case 'archived': return 'default';
    default: return 'default';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
    case 'high': return 'error';
    case 'medium': return 'warning';
    case 'low': return 'success';
    default: return 'default';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleViewTimeline = async(storyline) => {
    setSelectedStoryline(storyline);
    await fetchTimelineData(storyline.id);
    setTimelineDialogOpen(true);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          📚 Storylines with Timeline Tracking
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => fetchStorylines()}
          disabled={loading}
        >
          Refresh
        </Button>
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
                Total Storylines
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
              <Typography variant="h6" color="info">
                {stats.completed}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Completed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="warning">
                {stats.paused}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Paused
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="error">
                {stats.highPriority}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                High Priority
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="primary">
                {stats.total > 0 ? Math.round((stats.active / stats.total) * 100) : 0}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active Rate
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
              placeholder="Search storylines..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <TimelineIcon />
                  </InputAdornment>
                ),
              }}
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
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                label="Status"
              >
                <MenuItem value="">All Status</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="paused">Paused</MenuItem>
                <MenuItem value="archived">Archived</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                label="Priority"
              >
                <MenuItem value="">All Priority</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="low">Low</MenuItem>
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
                <MenuItem value="created_at">Created Date</MenuItem>
                <MenuItem value="updated_at">Updated Date</MenuItem>
                <MenuItem value="title">Title</MenuItem>
                <MenuItem value="priority">Priority</MenuItem>
                <MenuItem value="article_count">Article Count</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={1}>
            <Button
              variant="contained"
              startIcon={<FilterIcon />}
              onClick={() => fetchStorylines()}
              disabled={loading}
              fullWidth
            >
              Filter
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Storylines List */}
      {loading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={2}>
          {storylines.map((storyline) => (
            <Grid item xs={12} key={storyline.id}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Box flex={1}>
                      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
                        {storyline.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {storyline.description || 'No description available'}
                      </Typography>
                      <Box display="flex" alignItems="center" gap={1} mb={1}>
                        <Chip
                          icon={<ScheduleIcon />}
                          label={formatDate(storyline.created_at)}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          icon={<ArticleIcon />}
                          label={`${storyline.article_count || 0} articles`}
                          size="small"
                          variant="outlined"
                        />
                        {storyline.category && (
                          <Chip
                            label={storyline.category}
                            size="small"
                            color="primary"
                          />
                        )}
                      </Box>
                    </Box>
                    <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
                      {/* Status */}
                      <Chip
                        label={storyline.status}
                        color={getStatusColor(storyline.status)}
                        size="small"
                      />

                      {/* Priority */}
                      {storyline.priority && (
                        <Chip
                          label={`Priority: ${storyline.priority}`}
                          color={getPriorityColor(storyline.priority)}
                          size="small"
                          variant="outlined"
                        />
                      )}

                      {/* Action Buttons */}
                      <Box display="flex" gap={1}>
                        <Button
                          size="small"
                          startIcon={<TimelineIcon />}
                          onClick={() => handleViewTimeline(storyline)}
                        >
                          Timeline
                        </Button>
                        <Button
                          size="small"
                          startIcon={<EditIcon />}
                          variant="outlined"
                        >
                          Edit
                        </Button>
                      </Box>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Timeline Dialog */}
      <Dialog
        open={timelineDialogOpen}
        onClose={() => setTimelineDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <TimelineIcon />
            Timeline: {selectedStoryline?.title}
          </Box>
        </DialogTitle>
        <DialogContent>
          {timelineData.length > 0 ? (
            <Stepper orientation="vertical">
              {timelineData.map((event, index) => (
                <Step key={index} active>
                  <StepLabel>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="subtitle1">{event.title}</Typography>
                      <Chip
                        label={event.type}
                        size="small"
                        color="primary"
                      />
                    </Box>
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {event.description}
                    </Typography>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Chip
                        icon={<ScheduleIcon />}
                        label={formatDate(event.timestamp)}
                        size="small"
                        variant="outlined"
                      />
                      {event.article_count && (
                        <Chip
                          icon={<ArticleIcon />}
                          label={`${event.article_count} articles`}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          ) : (
            <Typography color="text.secondary">
              No timeline data available for this storyline.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTimelineDialogOpen(false)}>
            Close
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
          Showing {storylines.length} of {totalStorylines} storylines
        </Typography>
      </Box>
    </Box>
  );
};

export default Storylines;
