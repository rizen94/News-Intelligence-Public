import {
  Schedule,
  TrendingUp as TrendingUpIcon,
  Article,
  Timeline as TimelineIcon,
  Refresh,
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
  ListItemIcon,
  Divider,
  Paper,
  Alert,
  CircularProgress,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import { apiService } from '../../services/apiService.ts';

const MorningBriefing = () => {
  const [briefing, setBriefing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadBriefing();
  }, []);

  const loadBriefing = async() => {
    try {
      setLoading(true);
      setError(null);

      // Load recent articles and create a briefing
      const [articlesResponse, storylinesResponse] = await Promise.all([
        apiService.getArticles({ limit: 10 }),
        apiService.getStorylines(),
      ]);

      const briefing = {
        date: new Date().toLocaleDateString(),
        topStories: articlesResponse.data?.articles?.slice(0, 5) || [],
        storylines: storylinesResponse.data?.storylines?.slice(0, 3) || [],
        summary: `Today's briefing covers ${
          articlesResponse.data?.articles?.length || 0
        } articles across ${
          storylinesResponse.data?.storylines?.length || 0
        } active storylines.`,
      };

      setBriefing(briefing);
    } catch (err) {
      console.error('Error loading briefing:', err);
      setError('Failed to load morning briefing');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = dateString => {
    if (!dateString) return 'No date';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
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
      <Alert severity='error' sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Typography variant='h4' component='h1'>
          Morning Briefing
        </Typography>
        <Button
          variant='outlined'
          startIcon={<Refresh />}
          onClick={loadBriefing}
        >
          Refresh
        </Button>
      </Box>

      <Grid container spacing={3}>
        {/* Summary Card */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}
              >
                <Schedule color='primary' />
                <Typography variant='h5'>
                  {briefing?.date} - News Intelligence Briefing
                </Typography>
              </Box>
              <Typography variant='body1' color='text.secondary'>
                {briefing?.summary}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Top Stories */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}
              >
                <Article color='primary' />
                <Typography variant='h6'>Top Stories</Typography>
              </Box>
              {briefing?.topStories?.length > 0 ? (
                <List>
                  {briefing.topStories.map((article, index) => (
                    <React.Fragment key={article.id || index}>
                      <ListItem>
                        <ListItemText
                          primary={article.title || 'Untitled Article'}
                          secondary={
                            <Box>
                              <Typography
                                variant='body2'
                                color='text.secondary'
                              >
                                {article.source || 'Unknown Source'} •{' '}
                                {formatDate(article.published_date)}
                              </Typography>
                              {article.category && (
                                <Chip
                                  label={article.category}
                                  size='small'
                                  sx={{ mt: 0.5 }}
                                />
                              )}
                            </Box>
                          }
                        />
                      </ListItem>
                      {index < briefing.topStories.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  No stories available
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Active Storylines */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}
              >
                <TimelineIcon color='primary' />
                <Typography variant='h6'>Active Storylines</Typography>
              </Box>
              {briefing?.storylines?.length > 0 ? (
                <List>
                  {briefing.storylines.map((storyline, index) => (
                    <React.Fragment key={storyline.id || index}>
                      <ListItem>
                        <ListItemText
                          primary={storyline.title || 'Untitled Storyline'}
                          secondary={
                            <Box>
                              <Typography
                                variant='body2'
                                color='text.secondary'
                              >
                                {storyline.article_count || 0} articles •{' '}
                                {storyline.status || 'Unknown status'}
                              </Typography>
                              {storyline.description && (
                                <Typography variant='body2' sx={{ mt: 0.5 }}>
                                  {storyline.description.length > 100
                                    ? `${storyline.description.substring(
                                      0,
                                      100,
                                    )}...`
                                    : storyline.description}
                                </Typography>
                              )}
                            </Box>
                          }
                        />
                      </ListItem>
                      {index < briefing.storylines.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  No active storylines
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MorningBriefing;
