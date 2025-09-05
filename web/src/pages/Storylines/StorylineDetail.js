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
  Divider,
  CircularProgress,
  Alert,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Article as ArticleIcon,
  Schedule as ScheduleIcon,
  Flag as FlagIcon,
  LocationOn as LocationIcon,
  Person as PersonIcon,
  Settings as SettingsIcon,
  Timeline as TimelineIcon
} from '@mui/icons-material';
import { useNotifications } from '../../components/Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';
import EditStorylineDialog from '../../components/EditStorylineDialog/EditStorylineDialog';

const StorylineDetail = () => {
  const { storylineId } = useParams();
  const navigate = useNavigate();
  const { showLoading, showSuccess, showError } = useNotifications();
  
  const [storyline, setStoryline] = useState(null);
  const [storyContent, setStoryContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  useEffect(() => {
    if (storylineId) {
      fetchStoryline();
    }
  }, [storylineId]);

  const fetchStoryline = async () => {
    try {
      setLoading(true);
      showLoading('Loading storyline details...');

      const response = await newsSystemService.getStorylineTimeline(storylineId);
      
      if (response.success) {
        setStoryline(response.data);
        await fetchStoryContent(response.data);
        showSuccess('Storyline loaded successfully');
      } else {
        throw new Error(response.message || 'Failed to load storyline');
      }
    } catch (error) {
      console.error('Error loading storyline:', error);
      showError('Failed to load storyline details');
    } finally {
      setLoading(false);
    }
  };

  const fetchStoryContent = async (storylineData) => {
    try {
      // Get articles related to this storyline
      const articlesResponse = await newsSystemService.getArticles({
        per_page: 50,
        search: storylineData.storyline_name
      });
      
      if (articlesResponse.success && articlesResponse.data.articles) {
        // Generate a comprehensive story summary from the articles
        const articles = articlesResponse.data.articles;
        const storyContent = generateStoryContent(storylineData, articles);
        setStoryContent(storyContent);
      }
    } catch (error) {
      console.error('Error fetching story content:', error);
      // Set a placeholder if we can't fetch content
      setStoryContent({
        overview: storylineData.description,
        keyEvents: [],
        timeline: [],
        sources: []
      });
    }
  };

  const generateStoryContent = (storyline, articles) => {
    // Sort articles by published date
    const sortedArticles = articles.sort((a, b) => new Date(b.published_date) - new Date(a.published_date));
    
    // Extract key events from articles
    const keyEvents = sortedArticles.slice(0, 10).map(article => ({
      title: article.title,
      date: article.published_date,
      summary: article.summary || article.content?.substring(0, 200) + '...',
      source: article.source,
      importance: article.engagement_score || 0.5
    }));

    // Create timeline
    const timeline = sortedArticles.map(article => ({
      date: article.published_date,
      event: article.title,
      source: article.source
    }));

    // Extract sources
    const sources = [...new Set(articles.map(article => article.source))];

    return {
      overview: `Storyline: ${storyline.storyline_name}`,
      keyEvents,
      timeline,
      sources,
      totalArticles: articles.length,
      lastUpdated: storyline.updated_at || new Date().toISOString()
    };
  };

  const handleEdit = () => {
    setEditDialogOpen(true);
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this storyline?')) {
      try {
        showLoading('Deleting storyline...');
        
        const response = await newsSystemService.deleteStoryline(storylineId);
        
        if (response.success) {
          showSuccess('Storyline deleted successfully');
          navigate('/storylines');
        } else {
          throw new Error(response.message || 'Failed to delete storyline');
        }
      } catch (error) {
        console.error('Error deleting storyline:', error);
        showError('Failed to delete storyline');
      }
    }
  };

  const handleEditSuccess = () => {
    fetchStoryline();
    setEditDialogOpen(false);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getPriorityColor = (priority) => {
    if (priority >= 8) return 'error';
    if (priority >= 5) return 'warning';
    return 'success';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!storyline) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          Storyline not found
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
              {storyline.storyline_name}
            </Typography>
            <Typography variant="subtitle1" color="text.secondary">
              Storyline Details
            </Typography>
          </Box>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="View Timeline">
            <IconButton 
              onClick={() => navigate(`/storylines/${storylineId}/timeline`)} 
              color="primary"
            >
              <TimelineIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit Storyline">
            <IconButton onClick={handleEdit} color="primary">
              <EditIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete Storyline">
            <IconButton onClick={handleDelete} color="error">
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Main Content */}
        <Grid item xs={12} md={8}>
          {/* Story Overview */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Story Overview
              </Typography>
              <Typography variant="body1" paragraph>
                {storyContent?.overview || `Storyline: ${storyline.storyline_name}`}
              </Typography>
              {storyContent && (
                <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                  <Chip 
                    label={`${storyContent.totalArticles} Articles`} 
                    size="small" 
                    color="primary" 
                    variant="outlined"
                  />
                  <Chip 
                    label={`${storyContent.sources.length} Sources`} 
                    size="small" 
                    color="secondary" 
                    variant="outlined"
                  />
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Key Events */}
          {storyContent && storyContent.keyEvents && storyContent.keyEvents.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Key Events
                </Typography>
                <List>
                  {(storyContent.keyEvents || []).map((event, index) => (
                    <ListItem key={index} sx={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mb: 1 }}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          {event.title}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <Chip 
                            label={event.source} 
                            size="small" 
                            variant="outlined"
                          />
                          <Typography variant="caption" color="text.secondary">
                            {new Date(event.date).toLocaleDateString()}
                          </Typography>
                        </Box>
                      </Box>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {event.summary}
                      </Typography>
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          )}

          {/* Recent Timeline */}
          {storyContent && storyContent.timeline && storyContent.timeline.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Recent Timeline
                </Typography>
                <List dense>
                  {(storyContent.timeline || []).slice(0, 10).map((item, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        <ArticleIcon />
                      </ListItemIcon>
                      <ListItemText 
                        primary={item.event}
                        secondary={
                          <Box>
                            <Typography variant="caption" display="block">
                              {new Date(item.date).toLocaleDateString()} • {item.source}
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

          {/* Keywords */}
          {storyline.keywords && storyline.keywords.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Keywords
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {(storyline.keywords || []).map((keyword, index) => (
                    <Chip 
                      key={index}
                      label={keyword} 
                      variant="outlined"
                      size="small"
                    />
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Entities */}
          {storyline.entities && storyline.entities.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Key Entities
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {(storyline.entities || []).map((entity, index) => (
                    <Chip 
                      key={index}
                      label={entity} 
                      variant="outlined"
                      size="small"
                      icon={<PersonIcon />}
                    />
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}

          {/* Geographic Regions */}
          {storyline.geographic_regions && storyline.geographic_regions.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Geographic Regions
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {(storyline.geographic_regions || []).map((region, index) => (
                    <Chip 
                      key={index}
                      label={region} 
                      variant="outlined"
                      size="small"
                      icon={<LocationIcon />}
                    />
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={4}>
          {/* Status & Priority */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Status & Priority
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Status:</Typography>
                  <Chip 
                    label={storyline.is_active ? 'Active' : 'Inactive'} 
                    color={storyline.is_active ? 'success' : 'default'}
                    size="small"
                  />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Priority:</Typography>
                  <Chip 
                    label={`Level ${storyline.priority_level}`} 
                    color={getPriorityColor(storyline.priority_level)}
                    size="small"
                  />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Auto-Enhance:</Typography>
                  <Chip 
                    label={storyline.auto_enhance ? 'Enabled' : 'Disabled'} 
                    color={storyline.auto_enhance ? 'success' : 'default'}
                    size="small"
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Configuration */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Configuration
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemIcon>
                    <ArticleIcon />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Max Articles/Day" 
                    secondary={storyline.max_articles_per_day} 
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <FlagIcon />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Quality Threshold" 
                    secondary={`${Math.round(storyline.quality_threshold * 100)}%`} 
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>

          {/* Sources */}
          {storyContent && storyContent.sources && storyContent.sources.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Sources ({(storyContent.sources || []).length})
                </Typography>
                <List dense>
                  {(storyContent.sources || []).slice(0, 5).map((source, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        <FlagIcon />
                      </ListItemIcon>
                      <ListItemText 
                        primary={source}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItem>
                  ))}
                  {storyContent.sources.length > 5 && (
                    <ListItem>
                      <ListItemText 
                        primary={`+${storyContent.sources.length - 5} more sources`}
                        primaryTypographyProps={{ variant: 'caption', color: 'text.secondary' }}
                      />
                    </ListItem>
                  )}
                </List>
              </CardContent>
            </Card>
          )}

          {/* Timeline */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Timeline
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemIcon>
                    <ScheduleIcon />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Created" 
                    secondary={formatDate(storyline.created_at)} 
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <ScheduleIcon />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Last Updated" 
                    secondary={formatDate(storyline.updated_at)} 
                  />
                </ListItem>
                {storyContent && (
                  <ListItem>
                    <ListItemIcon>
                      <TimelineIcon />
                    </ListItemIcon>
                    <ListItemText 
                      primary="Story Events" 
                      secondary={`${storyContent.timeline.length} events`} 
                    />
                  </ListItem>
                )}
              </List>
              <Button
                variant="outlined"
                startIcon={<TimelineIcon />}
                onClick={() => navigate(`/storylines/${storylineId}/timeline`)}
                sx={{ mt: 2, width: '100%' }}
              >
                View Full Timeline
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Edit Dialog */}
      <EditStorylineDialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        onSuccess={handleEditSuccess}
        storyline={storyline}
      />
    </Box>
  );
};

export default StorylineDetail;
