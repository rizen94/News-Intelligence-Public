import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  Divider,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Article as ArticleIcon,
  Notifications as NotificationsIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../../components/Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';

const MorningBriefing = () => {
  const [loading, setLoading] = useState(true);
  const [storylines, setStorylines] = useState([]);
  const [newContent, setNewContent] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const navigate = useNavigate();
  const { showSuccess, showError, showLoading } = useNotifications();

  useEffect(() => {
    fetchBriefingData();
  }, []);

  const fetchBriefingData = async () => {
    try {
      showLoading('Loading your morning briefing...');
      
      // Fetch real storyline data
      const storylinesResponse = await newsSystemService.getActiveStories();
      
      if (storylinesResponse.success) {
        // Transform the data to match the expected format
        const transformedStorylines = storylinesResponse.data.map(storyline => ({
          id: storyline.story_id,
          story_id: storyline.story_id,
          title: storyline.name,
          category: 'Global Events', // Default category
          lastUpdate: new Date(storyline.updated_at).toLocaleString(),
          newEvents: 0, // This would need to be calculated from timeline events
          totalArticles: 0, // This would need to be calculated from articles
          summary: storyline.description,
          priority: storyline.priority_level > 5 ? 'high' : storyline.priority_level > 3 ? 'medium' : 'low',
          status: storyline.is_active ? 'active' : 'inactive'
        }));
        
        setStorylines(transformedStorylines);
      } else {
        throw new Error('Failed to fetch storylines');
      }

      // Fetch real new content from articles
      const articlesResponse = await newsSystemService.getArticles({ per_page: 10, sort_by: 'created_at', sort_order: 'desc' });
      
      if (articlesResponse.success) {
        const transformedNewContent = articlesResponse.data.articles.map(article => ({
          id: article.id,
          title: article.title,
          summary: article.summary || article.content?.substring(0, 150) + '...',
          sources: [article.source],
          clusterSize: 1, // This would need to be calculated from clustering
          category: article.category || 'General'
        }));
        setNewContent(transformedNewContent);
      } else {
        setNewContent([]);
      }

      // Fetch real alerts from storyline timeline events
      if (storylinesResponse.success && storylinesResponse.data.length > 0) {
        const firstStoryline = storylinesResponse.data[0];
        const timelineResponse = await newsSystemService.getStorylineTimeline(firstStoryline.story_id);
        
        if (timelineResponse.success && timelineResponse.data.recent_events) {
          const transformedAlerts = timelineResponse.data.recent_events.map(event => ({
            id: event.event_id,
            type: 'timeline_event',
            message: `${event.title} - New timeline event added`,
            timestamp: new Date(event.created_at).toLocaleString(),
            priority: event.importance_score > 0.7 ? 'high' : event.importance_score > 0.4 ? 'medium' : 'low'
          }));
          setAlerts(transformedAlerts);
        } else {
          setAlerts([]);
        }
      } else {
        setAlerts([]);
      }

      setLastUpdated(new Date());
      showSuccess('Morning briefing loaded successfully');
    } catch (error) {
      showError('Failed to load briefing data');
      console.error('Error fetching briefing data:', error);
    } finally {
      setLoading(false);
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

  const getCategoryColor = (category) => {
    switch (category) {
      case 'Global Events': return 'primary';
      case 'Business': return 'secondary';
      case 'Politics': return 'error';
      case 'Technology': return 'info';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={60} />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Preparing your morning briefing...
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          Morning Briefing
        </Typography>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          {new Date().toLocaleDateString('en-US', { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
          })}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </Typography>
      </Box>

      {/* Alerts */}
      {alerts.length > 0 && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
            <NotificationsIcon sx={{ mr: 1 }} />
            Important Updates
          </Typography>
          {alerts.map((alert) => (
            <Alert 
              key={alert.id} 
              severity={alert.priority === 'high' ? 'error' : 'info'} 
              sx={{ mb: 1 }}
            >
              <Typography variant="body2">
                {alert.message}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {alert.timestamp}
              </Typography>
            </Alert>
          ))}
        </Box>
      )}

      <Grid container spacing={3}>
        {/* Storylines Section */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h5" component="h2" sx={{ display: 'flex', alignItems: 'center' }}>
                  <TimelineIcon sx={{ mr: 1 }} />
                  Your Storylines
                </Typography>
                <Button 
                  variant="outlined" 
                  startIcon={<RefreshIcon />}
                  onClick={fetchBriefingData}
                >
                  Refresh
                </Button>
              </Box>
              
              <Grid container spacing={2}>
                {storylines.map((storyline) => (
                  <Grid item xs={12} sm={6} key={storyline.id}>
                    <Card 
                      variant="outlined" 
                      sx={{ 
                        cursor: 'pointer',
                        '&:hover': { boxShadow: 2 },
                        borderLeft: `4px solid ${
                          storyline.priority === 'high' ? '#d32f2f' : 
                          storyline.priority === 'medium' ? '#ed6c02' : '#2e7d32'
                        }`
                      }}
                      onClick={() => navigate(`/storylines/${storyline.story_id}`)}
                    >
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                          <Typography variant="h6" component="h3" noWrap>
                            {storyline.title}
                          </Typography>
                          <Chip 
                            label={storyline.priority} 
                            size="small" 
                            color={getPriorityColor(storyline.priority)}
                          />
                        </Box>
                        
                        <Chip 
                          label={storyline.category} 
                          size="small" 
                          color={getCategoryColor(storyline.category)}
                          sx={{ mb: 1 }}
                        />
                        
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {storyline.summary}
                        </Typography>
                        
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="caption" color="text.secondary">
                            {storyline.totalArticles} articles • {storyline.newEvents} new events
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Updated {storyline.lastUpdate}
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* New Content Section */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h5" component="h2" sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TrendingUpIcon sx={{ mr: 1 }} />
                New Content
              </Typography>
              
              <List>
                {newContent.map((content) => (
                  <React.Fragment key={content.id}>
                    <ListItem 
                      sx={{ 
                        cursor: 'pointer',
                        '&:hover': { backgroundColor: 'action.hover' },
                        borderRadius: 1
                      }}
                      onClick={() => navigate(`/articles/${content.id}`)}
                    >
                      <ListItemAvatar>
                        <Avatar sx={{ bgcolor: 'primary.main' }}>
                          <ArticleIcon />
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={
                          <Typography variant="subtitle2" noWrap>
                            {content.title}
                          </Typography>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary" noWrap>
                              {content.summary}
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                              <Chip 
                                label={`${content.clusterSize} sources`} 
                                size="small" 
                                variant="outlined"
                              />
                              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                                {content.sources.slice(0, 2).join(', ')}
                                {content.sources.length > 2 && ` +${content.sources.length - 2} more`}
                              </Typography>
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                    <Divider />
                  </React.Fragment>
                ))}
              </List>
              
              <Button 
                fullWidth 
                variant="outlined" 
                sx={{ mt: 2 }}
                onClick={() => navigate('/discover')}
              >
                View All New Content
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MorningBriefing;
