import {
  ArrowBack as ArrowBackIcon,
  Share as ShareIcon,
  Bookmark as BookmarkIcon,
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
} from '@mui/material';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { apiService } from '../../services/apiService.ts';

const ArticleDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (id) {
      loadArticle();
    }
  }, [id]);

  const loadArticle = async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticle(id);

      if (response.success) {
        setArticle(response.data);
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

  const formatDate = (dateString) => {
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
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!article) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        Article not found
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/articles')}
        >
          Back to Articles
        </Button>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button startIcon={<ShareIcon />} variant="outlined">
            Share
          </Button>
          <Button startIcon={<BookmarkIcon />} variant="outlined">
            Bookmark
          </Button>
        </Box>
      </Box>

      <Paper sx={{ p: 3 }}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h4" component="h1" sx={{ mb: 2 }}>
            {article.title || 'Untitled Article'}
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {article.source || 'Unknown Source'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              •
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatDate(article.published_date)}
            </Typography>
            {article.category && (
              <>
                <Typography variant="body2" color="text.secondary">
                  •
                </Typography>
                <Chip label={article.category} size="small" />
              </>
            )}
          </Box>

          {article.summary && (
            <Typography variant="h6" color="text.secondary" sx={{ mb: 3, fontStyle: 'italic' }}>
              {article.summary}
            </Typography>
          )}
        </Box>

        <Divider sx={{ mb: 3 }} />

        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" sx={{ lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
            {article.content || 'No content available for this article.'}
          </Typography>
        </Box>

        {article.url && (
          <Box sx={{ mt: 3, pt: 3, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Original Source:
            </Typography>
            <Button
              variant="outlined"
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View Original Article
            </Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default ArticleDetail;
