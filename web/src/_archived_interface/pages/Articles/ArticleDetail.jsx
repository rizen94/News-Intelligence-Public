import {
  ArrowBack as ArrowBackIcon,
  Share as ShareIcon,
  Bookmark,
  Event as EventIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  Divider,
  Alert,
  CircularProgress,
  Paper,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import apiService from '../../services/apiService';
import ArticleTopics from '../../components/ArticleTopics/ArticleTopics';
import { useDomainNavigation } from '../../hooks/useDomainNavigation';
import { useDomainRoute } from '../../hooks/useDomainRoute';

const ArticleDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { navigateToDomain } = useDomainNavigation();
  const { domain } = useDomainRoute();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [extractedEvents, setExtractedEvents] = useState([]);

  useEffect(() => {
    if (id) {
      loadArticle();
    }
  }, [id]);

  const loadArticle = async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticle(id, domain);

      if (response.success) {
        setArticle(response.data);
        try {
          const evts = await apiService.getArticleEvents(id, domain);
          if (evts?.success) setExtractedEvents(evts.data || []);
        } catch { /* non-critical */ }
      } else {
        setError('Failed to load article');
      }
    } catch (err) {
      console.error('Error loading article:', err);
      setError('Failed to load article');
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

  if (!article) {
    return (
      <Alert severity='warning' sx={{ mb: 2 }}>
        Article not found
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigateToDomain('/articles')}
        >
          Back to Articles
        </Button>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button startIcon={<ShareIcon />} variant='outlined'>
            Share
          </Button>
          <Button startIcon={<Bookmark />} variant='outlined'>
            Bookmark
          </Button>
        </Box>
      </Box>

      <Paper sx={{ p: 3 }}>
        <Box sx={{ mb: 3 }}>
          <Typography variant='h4' component='h1' sx={{ mb: 2 }}>
            {article.title || 'Untitled Article'}
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography variant='body2' color='text.secondary'>
              {article.source || article.source_domain || 'Unknown Source'}
            </Typography>
            <Typography variant='body2' color='text.secondary'>
              •
            </Typography>
            <Typography variant='body2' color='text.secondary'>
              {formatDate(article.published_date || article.published_at)}
            </Typography>
            {article.category && (
              <>
                <Typography variant='body2' color='text.secondary'>
                  •
                </Typography>
                <Chip label={article.category} size='small' />
              </>
            )}
          </Box>

          {(article.summary || article.excerpt) && (
            <Typography
              variant='h6'
              color='text.secondary'
              sx={{ mb: 3, fontStyle: 'italic' }}
            >
              {article.summary || article.excerpt}
            </Typography>
          )}
        </Box>

        <Divider sx={{ mb: 3 }} />

        <Box sx={{ mb: 3 }}>
          <Typography
            variant='body1'
            sx={{ lineHeight: 1.8, whiteSpace: 'pre-wrap' }}
          >
            {article.content || article.excerpt || article.summary || 'No content available for this article.'}
          </Typography>
        </Box>

        {article.url && (
          <Box sx={{ mt: 3, pt: 3, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
              Original Source:
            </Typography>
            <Button
              variant='outlined'
              href={article.url}
              target='_blank'
              rel='noopener noreferrer'
            >
              View Original Article
            </Button>
          </Box>
        )}
      </Paper>

      {/* Extracted Events (v5.0) */}
      {extractedEvents.length > 0 && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <EventIcon color='primary' />
              <Typography variant='h6'>
                Extracted Events ({extractedEvents.length})
              </Typography>
            </Box>
            <List dense>
              {extractedEvents.map((evt, i) => (
                <ListItem key={i} divider
                  sx={{ cursor: evt.storyline_id ? 'pointer' : 'default' }}
                  onClick={() => evt.storyline_id && navigate(`/${domain}/storylines/${evt.storyline_id}/timeline`)}>
                  <ListItemText
                    primary={evt.title}
                    secondary={
                      <>
                        {evt.event_date || 'date unknown'}
                        {' · '}
                        {(evt.event_type || '').replace(/_/g, ' ')}
                        {evt.location && evt.location !== 'unknown' && ` · ${evt.location}`}
                      </>
                    }
                  />
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    {evt.source_count > 1 && (
                      <Chip label={`${evt.source_count} sources`} size='small' color='info' variant='outlined' />
                    )}
                    {evt.is_ongoing && (
                      <Chip label='ongoing' size='small' color='warning' variant='outlined' />
                    )}
                    {evt.storyline_id && (
                      <Chip label={`Story #${evt.storyline_id}`} size='small' variant='outlined' />
                    )}
                  </Box>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Article Topics Section */}
      <Box sx={{ mt: 3 }}>
        <ArticleTopics articleId={parseInt(id)} />
      </Box>
    </Box>
  );
};

export default ArticleDetail;
