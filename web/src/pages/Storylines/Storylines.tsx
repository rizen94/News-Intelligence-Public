import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  FilterList,
  Refresh,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Schedule,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Visibility,
  Share as ShareIcon,
  Bookmark,
  BookmarkBorder,
  ViewList,
  ViewModule,
  Article,
  Assessment as AssessmentIcon,
  History as HistoryIcon,
  Person as PersonIcon,
  Public as PublicIcon,
  Business as BusinessIcon,
  Science as ScienceIcon,
  School as SchoolIcon,
  Work as WorkIcon,
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
  CardActions,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';

import apiService from '../../services/apiService';
import StorylineManagementDialog from '../../components/StorylineManagementDialog';
import { useDomainNavigation } from '../../hooks/useDomainNavigation';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { useDomain } from '../../contexts/DomainContext';
import { useNotification } from '../../hooks/useNotification';
import { getUserFriendlyError } from '../../utils/errorHandler';
import { formatDomainLabel } from '../../utils/domainHelper';
import LoadingState from '../../components/shared/LoadingState';
import EmptyState from '../../components/shared/EmptyState';

interface Storyline {
  id: number;
  title: string;
  description?: string;
  summary?: string;
  status?: string;
  category?: string;
  priority?: string;
  article_count?: number;
  total_events?: number;
  created_at: string;
  updated_at?: string;
  impact_score?: number;
  key_entities?: string[];
  last_event_at?: string;
  reactivation_count?: number;
}

interface TimelineEvent {
  title: string;
  description: string;
  type: string;
  timestamp: string;
  article_count?: number;
}

interface Stats {
  total: number;
  active: number;
  completed: number;
  paused: number;
  highPriority: number;
}

function DiscoverStorylinesButton({
  domain,
  onDone,
}: {
  domain: string;
  onDone: () => void;
}) {
  const [discovering, setDiscovering] = useState(false);
  const { showSuccess, showError, showInfo } = useNotification();

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const result = await apiService.discoverStorylines({ save: true }, domain);
      if (
        result?.success &&
        (result?.saved_storylines?.length || result?.summary?.storylines_saved)
      ) {
        const count =
          result?.saved_storylines?.length ??
          result?.summary?.storylines_saved ??
          0;
        showSuccess(`Discovery complete: ${count} new storyline(s) created.`);
        onDone();
      } else if (result?.success && result?.summary?.clusters_found === 0) {
        showInfo(
          'No article clusters found. Add more articles or try again later.'
        );
      } else if (result?.error) {
        showError(result.error);
      } else {
        showSuccess('Discovery finished. Refreshing list.');
        onDone();
      }
    } catch (e) {
      showError(getUserFriendlyError(e as Error));
    } finally {
      setDiscovering(false);
    }
  };

  return (
    <Button
      variant='contained'
      startIcon={
        discovering ? <CircularProgress size={18} /> : <AutoAwesomeIcon />
      }
      onClick={handleDiscover}
      disabled={discovering}
    >
      {discovering
        ? 'Discovering… (full backlog, may take a while)'
        : 'Discover storylines now'}
    </Button>
  );
}

