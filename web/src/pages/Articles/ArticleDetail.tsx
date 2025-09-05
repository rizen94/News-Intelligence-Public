/**
 * Article Detail Page v3.0 for News Intelligence System
 * Refactored to use new architecture with TypeScript and centralized state management
 */

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  Divider,
  Grid,
  Paper,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Breadcrumbs,
  Link,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Source as SourceIcon,
  Schedule as ScheduleIcon,
  Share as ShareIcon,
  Bookmark as BookmarkIcon,
  Add as AddIcon,
  OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { useNotifications } from '../components/Notifications/NotificationSystem';
import { useArticle } from '@/hooks';
import { Article } from '../../types/articles';
import AddToStorylineDialog from '../components/AddToStorylineDialog/AddToStorylineDialog';
import ErrorBoundary from '../components/ErrorBoundary/ErrorBoundary';

const ArticleDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showSuccess, showError } = useNotifications();
  
  const [bookmarked, setBookmarked] = useState(false);
  const [addToStorylineDialogOpen, setAddToStorylineDialogOpen] = useState(false);

  // Use custom hook for article data
  const { data: article, loading, error, refetch } = useArticle(parseInt(id || '0'));

  // Handle back navigation
  const handleBack = () => {
    navigate('/articles');
  };

  // Handle share
  const handleShare = async () => {
    if (navigator.share && article) {
      try {
        await navigator.share({
          title: article.title,
          text: article.summary || article.content.substring(0, 200),
          url: window.location.href,
        });
      } catch (error) {
        // Fallback to clipboard
        navigator.clipboard.writeText(window.location.href);
        showSuccess('Link copied to clipboard');
      }
    } else {
      // Fallback to clipboard
      navigator.clipboard.writeText(window.location.href);
      showSuccess('Link copied to clipboard');
    }
  };

  // Handle bookmark toggle
  const handleBookmarkToggle = () => {
    setBookmarked(!bookmarked);
    showSuccess(bookmarked ? 'Removed from bookmarks' : 'Added to bookmarks');
  };

  // Handle add to storyline
  const handleAddToStoryline = () => {
    setAddToStorylineDialogOpen(true);
  };

  // Handle external link
  const handleExternalLink = () => {
    if (article?.url) {
      window.open(article.url, '_blank', 'noopener,noreferrer');
    }
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Get sentiment color
  const getSentimentColor = (score: number) => {
    if (score > 0.1) return 'success';
    if (score < -0.1) return 'error';
    return 'default';
  };

  // Get sentiment label
  const getSentimentLabel = (score: number) => {
    if (score > 0.1) return 'Positive';
    if (score < -0.1) return 'Negative';
    return 'Neutral';
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
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="contained" onClick={refetch}>
          Try Again
        </Button>
      </Box>
    );
  }

  if (!article) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">
          Article not found
        </Alert>
        <Button variant="contained" onClick={handleBack}>
          Back to Articles
        </Button>
      </Box>
    );
  }

  return (
    <ErrorBoundary>
      <Box sx={{ p: 3 }}>
        {/* Header */}
        <Box sx={{ mb: 3 }}>
          <Breadcrumbs sx={{ mb: 2 }}>
            <Link
              component="button"
              variant="body2"
              onClick={handleBack}
              sx={{ textDecoration: 'none' }}
            >
              Articles
            </Link>
            <Typography variant="body2" color="text.primary">
              Article Detail
            </Typography>
          </Breadcrumbs>

          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={handleBack}
              sx={{ mr: 2 }}
            >
              Back
            </Button>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="Share">
                <IconButton onClick={handleShare}>
                  <ShareIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title={bookmarked ? 'Remove from bookmarks' : 'Add to bookmarks'}>
                <IconButton onClick={handleBookmarkToggle}>
                  <BookmarkIcon color={bookmarked ? 'primary' : 'inherit'} />
                </IconButton>
              </Tooltip>
              <Tooltip title="Add to storyline">
                <IconButton onClick={handleAddToStoryline}>
                  <AddIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Open original article">
                <IconButton onClick={handleExternalLink}>
                  <OpenInNewIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* Main Article Content */}
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                {/* Article Header */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="h4" component="h1" gutterBottom>
                    {article.title}
                  </Typography>
                  
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                    <Chip
                      icon={<SourceIcon />}
                      label={article.source}
                      color="primary"
                      variant="outlined"
                    />
                    <Chip
                      icon={<ScheduleIcon />}
                      label={formatDate(article.created_at.toString())}
                      variant="outlined"
                    />
                    {article.category && (
                      <Chip
                        label={article.category}
                        variant="outlined"
                      />
                    )}
                    <Chip
                      label={article.processing_status}
                      color={article.processing_status === 'processed' ? 'success' : 'warning'}
                    />
                  </Box>

                  {article.summary && (
                    <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
                      {article.summary}
                    </Typography>
                  )}
                </Box>

                <Divider sx={{ mb: 3 }} />

                {/* Article Content */}
                <Typography variant="body1" sx={{ lineHeight: 1.8, mb: 3 }}>
                  {article.content}
                </Typography>

                {/* External Link */}
                {article.url && (
                  <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Original Article:
                    </Typography>
                    <Link
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{ textDecoration: 'none' }}
                    >
                      {article.url}
                    </Link>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Sidebar */}
          <Grid item xs={12} md={4}>
            {/* Article Stats */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Article Analysis
                </Typography>
                
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="Quality Score"
                      secondary={`${(article.quality_score * 100).toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Sentiment"
                      secondary={
                        <Chip
                          label={getSentimentLabel(article.sentiment_score)}
                          color={getSentimentColor(article.sentiment_score) as any}
                          size="small"
                        />
                      }
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Readability Score"
                      secondary={`${(article.readability_score * 100).toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Engagement Score"
                      secondary={`${(article.engagement_score * 100).toFixed(1)}%`}
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>

            {/* Key Points */}
            {article.key_points && article.key_points.length > 0 && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Key Points
                  </Typography>
                  <List dense>
                    {article.key_points.map((point, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <Typography variant="body2" color="primary">
                            {index + 1}.
                          </Typography>
                        </ListItemIcon>
                        <ListItemText primary={point} />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            )}

            {/* Topics */}
            {article.topics_extracted && article.topics_extracted.length > 0 && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Topics
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {article.topics_extracted.map((topic, index) => (
                      <Chip
                        key={index}
                        label={topic}
                        size="small"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </CardContent>
              </Card>
            )}

            {/* Entities */}
            {article.entities_extracted && article.entities_extracted.length > 0 && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Entities
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {article.entities_extracted.map((entity, index) => (
                      <Chip
                        key={index}
                        label={entity}
                        size="small"
                        color="secondary"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </CardContent>
              </Card>
            )}
          </Grid>
        </Grid>

        {/* Add to Storyline Dialog */}
        <AddToStorylineDialog
          open={addToStorylineDialogOpen}
          onClose={() => setAddToStorylineDialogOpen(false)}
          articleId={article.id}
          onSuccess={() => {
            setAddToStorylineDialogOpen(false);
            showSuccess('Article added to storyline successfully');
          }}
        />
      </Box>
    </ErrorBoundary>
  );
};

export default ArticleDetail;

