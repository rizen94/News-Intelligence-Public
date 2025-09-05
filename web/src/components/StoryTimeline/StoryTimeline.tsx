import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Button,
  LinearProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Grid
} from '@mui/material';
import {
  ExpandMore,
  Timeline,
  Article,
  TrendingUp,
  Psychology,
  CheckCircle,
  Warning,
  Error,
  Info
} from '@mui/icons-material';

interface StoryTimelineProps {
  storyId?: string;
  onStorySelect?: (storyId: string) => void;
}

interface StoryData {
  id: number;
  story_id: string;
  title: string;
  summary: string;
  status: 'breaking' | 'developing' | 'resolved' | 'archived';
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed';
  impact_level: 'low' | 'medium' | 'high' | 'critical';
  confidence_score: number;
  sources_count: number;
  last_updated: string;
  created_at: string;
  updated_at: string;
}

interface TimelineEvent {
  id: number;
  story_timeline_id: number;
  event_title: string;
  event_description: string;
  event_date: string;
  event_type: 'development' | 'milestone' | 'breaking' | 'update';
  source_url: string;
  source_title: string;
  created_at: string;
}

const StoryTimeline: React.FC<StoryTimelineProps> = ({ storyId, onStorySelect }) => {
  const [stories, setStories] = useState<StoryData[]>([]);
  const [selectedStory, setSelectedStory] = useState<StoryData | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStories = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/stories/timelines/');
      const data = await response.json();
      
      if (data.success) {
        setStories(data.data || []);
      } else {
        setError(data.message || 'Failed to load stories');
      }
    } catch (err) {
      setError('Failed to connect to backend API');
      console.error('Error loading stories:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadTimelineEvents = async (timelineId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/stories/events/?timeline_id=${timelineId}`);
      const data = await response.json();
      
      if (data.success) {
        setTimelineEvents(data.data || []);
      }
    } catch (err) {
      console.error('Error loading timeline events:', err);
    }
  };

  useEffect(() => {
    loadStories();
  }, []);

  useEffect(() => {
    if (selectedStory) {
      loadTimelineEvents(selectedStory.id);
    }
  }, [selectedStory]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'breaking': return 'error';
      case 'developing': return 'warning';
      case 'resolved': return 'success';
      case 'archived': return 'default';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'breaking': return <Error />;
      case 'developing': return <Warning />;
      case 'resolved': return <CheckCircle />;
      case 'archived': return <Info />;
      default: return <Info />;
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'success';
      case 'negative': return 'error';
      case 'neutral': return 'default';
      case 'mixed': return 'warning';
      default: return 'default';
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleStorySelect = (story: StoryData) => {
    setSelectedStory(story);
    onStorySelect?.(story.story_id);
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Timeline sx={{ mr: 1 }} />
            <Typography variant="h6">Story Timelines</Typography>
          </Box>
          <LinearProgress />
          <Typography variant="body2" sx={{ mt: 1 }}>
            Loading story timelines...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Timeline sx={{ mr: 1 }} />
            <Typography variant="h6">Story Timelines</Typography>
          </Box>
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
          <Button variant="outlined" onClick={loadStories}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box>
      {/* Stories List */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Timeline sx={{ mr: 1 }} />
            <Typography variant="h6">Active Stories</Typography>
          </Box>
          
          {stories.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No active stories found
            </Typography>
          ) : (
            <Grid container spacing={2}>
              {stories.map((story) => (
                <Grid item xs={12} md={6} key={story.id}>
                  <Card 
                    sx={{ 
                      cursor: 'pointer',
                      border: selectedStory?.id === story.id ? 2 : 1,
                      borderColor: selectedStory?.id === story.id ? 'primary.main' : 'divider',
                      '&:hover': { boxShadow: 4 }
                    }}
                    onClick={() => handleStorySelect(story)}
                  >
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="h6" sx={{ flexGrow: 1, mr: 1 }}>
                          {story.title}
                        </Typography>
                        <Chip
                          icon={getStatusIcon(story.status)}
                          label={story.status}
                          color={getStatusColor(story.status)}
                          size="small"
                        />
                      </Box>
                      
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {story.summary}
                      </Typography>
                      
                      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                        <Chip
                          label={`${story.sentiment} sentiment`}
                          color={getSentimentColor(story.sentiment)}
                          size="small"
                        />
                        <Chip
                          label={`${story.impact_level} impact`}
                          color={getImpactColor(story.impact_level)}
                          size="small"
                        />
                        <Chip
                          label={`${Math.round(story.confidence_score * 100)}% confidence`}
                          color="primary"
                          size="small"
                        />
                      </Box>
                      
                      <Typography variant="caption" color="text.secondary">
                        Last updated: {formatDate(story.last_updated)}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </CardContent>
      </Card>

      {/* Timeline Events */}
      {selectedStory && (
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Article sx={{ mr: 1 }} />
              <Typography variant="h6">
                Timeline: {selectedStory.title}
              </Typography>
            </Box>
            
            {timelineEvents.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No timeline events available for this story
              </Typography>
            ) : (
              <List>
                {timelineEvents.map((event, index) => (
                  <React.Fragment key={event.id}>
                    <ListItem alignItems="flex-start">
                      <ListItemIcon>
                        <Box
                          sx={{
                            width: 40,
                            height: 40,
                            borderRadius: '50%',
                            backgroundColor: 'primary.main',
                            color: 'white',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.875rem',
                            fontWeight: 'bold'
                          }}
                        >
                          {index + 1}
                        </Box>
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                              {event.event_title}
                            </Typography>
                            <Chip
                              label={event.event_type}
                              size="small"
                              color="primary"
                              variant="outlined"
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              {event.event_description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatDate(event.event_date)}
                            </Typography>
                            {event.source_url && (
                              <Typography variant="caption" color="primary" sx={{ ml: 1 }}>
                                <a href={event.source_url} target="_blank" rel="noopener noreferrer">
                                  {event.source_title || 'View Source'}
                                </a>
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < timelineEvents.length - 1 && <Divider variant="inset" component="li" />}
                  </React.Fragment>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default StoryTimeline;