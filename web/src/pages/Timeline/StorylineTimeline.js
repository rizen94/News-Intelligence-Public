import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  Grid,
  CircularProgress,
  Alert,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  ExpandMore as ExpandMoreIcon,
  Event as EventIcon,
  Security as MilitaryIcon,
  Gavel as GavelIcon,
  LocalHospital as HumanitarianIcon,
  Business as BusinessIcon,
  Public as PublicIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  CalendarToday as CalendarIcon,
  LocationOn as LocationIcon,
  Person as PersonIcon,
  Flag as FlagIcon
} from '@mui/icons-material';
import { useNotifications } from '../../components/Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';

const StorylineTimeline = () => {
  const { storylineId } = useParams();
  const navigate = useNavigate();
  const { showLoading, showSuccess, showError } = useNotifications();
  
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filteredEvents, setFilteredEvents] = useState([]);
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [importanceFilter, setImportanceFilter] = useState(0);
  const [dateRange, setDateRange] = useState({ start: '', end: '' });

  useEffect(() => {
    if (storylineId) {
      fetchTimeline();
    }
  }, [storylineId]);

  useEffect(() => {
    if (timeline) {
      applyFilters();
    }
  }, [timeline, eventTypeFilter, importanceFilter, dateRange]);

  const fetchTimeline = async () => {
    try {
      setLoading(true);
      showLoading('Loading storyline timeline...');

      const response = await newsSystemService.getStorylineTimeline(storylineId);
      
      if (response.success) {
        setTimeline(response.data);
        setFilteredEvents(response.data.recent_events || []);
        showSuccess('Timeline loaded successfully');
      } else {
        throw new Error(response.message || 'Failed to load timeline');
      }
    } catch (error) {
      console.error('Error loading timeline:', error);
      showError('Failed to load storyline timeline');
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    if (!timeline) return;

    let events = [...(timeline.recent_events || [])];
    
    // Filter by event type
    if (eventTypeFilter) {
      events = events.filter(event => 
        event.event_type.toLowerCase().includes(eventTypeFilter.toLowerCase())
      );
    }
    
    // Filter by importance
    if (importanceFilter > 0) {
      events = events.filter(event => event.importance_score >= importanceFilter);
    }
    
    // Filter by date range
    if (dateRange.start) {
      events = events.filter(event => event.event_date >= dateRange.start);
    }
    if (dateRange.end) {
      events = events.filter(event => event.event_date <= dateRange.end);
    }
    
    setFilteredEvents(events);
  };

  const getEventIcon = (eventType) => {
    switch (eventType.toLowerCase()) {
      case 'military': return <MilitaryIcon />;
      case 'diplomatic': return <GavelIcon />;
      case 'humanitarian': return <HumanitarianIcon />;
      case 'business': return <BusinessIcon />;
      case 'political': return <PublicIcon />;
      default: return <EventIcon />;
    }
  };

  const getEventColor = (importance) => {
    if (importance >= 0.8) return 'error';
    if (importance >= 0.6) return 'warning';
    if (importance >= 0.4) return 'info';
    return 'default';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const formatTime = (timeString) => {
    if (!timeString) return '';
    return new Date(`2000-01-01T${timeString}`).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!timeline) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          Timeline not found
        </Alert>
        <Button 
          variant="contained" 
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/storylines')}
          sx={{ mt: 2 }}
        >
          Back to Storylines
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton onClick={() => navigate('/storylines')}>
            <ArrowBackIcon />
          </IconButton>
          <Box>
            <Typography variant="h4" component="h1">
              {timeline.storyline_name} Timeline
            </Typography>
            <Typography variant="subtitle1" color="text.secondary">
              {timeline.total_events} events • {timeline.time_range.start} to {timeline.time_range.end}
            </Typography>
          </Box>
        </Box>
        
        <IconButton onClick={fetchTimeline} color="primary">
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <FilterIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Filters
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Event Type</InputLabel>
                <Select
                  value={eventTypeFilter}
                  onChange={(e) => setEventTypeFilter(e.target.value)}
                  label="Event Type"
                >
                  <MenuItem value="">All Types</MenuItem>
                  <MenuItem value="military">Military</MenuItem>
                  <MenuItem value="diplomatic">Diplomatic</MenuItem>
                  <MenuItem value="humanitarian">Humanitarian</MenuItem>
                  <MenuItem value="business">Business</MenuItem>
                  <MenuItem value="political">Political</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Min Importance</InputLabel>
                <Select
                  value={importanceFilter}
                  onChange={(e) => setImportanceFilter(e.target.value)}
                  label="Min Importance"
                >
                  <MenuItem value={0}>All Events</MenuItem>
                  <MenuItem value={0.4}>Moderate+</MenuItem>
                  <MenuItem value={0.6}>High</MenuItem>
                  <MenuItem value={0.8}>Critical</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Start Date"
                type="date"
                value={dateRange.start}
                onChange={(e) => setDateRange({...dateRange, start: e.target.value})}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="End Date"
                type="date"
                value={dateRange.end}
                onChange={(e) => setDateRange({...dateRange, end: e.target.value})}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        {/* Main Timeline */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Event Timeline ({filteredEvents.length} events)
              </Typography>
              
              {filteredEvents.length === 0 ? (
                <Alert severity="info">
                  No events match the current filters
                </Alert>
              ) : (
                <Box>
                  {filteredEvents.map((event, index) => (
                    <Box key={event.event_id} sx={{ mb: 3, display: 'flex', gap: 2 }}>
                      {/* Timeline dot and connector */}
                      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <Box
                          sx={{
                            width: 40,
                            height: 40,
                            borderRadius: '50%',
                            backgroundColor: getEventColor(event.importance_score) === 'error' ? '#d32f2f' :
                                           getEventColor(event.importance_score) === 'warning' ? '#ed6c02' :
                                           getEventColor(event.importance_score) === 'info' ? '#0288d1' : '#757575',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'white',
                            mb: 1
                          }}
                        >
                          {getEventIcon(event.event_type)}
                        </Box>
                        {index < filteredEvents.length - 1 && (
                          <Box
                            sx={{
                              width: 2,
                              height: 60,
                              backgroundColor: '#e0e0e0',
                              mt: 1
                            }}
                          />
                        )}
                      </Box>
                      
                      {/* Event content */}
                      <Box sx={{ flex: 1 }}>
                        <Card>
                          <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                              <Typography variant="h6" component="h3">
                                {event.title}
                              </Typography>
                              <Box sx={{ display: 'flex', gap: 1 }}>
                                <Chip 
                                  label={event.event_type} 
                                  size="small" 
                                  color={getEventColor(event.importance_score)}
                                />
                                <Chip 
                                  label={`${Math.round(event.importance_score * 100)}%`} 
                                  size="small" 
                                  variant="outlined"
                                />
                              </Box>
                            </Box>
                            
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              {formatDate(event.event_date)} {event.event_time && `• ${formatTime(event.event_time)}`}
                            </Typography>
                            
                            <Typography variant="body2" color="text.secondary" paragraph>
                              {event.description}
                            </Typography>
                            
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                              <Typography variant="caption" color="text.secondary">
                                <FlagIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                                {event.source}
                              </Typography>
                              {event.location && (
                                <Typography variant="caption" color="text.secondary">
                                  <LocationIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                                  {event.location}
                                </Typography>
                              )}
                            </Box>
                            
                            {event.entities && event.entities.length > 0 && (
                              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                                {(event.entities || []).slice(0, 3).map((entity, idx) => (
                                  <Chip 
                                    key={idx}
                                    label={entity} 
                                    size="small" 
                                    variant="outlined"
                                    icon={<PersonIcon />}
                                  />
                                ))}
                                {event.entities.length > 3 && (
                                  <Chip 
                                    label={`+${event.entities.length - 3}`} 
                                    size="small" 
                                    variant="outlined"
                                  />
                                )}
                              </Box>
                            )}
                            
                            {event.tags && event.tags.length > 0 && (
                              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {(event.tags || []).slice(0, 5).map((tag, idx) => (
                                  <Chip 
                                    key={idx}
                                    label={tag} 
                                    size="small" 
                                    variant="outlined"
                                    sx={{ fontSize: '0.7rem' }}
                                  />
                                ))}
                                {event.tags.length > 5 && (
                                  <Chip 
                                    label={`+${event.tags.length - 5}`} 
                                    size="small" 
                                    variant="outlined"
                                    sx={{ fontSize: '0.7rem' }}
                                  />
                                )}
                              </Box>
                            )}
                          </CardContent>
                        </Card>
                      </Box>
                    </Box>
                  ))}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={4}>
          {/* Key Milestones */}
          {timeline.key_milestones && timeline.key_milestones.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Key Milestones
                </Typography>
                <List dense>
                  {(timeline.key_milestones || []).slice(0, 5).map((milestone, index) => (
                    <ListItem key={milestone.event_id} sx={{ px: 0 }}>
                      <ListItemIcon>
                        <Box
                          sx={{
                            width: 24,
                            height: 24,
                            borderRadius: '50%',
                            backgroundColor: getEventColor(milestone.importance_score) === 'error' ? '#d32f2f' :
                                           getEventColor(milestone.importance_score) === 'warning' ? '#ed6c02' :
                                           getEventColor(milestone.importance_score) === 'info' ? '#0288d1' : '#757575',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'white'
                          }}
                        >
                          {getEventIcon(milestone.event_type)}
                        </Box>
                      </ListItemIcon>
                      <ListItemText
                        primary={milestone.title}
                        secondary={
                          <Box>
                            <Typography variant="caption" display="block">
                              {formatDate(milestone.event_date)}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {milestone.event_type} • {Math.round(milestone.importance_score * 100)}%
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}

          {/* Timeline Periods */}
          {timeline.periods && timeline.periods.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Timeline Periods
                </Typography>
                {(timeline.periods || []).map((period, index) => (
                  <Accordion key={period.period} sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', mr: 2 }}>
                        <Typography variant="subtitle2">
                          {period.period}
                        </Typography>
                        <Chip 
                          label={`${period.event_count} events`} 
                          size="small" 
                          color="primary"
                        />
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography variant="body2" paragraph>
                        {period.summary}
                      </Typography>
                      {period.key_events && period.key_events.length > 0 && (
                        <List dense>
                          {(period.key_events || []).map((event, idx) => (
                            <ListItem key={event.event_id} sx={{ px: 0 }}>
                              <ListItemIcon>
                                {getEventIcon(event.event_type)}
                              </ListItemIcon>
                              <ListItemText
                                primary={event.title}
                                secondary={`${formatDate(event.event_date)} • ${event.event_type}`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      )}
                    </AccordionDetails>
                  </Accordion>
                ))}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default StorylineTimeline;
