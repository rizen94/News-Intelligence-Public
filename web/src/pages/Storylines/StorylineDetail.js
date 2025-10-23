import {
  ArrowBack as ArrowBackIcon,
  Timeline as TimelineIcon,
  Article,
  Edit,
  Event as EventIcon,
  Schedule as ScheduleIcon,
  ExpandMore as ExpandMoreIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Search as SearchIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  CircularProgress,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
  ListItemSecondaryAction,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { apiService } from '../../services/apiService.ts';

const StorylineDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [storyline, setStoryline] = useState(null);
  const [articles, setArticles] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [showTimeline, setShowTimeline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [error, setError] = useState(null);

  // Article management state
  const [showAddArticles, setShowAddArticles] = useState(false);
  const [availableArticles, setAvailableArticles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedArticles, setSelectedArticles] = useState([]);
  const [addArticlesLoading, setAddArticlesLoading] = useState(false);

  useEffect(() => {
    if (id) {
      loadStoryline();
    }
  }, [id]);

  const loadStoryline = async() => {
    try {
      setLoading(true);
      setError(null);

      console.log('Loading storyline with ID:', id);
      const storylineResponse = await apiService.getStoryline(id);
      console.log('Storyline response:', storylineResponse);

      if (storylineResponse.success) {
        setStoryline(storylineResponse.data.storyline);
        setArticles(storylineResponse.data.articles || []);
        console.log('Set storyline:', storylineResponse.data.storyline);
        console.log('Set articles:', storylineResponse.data.articles);
      } else {
        console.error('Storyline response not successful:', storylineResponse);
        setError('Failed to load storyline');
      }
    } catch (err) {
      console.error('Error loading storyline:', err);
      setError('Failed to load storyline');
    } finally {
      setLoading(false);
    }
  };

  const loadTimeline = async() => {
    try {
      setTimelineLoading(true);
      const timelineResponse = await apiService.getStorylineTimeline(id);

      if (timelineResponse.success) {
        setTimeline(timelineResponse.data?.timeline_events || []);
      }
    } catch (err) {
      console.error('Error loading timeline:', err);
    } finally {
      setTimelineLoading(false);
    }
  };

  const loadAvailableArticles = async() => {
    try {
      setAddArticlesLoading(true);
      const response = await apiService.getAvailableArticlesForStoryline(id);
      if (response.success) {
        setAvailableArticles(response.data.articles || []);
      }
    } catch (err) {
      console.error('Error loading available articles:', err);
      setError('Failed to load available articles');
    } finally {
      setAddArticlesLoading(false);
    }
  };

  const handleRemoveArticle = async(articleId) => {
    try {
      const response = await apiService.removeArticleFromStoryline(id, articleId);
      if (response.success) {
        setArticles(prev => prev.filter(article => article.id !== articleId));
        setError(null);
      } else {
        setError(response.message || 'Failed to remove article');
      }
    } catch (err) {
      console.error('Error removing article:', err);
      setError('Failed to remove article');
    }
  };

  const handleAddSelectedArticles = async() => {
    if (selectedArticles.length === 0) return;

    try {
      setAddArticlesLoading(true);
      const promises = selectedArticles.map(articleId =>
        apiService.addArticleToStoryline(id, articleId),
      );

      await Promise.all(promises);

      setSelectedArticles([]);
      setShowAddArticles(false);

      // Reload storyline to get updated articles
      await loadStoryline();
    } catch (err) {
      console.error('Error adding articles:', err);
      setError('Failed to add articles');
    } finally {
      setAddArticlesLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
    case 'active':
      return 'success';
    case 'developing':
      return 'warning';
    case 'concluded':
      return 'default';
    default:
      return 'default';
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'No date';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch (error) {
      return 'Invalid date';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!storyline) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        Storyline not found
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/storylines')}
        >
          Back to Storylines
        </Button>
        <Button
          startIcon={<TimelineIcon />}
          onClick={() => {
            setShowTimeline(!showTimeline);
            if (!showTimeline && timeline.length === 0) {
              loadTimeline();
            }
          }}
        >
          {showTimeline ? 'Hide Timeline' : 'View Timeline'}
        </Button>
        <Button startIcon={<Edit />} variant="outlined">
          Edit Storyline
        </Button>
      </Box>

      <Grid container spacing={3}>
        {/* Storyline Info */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                <Typography variant="h4" component="h1">
                  {storyline.title || 'Untitled Storyline'}
                </Typography>
                <Chip
                  label={storyline.status?.toUpperCase() || 'UNKNOWN'}
                  color={getStatusColor(storyline.status)}
                  variant="outlined"
                />
              </Box>

              {storyline.description && (
                <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
                  {storyline.description}
                </Typography>
              )}

              <Box sx={{ display: 'flex', gap: 3 }}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Articles:</strong> {articles.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  <strong>Last Updated:</strong> {formatDate(storyline.updated_at)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  <strong>Created:</strong> {formatDate(storyline.created_at)}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Timeline Section */}
        {showTimeline && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <TimelineIcon color="primary" />
                  <Typography variant="h6">Timeline</Typography>
                </Box>

                {timelineLoading ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <CircularProgress />
                  </Box>
                ) : timeline.length > 0 ? (
                  <Timeline>
                    {timeline.map((event, index) => (
                      <TimelineItem key={event.article_id || index}>
                        <TimelineOppositeContent
                          sx={{ m: 'auto 0' }}
                          align="right"
                          variant="body2"
                          color="text.secondary"
                        >
                          {event.published_at ? formatDate(event.published_at) : 'No date'}
                        </TimelineOppositeContent>
                        <TimelineSeparator>
                          <TimelineConnector />
                          <TimelineDot color="primary">
                            <EventIcon />
                          </TimelineDot>
                          <TimelineConnector />
                        </TimelineSeparator>
                        <TimelineContent sx={{ py: '12px', px: 2 }}>
                          <Typography variant="h6" component="span">
                            {event.title || 'Untitled Event'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {event.source_domain || 'Unknown Source'}
                          </Typography>
                          {event.event_type && (
                            <Chip
                              label={event.event_type}
                              size="small"
                              sx={{ mt: 1, mr: 1 }}
                            />
                          )}
                          {event.confidence_score && (
                            <Chip
                              label={`Confidence: ${(event.confidence_score * 100).toFixed(0)}%`}
                              size="small"
                              variant="outlined"
                              sx={{ mt: 1 }}
                            />
                          )}
                          {event.event_description && (
                            <Typography variant="body2" sx={{ mt: 1 }}>
                              {event.event_description}
                            </Typography>
                          )}
                          {event.summary && (
                            <Typography variant="body2" sx={{ mt: 1, fontStyle: 'italic' }}>
                              {event.summary.length > 150
                                ? `${event.summary.substring(0, 150)}...`
                                : event.summary}
                            </Typography>
                          )}
                        </TimelineContent>
                      </TimelineItem>
                    ))}
                  </Timeline>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No timeline events found for this storyline
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Articles in Storyline */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Article color="primary" />
                  <Typography variant="h6">Articles in this Storyline ({articles.length})</Typography>
                </Box>
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  onClick={() => {
                    setShowAddArticles(true);
                    loadAvailableArticles();
                  }}
                  size="small"
                >
                  Add Articles
                </Button>
              </Box>

              {articles.length > 0 ? (
                <List>
                  {articles.map((article, index) => (
                    <React.Fragment key={article.id || index}>
                      <ListItem>
                        <ListItemText
                          primary={
                            <Typography
                              variant="h6"
                              sx={{ cursor: 'pointer' }}
                              onClick={() => navigate(`/articles/${article.id}`)}
                            >
                              {article.title || 'Untitled Article'}
                            </Typography>
                          }
                          secondary={
                            <Box>
                              <Typography variant="body2" color="text.secondary">
                                {article.source_domain || 'Unknown Source'} • {formatDate(article.published_at)}
                              </Typography>
                              {article.category && (
                                <Chip label={article.category} size="small" sx={{ mt: 0.5 }} />
                              )}
                              {article.summary && (
                                <Typography variant="body2" sx={{ mt: 1 }}>
                                  {article.summary.length > 200
                                    ? `${article.summary.substring(0, 200)}...`
                                    : article.summary}
                                </Typography>
                              )}
                            </Box>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Tooltip title="Remove from storyline">
                            <IconButton
                              edge="end"
                              onClick={() => handleRemoveArticle(article.id)}
                              color="error"
                              size="small"
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < articles.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No articles found in this storyline
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Add Articles Dialog */}
      <Dialog
        open={showAddArticles}
        onClose={() => setShowAddArticles(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Add Articles to Storyline</Typography>
            <IconButton onClick={() => setShowAddArticles(false)} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent>
          <TextField
            fullWidth
            placeholder="Search articles..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
            sx={{ mb: 2 }}
          />

          <Box sx={{ maxHeight: '400px', overflow: 'auto' }}>
            {addArticlesLoading ? (
              <Box display="flex" justifyContent="center" p={2}>
                <CircularProgress />
              </Box>
            ) : (
              <List dense>
                {availableArticles
                  .filter(article =>
                    article.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    article.source_domain.toLowerCase().includes(searchTerm.toLowerCase()),
                  )
                  .map((article, index) => (
                    <React.Fragment key={article.id}>
                      <ListItem>
                        <ListItemText
                          primary={article.title}
                          secondary={`${article.source_domain} • ${formatDate(article.published_at)}`}
                        />
                        <ListItemSecondaryAction>
                          <Button
                            variant={selectedArticles.includes(article.id) ? 'contained' : 'outlined'}
                            size="small"
                            onClick={() => {
                              setSelectedArticles(prev =>
                                prev.includes(article.id)
                                  ? prev.filter(id => id !== article.id)
                                  : [...prev, article.id],
                              );
                            }}
                          >
                            {selectedArticles.includes(article.id) ? 'Selected' : 'Select'}
                          </Button>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < availableArticles.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
              </List>
            )}
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setShowAddArticles(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleAddSelectedArticles}
            disabled={addArticlesLoading || selectedArticles.length === 0}
            startIcon={<AddIcon />}
          >
            Add {selectedArticles.length} Articles
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StorylineDetail;
