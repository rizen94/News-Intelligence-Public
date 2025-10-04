import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Visibility as VisibilityIcon,
  Share as ShareIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  Sort as SortIcon,
  ViewList as ViewListIcon,
  ViewModule as ViewModuleIcon,
  ExpandMore as ExpandMoreIcon,
  Article as ArticleIcon,
  Group as GroupIcon,
  Analytics as AnalyticsIcon,
  Assessment as AssessmentIcon,
  History as HistoryIcon,
  AutoAwesome as PredictionIcon,
  Person as PersonIcon,
  Public as PublicIcon,
  Business as BusinessIcon,
  Science as ScienceIcon,
  School as SchoolIcon,
  Work as WorkIcon,
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
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/material';
import React, { useState, useEffect, useCallback } from 'react';

import { apiService } from '../../services/apiService.ts';

const EnhancedStorylines = () => {
  const [storylines, setStorylines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [sortBy, setSortBy] = useState('updated_at');
  const [viewMode, setViewMode] = useState('grid');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [bookmarkedStorylines, setBookmarkedStorylines] = useState(new Set());
  const [expandedStoryline, setExpandedStoryline] = useState(null);

  const loadStorylines = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getStorylines({
        page,
        limit: 12,
        search: searchQuery,
        status: filterStatus,
        category: filterCategory,
        sort: sortBy,
      });

      if (response.success) {
        setStorylines(response.data.storylines || []);
        setTotalPages(Math.ceil((response.data.total || 0) / 12));
      } else {
        setStorylines([]);
        setTotalPages(1);
      }
    } catch (err) {
      console.error('Error loading storylines:', err);
      setError('Failed to load storylines');
      setStorylines([]);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, filterStatus, filterCategory, sortBy]);

  useEffect(() => {
    loadStorylines();
  }, [loadStorylines]);

  const handleSearch = (event) => {
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

  const handleRefresh = () => {
    loadStorylines();
  };

  const toggleBookmark = (storylineId) => {
    const newBookmarked = new Set(bookmarkedStorylines);
    if (newBookmarked.has(storylineId)) {
      newBookmarked.delete(storylineId);
    } else {
      newBookmarked.add(storylineId);
    }
    setBookmarkedStorylines(newBookmarked);
  };

  const toggleExpanded = (storylineId) => {
    setExpandedStoryline(expandedStoryline === storylineId ? null : storylineId);
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
    case 'active': return 'success';
    case 'developing': return 'warning';
    case 'resolved': return 'info';
    case 'archived': return 'default';
    default: return 'default';
    }
  };

  const getCategoryIcon = (category) => {
    switch (category?.toLowerCase()) {
    case 'politics': return <PublicIcon />;
    case 'business': return <BusinessIcon />;
    case 'technology': return <ScienceIcon />;
    case 'health': return <PersonIcon />;
    case 'education': return <SchoolIcon />;
    case 'employment': return <WorkIcon />;
    default: return <ArticleIcon />;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateText = (text, maxLength = 150) => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const StorylineCard = ({ storyline }) => (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Typography variant="h6" component="h3" sx={{
            fontWeight: 'bold',
            lineHeight: 1.2,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}>
            {storyline.title || 'Untitled Storyline'}
          </Typography>
          <IconButton
            size="small"
            onClick={() => toggleBookmark(storyline.id)}
            sx={{ ml: 1 }}
          >
            {bookmarkedStorylines.has(storyline.id) ?
              <BookmarkIcon color="primary" /> :
              <BookmarkBorderIcon />
            }
          </IconButton>
        </Box>

        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: 2,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {truncateText(storyline.description || storyline.summary)}
        </Typography>

        <Box display="flex" flexWrap="wrap" gap={1} mb={2}>
          {storyline.status && (
            <Chip
              label={storyline.status}
              color={getStatusColor(storyline.status)}
              size="small"
            />
          )}
          {storyline.category && (
            <Chip
              icon={getCategoryIcon(storyline.category)}
              label={storyline.category}
              color="secondary"
              size="small"
            />
          )}
          {storyline.impact_score && (
            <Chip
              label={`Impact: ${Math.round(storyline.impact_score * 100)}%`}
              color="primary"
              size="small"
            />
          )}
        </Box>

        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Box display="flex" alignItems="center" gap={1}>
            <ArticleIcon fontSize="small" color="action" />
            <Typography variant="caption" color="text.secondary">
              {storyline.article_count || 0} articles
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Updated: {formatDate(storyline.updated_at || storyline.created_at)}
          </Typography>
        </Box>

        {storyline.key_entities && storyline.key_entities.length > 0 && (
          <Box mt={1}>
            <Typography variant="caption" color="text.secondary" display="block">
              Key Entities: {storyline.key_entities.slice(0, 3).join(', ')}
              {storyline.key_entities.length > 3 && ` +${storyline.key_entities.length - 3} more`}
            </Typography>
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button
          size="small"
          startIcon={<VisibilityIcon />}
          onClick={() => toggleExpanded(storyline.id)}
        >
          {expandedStoryline === storyline.id ? 'Hide Details' : 'View Details'}
        </Button>
        <Button size="small" startIcon={<TimelineIcon />}>
          Timeline
        </Button>
        <Button size="small" startIcon={<ShareIcon />}>
          Share
        </Button>
      </CardActions>
    </Card>
  );

  const StorylineListItem = ({ storyline }) => (
    <ListItem
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        mb: 1,
        bgcolor: 'background.paper',
        flexDirection: 'column',
        alignItems: 'stretch',
      }}
    >
      <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
        <ListItemText
          primary={
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <Typography variant="h6" sx={{ flexGrow: 1 }}>
                {storyline.title || 'Untitled Storyline'}
              </Typography>
              <Box display="flex" gap={1}>
                {storyline.status && (
                  <Chip
                    label={storyline.status}
                    color={getStatusColor(storyline.status)}
                    size="small"
                  />
                )}
                {storyline.category && (
                  <Chip
                    icon={getCategoryIcon(storyline.category)}
                    label={storyline.category}
                    color="secondary"
                    size="small"
                  />
                )}
                {storyline.impact_score && (
                  <Chip
                    label={`${Math.round(storyline.impact_score * 100)}%`}
                    color="primary"
                    size="small"
                  />
                )}
              </Box>
            </Box>
          }
          secondary={
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {truncateText(storyline.description || storyline.summary, 200)}
              </Typography>
              <Box display="flex" alignItems="center" gap={2}>
                <Box display="flex" alignItems="center" gap={0.5}>
                  <ArticleIcon fontSize="small" />
                  <Typography variant="caption">
                    {storyline.article_count || 0} articles
                  </Typography>
                </Box>
                <Typography variant="caption">
                  Updated: {formatDate(storyline.updated_at || storyline.created_at)}
                </Typography>
                {storyline.key_entities && storyline.key_entities.length > 0 && (
                  <Typography variant="caption" color="text.secondary">
                    Entities: {storyline.key_entities.slice(0, 3).join(', ')}
                  </Typography>
                )}
              </Box>
            </Box>
          }
        />
        <ListItemSecondaryAction>
          <Box display="flex" gap={1}>
            <IconButton
              size="small"
              onClick={() => toggleBookmark(storyline.id)}
            >
              {bookmarkedStorylines.has(storyline.id) ?
                <BookmarkIcon color="primary" /> :
                <BookmarkBorderIcon />
              }
            </IconButton>
            <Button
              size="small"
              startIcon={<VisibilityIcon />}
              onClick={() => toggleExpanded(storyline.id)}
            >
              {expandedStoryline === storyline.id ? 'Hide' : 'Details'}
            </Button>
          </Box>
        </ListItemSecondaryAction>
      </Box>

      {expandedStoryline === storyline.id && (
        <Box width="100%" mt={2}>
          <Divider sx={{ mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            AI Analysis Features
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <AutoAwesomeIcon color="primary" sx={{ fontSize: 30, mb: 1 }} />
                <Typography variant="subtitle2">Multi-Perspective</Typography>
                <Typography variant="caption" color="text.secondary">
                  Available
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <AssessmentIcon color="primary" sx={{ fontSize: 30, mb: 1 }} />
                <Typography variant="subtitle2">Impact Assessment</Typography>
                <Typography variant="caption" color="text.secondary">
                  Available
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <HistoryIcon color="primary" sx={{ fontSize: 30, mb: 1 }} />
                <Typography variant="subtitle2">Historical Context</Typography>
                <Typography variant="caption" color="text.secondary">
                  Available
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        </Box>
      )}
    </ListItem>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          Storylines
        </Typography>
        <Box display="flex" gap={2} alignItems="center">
          <Tooltip title="Refresh Storylines">
            <IconButton onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant={viewMode === 'grid' ? 'contained' : 'outlined'}
            startIcon={<ViewModuleIcon />}
            onClick={() => setViewMode('grid')}
            size="small"
          >
            Grid
          </Button>
          <Button
            variant={viewMode === 'list' ? 'contained' : 'outlined'}
            startIcon={<ViewListIcon />}
            onClick={() => setViewMode('list')}
            size="small"
          >
            List
          </Button>
        </Box>
      </Box>

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder="Search storylines by title or description..."
              value={searchQuery}
              onChange={handleSearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
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
                label="Status"
                onChange={(e) => handleFilterChange('status', e.target.value)}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="developing">Developing</MenuItem>
                <MenuItem value="resolved">Resolved</MenuItem>
                <MenuItem value="archived">Archived</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={filterCategory}
                label="Category"
                onChange={(e) => handleFilterChange('category', e.target.value)}
              >
                <MenuItem value="">All Categories</MenuItem>
                <MenuItem value="politics">Politics</MenuItem>
                <MenuItem value="business">Business</MenuItem>
                <MenuItem value="technology">Technology</MenuItem>
                <MenuItem value="health">Health</MenuItem>
                <MenuItem value="education">Education</MenuItem>
                <MenuItem value="employment">Employment</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={(e) => handleFilterChange('sort', e.target.value)}
              >
                <MenuItem value="updated_at">Last Updated</MenuItem>
                <MenuItem value="created_at">Created Date</MenuItem>
                <MenuItem value="impact_score">Impact Score</MenuItem>
                <MenuItem value="article_count">Article Count</MenuItem>
                <MenuItem value="title">Title</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<FilterIcon />}
              onClick={() => {
                setSearchQuery('');
                setFilterStatus('');
                setFilterCategory('');
                setSortBy('updated_at');
                setPage(1);
              }}
            >
              Clear Filters
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Storylines Display */}
      {storylines.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <TimelineIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No storylines found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {searchQuery || filterStatus || filterCategory
              ? 'Try adjusting your search criteria or filters'
              : 'Storylines will appear here once the system starts analyzing articles'
            }
          </Typography>
        </Paper>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {storylines.map((storyline) => (
                <Grid item xs={12} sm={6} md={4} key={storyline.id}>
                  <StorylineCard storyline={storyline} />
                </Grid>
              ))}
            </Grid>
          ) : (
            <List>
              {storylines.map((storyline) => (
                <StorylineListItem key={storyline.id} storyline={storyline} />
              ))}
            </List>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Box display="flex" justifyContent="center" mt={4}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(event, value) => setPage(value)}
                color="primary"
                size="large"
              />
            </Box>
          )}
        </>
      )}

      {/* AI Analysis Features */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Advanced AI Analysis Features
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}>
            <Box textAlign="center">
              <AutoAwesomeIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Multi-Perspective Analysis</Typography>
              <Typography variant="body2" color="text.secondary">
                Analyze storylines from multiple viewpoints and sources
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={3}>
            <Box textAlign="center">
              <AssessmentIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Impact Assessment</Typography>
              <Typography variant="body2" color="text.secondary">
                Evaluate potential impacts across different dimensions
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={3}>
            <Box textAlign="center">
              <HistoryIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Historical Context</Typography>
              <Typography variant="body2" color="text.secondary">
                Connect current events to historical patterns
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={3}>
            <Box textAlign="center">
              <PredictionIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="h6">Predictive Analysis</Typography>
              <Typography variant="body2" color="text.secondary">
                Forecast future developments and trends
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default EnhancedStorylines;