const Storylines: React.FC = () => {
  const navigate = useNavigate();
  const { navigateToDomain } = useDomainNavigation();
  const { domain } = useDomainRoute();
  const { showSuccess, showError, showInfo, NotificationComponent } =
    useNotification();

  const [storylines, setStorylines] = useState<Storyline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [sortBy, setSortBy] = useState('updated_at');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalStorylines, setTotalStorylines] = useState(0);
  const [bookmarkedStorylines, setBookmarkedStorylines] = useState<Set<number>>(
    new Set()
  );
  const [stats, setStats] = useState<Stats>({
    total: 0,
    active: 0,
    completed: 0,
    paused: 0,
    highPriority: 0,
  });

  // Timeline dialog state
  const [timelineDialogOpen, setTimelineDialogOpen] = useState(false);
  const [selectedStoryline, setSelectedStoryline] = useState<Storyline | null>(
    null
  );
  const [timelineData, setTimelineData] = useState<TimelineEvent[]>([]);

  // Management dialog state
  const [managementDialogOpen, setManagementDialogOpen] = useState(false);
  const [selectedStorylineForEdit, setSelectedStorylineForEdit] =
    useState<Storyline | null>(null);

  const loadStorylines = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        page,
        page_size: viewMode === 'grid' ? 12 : 20,
        search: searchQuery || undefined,
        status: filterStatus || undefined,
        category: filterCategory || undefined,
        priority: filterPriority || undefined,
        sort_by: sortBy,
      };

      // Response shape varies by API path; normalize with a loose type here
      const response: any = await apiService.getStorylines(params, domain);

      // Handle response formats: crud returns { data, pagination, domain }; legacy may return { success, data: { storylines, total } }
      let storylinesData: Storyline[] = [];
      const pagination = response.pagination;
      const totalFromPagination = pagination?.total;
      if (response.data && Array.isArray(response.data)) {
        storylinesData = response.data;
        setTotalPages(pagination?.pages ?? 1);
        setTotalStorylines(totalFromPagination ?? storylinesData.length);
      } else if (response.data?.data && Array.isArray(response.data.data)) {
        storylinesData = response.data.data;
        setTotalPages(response.data.pagination?.pages ?? 1);
        setTotalStorylines(
          response.data.pagination?.total ?? storylinesData.length
        );
      } else if (response.success && response.data?.storylines) {
        storylinesData = response.data.storylines || [];
        setTotalPages(
          Math.ceil(
            (response.data.total || 0) / (viewMode === 'grid' ? 12 : 20)
          )
        );
        setTotalStorylines(response.data.total || 0);
      } else {
        storylinesData = [];
        setTotalPages(1);
        setTotalStorylines(0);
      }

      setStorylines(storylinesData);

      // Calculate statistics
      const calculatedStats: Stats = {
        total: storylinesData.length,
        active: storylinesData.filter(s => s.status?.toLowerCase() === 'active')
          .length,
        completed: storylinesData.filter(
          s =>
            s.status?.toLowerCase() === 'completed' ||
            s.status?.toLowerCase() === 'resolved'
        ).length,
        paused: storylinesData.filter(s => s.status?.toLowerCase() === 'paused')
          .length,
        highPriority: storylinesData.filter(
          s => s.priority?.toLowerCase() === 'high'
        ).length,
      };
      setStats(calculatedStats);
    } catch (err: any) {
      console.error('Error loading storylines:', err);
      const errorMsg = getUserFriendlyError(err);
      setError(errorMsg);
      showError(errorMsg);
      setStorylines([]);
    } finally {
      setLoading(false);
    }
  }, [
    page,
    searchQuery,
    filterStatus,
    filterCategory,
    filterPriority,
    sortBy,
    viewMode,
    domain,
  ]);

  // Initial load - only run when dependencies actually change
  useEffect(() => {
    loadStorylines();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    page,
    searchQuery,
    filterStatus,
    filterCategory,
    filterPriority,
    sortBy,
    viewMode,
    domain,
  ]);

  const fetchTimelineData = useCallback(async (storylineId: number) => {
    try {
      const response = await apiService.getStorylineTimeline(storylineId);
      if (response.success) {
        const events = response.data?.timeline_events || [];
        setTimelineData(
          events.map((event: any) => ({
            title: event.title || event.event_title || 'Untitled Event',
            description: event.description || event.event_description || '',
            type: event.event_type || 'Event',
            timestamp:
              event.event_date || event.created_at || new Date().toISOString(),
            article_count: event.source_article_ids?.length || 0,
          }))
        );
      }
    } catch (error: any) {
      console.error('Error fetching timeline data:', error);
      const errorMsg = getUserFriendlyError(error);
      showError(errorMsg);
      setTimelineData([]);
    }
  }, []);

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
    setPage(1);
  };

  const handleFilterChange = (filterType: string, value: string) => {
    switch (filterType) {
      case 'status':
        setFilterStatus(value);
        break;
      case 'category':
        setFilterCategory(value);
        break;
      case 'priority':
        setFilterPriority(value);
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

  const handleCreateStoryline = () => {
    setSelectedStorylineForEdit(null);
    setManagementDialogOpen(true);
  };

  const handleEditStoryline = (storyline: Storyline) => {
    setSelectedStorylineForEdit(storyline);
    setManagementDialogOpen(true);
  };

  const handleStorylineUpdated = () => {
    loadStorylines();
  };

  const handleCloseManagementDialog = () => {
    setManagementDialogOpen(false);
    setSelectedStorylineForEdit(null);
  };

  const toggleBookmark = (storylineId: number) => {
    const newBookmarked = new Set(bookmarkedStorylines);
    if (newBookmarked.has(storylineId)) {
      newBookmarked.delete(storylineId);
    } else {
      newBookmarked.add(storylineId);
    }
    setBookmarkedStorylines(newBookmarked);
  };

  const handleViewTimeline = async (storyline: Storyline) => {
    setSelectedStoryline(storyline);
    await fetchTimelineData(storyline.id);
    setTimelineDialogOpen(true);
  };

  const getStatusColor = (
    status?: string
  ): 'success' | 'warning' | 'info' | 'default' | 'error' => {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'success';
      case 'developing':
        return 'warning';
      case 'dormant':
        return 'warning';
      case 'watching':
        return 'info';
      case 'completed':
      case 'resolved':
      case 'concluded':
        return 'info';
      case 'paused':
        return 'warning';
      case 'archived':
        return 'default';
      default:
        return 'default';
    }
  };

  const getPriorityColor = (
    priority?: string
  ): 'error' | 'warning' | 'success' | 'default' => {
    switch (priority?.toLowerCase()) {
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      case 'low':
        return 'success';
      default:
        return 'default';
    }
  };

  const getCategoryIcon = (category?: string) => {
    switch (category?.toLowerCase()) {
      case 'politics':
        return <PublicIcon />;
      case 'business':
        return <BusinessIcon />;
      case 'technology':
        return <ScienceIcon />;
      case 'health':
        return <PersonIcon />;
      case 'education':
        return <SchoolIcon />;
      case 'employment':
        return <WorkIcon />;
      default:
        return <Article />;
    }
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateText = (text?: string, maxLength: number = 150): string => {
    if (!text) return '';
    return text.length > maxLength
      ? text.substring(0, maxLength) + '...'
      : text;
  };

  const StorylineCard: React.FC<{ storyline: Storyline }> = ({ storyline }) => (
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
            {storyline.title || 'Untitled Storyline'}
          </Typography>
          <IconButton
            size='small'
            onClick={() => toggleBookmark(storyline.id)}
            sx={{ ml: 1 }}
          >
            {bookmarkedStorylines.has(storyline.id) ? (
              <Bookmark color='primary' />
            ) : (
              <BookmarkBorder />
            )}
          </IconButton>
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
          {truncateText(storyline.description || storyline.summary)}
        </Typography>

        <Box display='flex' flexWrap='wrap' gap={1} mb={2}>
          {storyline.status && (
            <Chip
              label={storyline.status}
              color={getStatusColor(storyline.status)}
              size='small'
            />
          )}
          {storyline.category && (
            <Chip
              icon={getCategoryIcon(storyline.category)}
              label={storyline.category}
              color='secondary'
              size='small'
            />
          )}
          {storyline.priority && (
            <Chip
              label={`Priority: ${storyline.priority}`}
              color={getPriorityColor(storyline.priority)}
              size='small'
              variant='outlined'
            />
          )}
          {storyline.impact_score && (
            <Chip
              label={`Impact: ${Math.round(storyline.impact_score * 100)}%`}
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
            <Article fontSize='small' color='action' />
            <Typography variant='caption' color='text.secondary'>
              {storyline.article_count || 0} articles
              {(storyline.total_events ?? 0) > 0 &&
                ` · ${storyline.total_events} events`}
            </Typography>
          </Box>
          <Typography variant='caption' color='text.secondary'>
            Updated: {formatDate(storyline.updated_at || storyline.created_at)}
          </Typography>
        </Box>

        {storyline.key_entities && storyline.key_entities.length > 0 && (
          <Box mt={1}>
            <Typography
              variant='caption'
              color='text.secondary'
              display='block'
            >
              Key Entities: {storyline.key_entities.slice(0, 3).join(', ')}
              {storyline.key_entities.length > 3 &&
                ` +${storyline.key_entities.length - 3} more`}
            </Typography>
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button
          size='small'
          startIcon={<Visibility />}
          onClick={() => navigateToDomain(`/storylines/${storyline.id}`)}
        >
          View Details
        </Button>
        <Button
          size='small'
          startIcon={<TimelineIcon />}
          onClick={() => handleViewTimeline(storyline)}
        >
          Timeline
        </Button>
        <Button size='small' startIcon={<ShareIcon />}>
          Share
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Tooltip title='Edit Storyline'>
          <IconButton
            size='small'
            onClick={() => handleEditStoryline(storyline)}
            color='primary'
          >
            <EditIcon />
          </IconButton>
        </Tooltip>
      </CardActions>
    </Card>
  );

  const StorylineListItem: React.FC<{ storyline: Storyline }> = ({
    storyline,
  }) => (
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
      <Box
        display='flex'
        alignItems='center'
        justifyContent='space-between'
        width='100%'
      >
        <ListItemText
          primary={
            <Box display='flex' alignItems='center' gap={1} mb={1}>
              <Typography variant='h6' sx={{ flexGrow: 1 }}>
                {storyline.title || 'Untitled Storyline'}
              </Typography>
              <Box display='flex' gap={1}>
                {storyline.status && (
                  <Chip
                    label={storyline.status}
                    color={getStatusColor(storyline.status)}
                    size='small'
                  />
                )}
                {storyline.category && (
                  <Chip
                    icon={getCategoryIcon(storyline.category)}
                    label={storyline.category}
                    color='secondary'
                    size='small'
                  />
                )}
                {storyline.priority && (
                  <Chip
                    label={storyline.priority}
                    color={getPriorityColor(storyline.priority)}
                    size='small'
                    variant='outlined'
                  />
                )}
                {storyline.impact_score && (
                  <Chip
                    label={`${Math.round(storyline.impact_score * 100)}%`}
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
                {truncateText(storyline.description || storyline.summary, 200)}
              </Typography>
              <Box display='flex' alignItems='center' gap={2}>
                <Box display='flex' alignItems='center' gap={0.5}>
                  <Article fontSize='small' />
                  <Typography variant='caption'>
                    {storyline.article_count || 0} articles
                  </Typography>
                </Box>
                <Typography variant='caption'>
                  Updated:{' '}
                  {formatDate(storyline.updated_at || storyline.created_at)}
                </Typography>
                {storyline.key_entities &&
                  storyline.key_entities.length > 0 && (
                    <Typography variant='caption' color='text.secondary'>
                      Entities: {storyline.key_entities.slice(0, 3).join(', ')}
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
              onClick={() => toggleBookmark(storyline.id)}
            >
              {bookmarkedStorylines.has(storyline.id) ? (
                <Bookmark color='primary' />
              ) : (
                <BookmarkBorder />
              )}
            </IconButton>
            <Button
              size='small'
              startIcon={<Visibility />}
              onClick={() => navigateToDomain(`/storylines/${storyline.id}`)}
            >
              Details
            </Button>
            <Button
              size='small'
              startIcon={<TimelineIcon />}
              onClick={() => handleViewTimeline(storyline)}
            >
              Timeline
            </Button>
          </Box>
        </ListItemSecondaryAction>
      </Box>
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
        <Box display='flex' alignItems='center' gap={2}>
          <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
            Storylines
          </Typography>
          <Chip
            label={formatDomainLabel(domain)}
            size='small'
            variant='outlined'
            color='primary'
          />
        </Box>
        <Box display='flex' gap={2} alignItems='center'>
          <Button
            variant='contained'
            startIcon={<AddIcon />}
            onClick={handleCreateStoryline}
            sx={{ mr: 2 }}
          >
            Create Storyline
          </Button>
          <Tooltip title='Refresh Storylines'>
            <span>
              <IconButton onClick={handleRefresh} disabled={loading}>
                <Refresh />
              </IconButton>
            </span>
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

      {/* Statistics Overview */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='primary'>
                {stats.total}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Total Storylines
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='success.main'>
                {stats.active}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Active
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='info.main'>
                {stats.completed}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Completed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='warning.main'>
                {stats.paused}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Paused
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='error.main'>
                {stats.highPriority}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                High Priority
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant='h6' color='primary'>
                {stats.total > 0
                  ? Math.round((stats.active / stats.total) * 100)
                  : 0}
                %
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                Active Rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems='center'>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder='Search storylines by title or description...'
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
                <MenuItem value='developing'>Developing</MenuItem>
                <MenuItem value='dormant'>Dormant</MenuItem>
                <MenuItem value='watching'>Watching</MenuItem>
                <MenuItem value='concluded'>Concluded</MenuItem>
                <MenuItem value='completed'>Completed</MenuItem>
                <MenuItem value='resolved'>Resolved</MenuItem>
                <MenuItem value='paused'>Paused</MenuItem>
                <MenuItem value='archived'>Archived</MenuItem>
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
                <MenuItem value='politics'>Politics</MenuItem>
                <MenuItem value='business'>Business</MenuItem>
                <MenuItem value='technology'>Technology</MenuItem>
                <MenuItem value='health'>Health</MenuItem>
                <MenuItem value='education'>Education</MenuItem>
                <MenuItem value='employment'>Employment</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={filterPriority}
                label='Priority'
                onChange={e => handleFilterChange('priority', e.target.value)}
              >
                <MenuItem value=''>All Priority</MenuItem>
                <MenuItem value='high'>High</MenuItem>
                <MenuItem value='medium'>Medium</MenuItem>
                <MenuItem value='low'>Low</MenuItem>
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
                <MenuItem value='updated_at'>Last Updated</MenuItem>
                <MenuItem value='created_at'>Created Date</MenuItem>
                <MenuItem value='impact_score'>Impact Score</MenuItem>
                <MenuItem value='article_count'>Article Count</MenuItem>
                <MenuItem value='priority'>Priority</MenuItem>
                <MenuItem value='title'>Title</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
        <Box mt={2} display='flex' justifyContent='flex-end'>
          <Button
            variant='outlined'
            startIcon={<FilterList />}
            onClick={() => {
              setSearchQuery('');
              setFilterStatus('');
              setFilterCategory('');
              setFilterPriority('');
              setSortBy('updated_at');
              setPage(1);
            }}
          >
            Clear Filters
          </Button>
        </Box>
      </Paper>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Storylines Display */}
      {storylines.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <TimelineIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant='h6' color='text.secondary' gutterBottom>
            No storylines found
            {domain ? ` for ${domainName || domain}` : ''}
          </Typography>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
            {searchQuery || filterStatus || filterCategory || filterPriority
              ? 'Try adjusting your search criteria or filters'
              : 'Storylines are per domain. Get storylines in three ways:'}
          </Typography>
          {!searchQuery &&
            !filterStatus &&
            !filterCategory &&
            !filterPriority && (
              <>
                <Box
                  component='ul'
                  sx={{
                    textAlign: 'left',
                    maxWidth: 480,
                    mx: 'auto',
                    mb: 2,
                    pl: 2.5,
                  }}
                >
                  <li>
                    <strong>Discover now</strong> — AI clusters articles from the
                    full backlog (newest-first, capped) into storylines. Can take
                    much longer than a quick weekly scan; Ollama must stay up.
                  </li>
                  <li>
                    <strong>Create one</strong> — Go to{' '}
                    <strong>Story Management</strong> and add a storyline, then
                    add articles or enable automation.
                  </li>
                  <li>
                    <strong>Auto-discovery</strong> — Scheduled job uses the same
                    full-backlog window per domain (not a 7-day slice).
                  </li>
                </Box>
                <DiscoverStorylinesButton
                  domain={domain}
                  onDone={loadStorylines}
                />
              </>
            )}
        </Paper>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {storylines.map(storyline => (
                <Grid item xs={12} sm={6} md={4} key={storyline.id}>
                  <StorylineCard storyline={storyline} />
                </Grid>
              ))}
            </Grid>
          ) : (
            <List>
              {storylines.map(storyline => (
                <StorylineListItem key={storyline.id} storyline={storyline} />
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

          {/* Results Summary */}
          <Box mt={2}>
            <Typography variant='body2' color='text.secondary'>
              Showing {storylines.length} of {totalStorylines} storylines
            </Typography>
          </Box>
        </>
      )}

      {/* AI Analysis Features */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant='h6' gutterBottom>
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Advanced AI Analysis Features
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}>
            <Box textAlign='center'>
              <AutoAwesomeIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Multi-Perspective Analysis</Typography>
              <Typography variant='body2' color='text.secondary'>
                Analyze storylines from multiple viewpoints and sources
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={3}>
            <Box textAlign='center'>
              <AssessmentIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Impact Assessment</Typography>
              <Typography variant='body2' color='text.secondary'>
                Evaluate potential impacts across different dimensions
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={3}>
            <Box textAlign='center'>
              <HistoryIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Historical Context</Typography>
              <Typography variant='body2' color='text.secondary'>
                Connect current events to historical patterns
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={3}>
            <Box textAlign='center'>
              <AutoAwesomeIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Predictive Analysis</Typography>
              <Typography variant='body2' color='text.secondary'>
                Forecast future developments and trends
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Timeline Dialog */}
      <Dialog
        open={timelineDialogOpen}
        onClose={() => setTimelineDialogOpen(false)}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>
          <Box display='flex' alignItems='center' gap={1}>
            <TimelineIcon />
            Timeline: {selectedStoryline?.title}
          </Box>
        </DialogTitle>
        <DialogContent>
          {timelineData.length > 0 ? (
            <Stepper orientation='vertical'>
              {timelineData.map((event, index) => (
                <Step key={index} active>
                  <StepLabel>
                    <Box display='flex' alignItems='center' gap={1}>
                      <Typography variant='subtitle1'>{event.title}</Typography>
                      <Chip label={event.type} size='small' color='primary' />
                    </Box>
                  </StepLabel>
                  <StepContent>
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ mb: 1 }}
                    >
                      {event.description}
                    </Typography>
                    <Box display='flex' alignItems='center' gap={1}>
                      <Chip
                        icon={<Schedule />}
                        label={formatDate(event.timestamp)}
                        size='small'
                        variant='outlined'
                      />
                      {event.article_count && event.article_count > 0 && (
                        <Chip
                          icon={<Article />}
                          label={`${event.article_count} articles`}
                          size='small'
                          variant='outlined'
                        />
                      )}
                    </Box>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          ) : (
            <Typography color='text.secondary'>
              No timeline data available for this storyline.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTimelineDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Storyline Management Dialog */}
      <StorylineManagementDialog
        open={managementDialogOpen}
        onClose={handleCloseManagementDialog}
        storyline={selectedStorylineForEdit}
        domain={domain}
        onStorylineUpdated={handleStorylineUpdated}
      />
    </Box>
  );
};

export default Storylines;
