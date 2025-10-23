import {
  ArrowBack as ArrowBackIcon,
  Timeline as TimelineIcon,
  Article,
  Edit,
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
} from '@mui/material';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { apiService } from '../../services/apiService.ts';

const StorylineDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [storyline, setStoryline] = useState(null);
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (id) {
      loadStoryline();
    }
  }, [id]);

  const loadStoryline = async() => {
    try {
      setLoading(true);
      setError(null);

      const [storylineResponse, articlesResponse] = await Promise.all([
        apiService.getStoryline(id),
        apiService.getArticles({ storyline_id: id }),
      ]);

      if (storylineResponse.success) {
        setStoryline(storylineResponse.data);
      }

      if (articlesResponse.success) {
        setArticles(articlesResponse.data?.articles || []);
      }
    } catch (err) {
      console.error('Error loading storyline:', err);
      setError('Failed to load storyline');
    } finally {
      setLoading(false);
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
          onClick={() => navigate(`/storylines/${id}/timeline`)}
        >
          View Timeline
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

        {/* Articles in Storyline */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Article color="primary" />
                <Typography variant="h6">Articles in this Storyline</Typography>
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
                                {article.source || 'Unknown Source'} • {formatDate(article.published_date)}
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
    </Box>
  );
};

export default StorylineDetail;
