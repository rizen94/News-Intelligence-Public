import React, { useState, useEffect } from 'react';
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
import { useNotifications } from '../../components/Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';
import AddToStorylineDialog from '../../components/AddToStorylineDialog/AddToStorylineDialog';

const ArticleDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showSuccess, showError, showLoading } = useNotifications();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [relatedArticles, setRelatedArticles] = useState([]);
  const [bookmarked, setBookmarked] = useState(false);
  const [addToStorylineDialogOpen, setAddToStorylineDialogOpen] = useState(false);

  useEffect(() => {
    if (id) {
      fetchArticle();
    }
  }, [id]);

  const fetchArticle = async () => {
    try {
      setLoading(true);
      showLoading('Loading article...');

      const response = await newsSystemService.getArticle(id);
      
      if (response.success) {
        setArticle(response.data);
        showSuccess('Article loaded successfully');
      } else {
        throw new Error(response.message || 'Failed to fetch article');
      }
    } catch (error) {
      console.error('Error fetching article:', error);
      showError('Failed to load article. Please try refreshing the page.');
      
      // Set empty state instead of mock data
      setArticle(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchRelatedArticles = async () => {
    try {
      // TODO: Implement related articles API call
      // For now, set empty array
      setRelatedArticles([]);
    } catch (error) {
      console.error('Error fetching related articles:', error);
      setRelatedArticles([]);
    }
  };

  const handleBookmark = () => {
    setBookmarked(!bookmarked);
    showSuccess(bookmarked ? 'Removed from bookmarks' : 'Added to bookmarks');
  };

  const handleAddToStoryline = () => {
    setAddToStorylineDialogOpen(true);
  };

  const handleAddToStorylineSuccess = () => {
    // Refresh article data or show success message
    showSuccess('Article added to storyline successfully');
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

  const getSentimentColor = (score) => {
    if (score > 0.1) return 'success';
    if (score < -0.1) return 'error';
    return 'default';
  };

  const getSentimentLabel = (score) => {
    if (score > 0.1) return 'Positive';
    if (score < -0.1) return 'Negative';
    return 'Neutral';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={60} />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading article...
        </Typography>
      </Box>
    );
  }

  if (!article) {
    return (
      <Box>
        <Alert severity="error">
          Article not found
        </Alert>
        <Button
          variant="contained"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/articles')}
          sx={{ mt: 2 }}
        >
          Back to Articles
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 3 }}>
        <Link 
          component="button" 
          variant="body2" 
          onClick={() => navigate('/articles')}
          sx={{ textDecoration: 'none' }}
        >
          Articles
        </Link>
        <Typography color="text.primary">{article.title}</Typography>
      </Breadcrumbs>

      {/* Header Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/articles')}
        >
          Back to Articles
        </Button>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Add to Storyline">
            <IconButton onClick={handleAddToStoryline} color="primary">
              <AddIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title={bookmarked ? "Remove from Bookmarks" : "Add to Bookmarks"}>
            <IconButton onClick={handleBookmark} color={bookmarked ? "primary" : "default"}>
              <BookmarkIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Share">
            <IconButton>
              <ShareIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Main Article Content */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              {/* Article Header */}
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Chip 
                    label={article.category} 
                    color="primary"
                    variant="outlined"
                  />
                  <Chip 
                    label={getSentimentLabel(article.sentiment_score)}
                    color={getSentimentColor(article.sentiment_score)}
                    variant="outlined"
                  />
                </Box>

                <Typography variant="h3" component="h1" gutterBottom sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                  {article.title}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <SourceIcon sx={{ fontSize: 20, mr: 1, color: 'text.secondary' }} />
                    <Typography variant="h6" color="text.secondary">
                      {article.source}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <ScheduleIcon sx={{ fontSize: 20, mr: 1, color: 'text.secondary' }} />
                    <Typography variant="body1" color="text.secondary">
                      {formatDate(article.published_date)}
                    </Typography>
                  </Box>
                </Box>

                {/* Summary */}
                {article.summary && (
                  <Paper sx={{ p: 2, mb: 3, backgroundColor: 'grey.50' }}>
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                      Summary
                    </Typography>
                    <Typography variant="body1" sx={{ lineHeight: 1.6 }}>
                      {article.summary}
                    </Typography>
                  </Paper>
                )}
              </Box>

              <Divider sx={{ mb: 3 }} />

              {/* Article Content */}
              <Typography variant="body1" sx={{ lineHeight: 1.8, fontSize: '1.1rem' }}>
                {article.content}
              </Typography>

              {/* Key Points */}
              {article.key_points && article.key_points.length > 0 && (
                <Box sx={{ mt: 4 }}>
                  <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                    Key Points
                  </Typography>
                  <List>
                    {(article.key_points || []).map((point, index) => (
                      <ListItem key={index} sx={{ py: 0.5 }}>
                        <ListItemIcon>
                          <Typography variant="body2" color="primary" sx={{ fontWeight: 'bold' }}>
                            {index + 1}.
                          </Typography>
                        </ListItemIcon>
                        <ListItemText primary={point} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              {/* Topics and Entities */}
              <Box sx={{ mt: 4 }}>
                <Grid container spacing={2}>
                  {article.topics_extracted && article.topics_extracted.length > 0 && (
                    <Grid item xs={12} md={6}>
                      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                        Topics
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {(article.topics_extracted || []).map((topic, index) => (
                          <Chip 
                            key={index}
                            label={topic} 
                            variant="outlined"
                            color="primary"
                          />
                        ))}
                      </Box>
                    </Grid>
                  )}
                  
                  {article.entities_extracted && article.entities_extracted.length > 0 && (
                    <Grid item xs={12} md={6}>
                      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                        Key Entities
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {(article.entities_extracted || []).map((entity, index) => (
                          <Chip 
                            key={index}
                            label={entity} 
                            variant="outlined"
                            color="secondary"
                          />
                        ))}
                      </Box>
                    </Grid>
                  )}
                </Grid>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={4}>
          {/* Article Metadata */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Article Details
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Quality Score
                </Typography>
                <Box sx={{ 
                  width: '100%', 
                  height: 8, 
                  backgroundColor: 'grey.300', 
                  borderRadius: 4,
                  overflow: 'hidden'
                }}>
                  <Box sx={{ 
                    width: `${(article.quality_score || 0) * 100}%`, 
                    height: '100%', 
                    backgroundColor: article.quality_score > 0.8 ? 'success.main' : 
                                   article.quality_score > 0.6 ? 'warning.main' : 'error.main'
                  }} />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {Math.round((article.quality_score || 0) * 100)}%
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Sentiment Analysis
                </Typography>
                <Chip 
                  label={getSentimentLabel(article.sentiment_score)}
                  color={getSentimentColor(article.sentiment_score)}
                  variant="outlined"
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Published
                </Typography>
                <Typography variant="body2">
                  {formatDate(article.published_date)}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Last Updated
                </Typography>
                <Typography variant="body2">
                  {formatDate(article.updated_at || article.created_at)}
                </Typography>
              </Box>

              {article.url && (
                <Button
                  variant="outlined"
                  startIcon={<OpenInNewIcon />}
                  href={article.url}
                  target="_blank"
                  fullWidth
                  sx={{ mt: 2 }}
                >
                  View Original Source
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Related Articles */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Related Articles
              </Typography>
              <List>
                {(relatedArticles || []).map((relatedArticle) => (
                  <ListItem 
                    key={relatedArticle.id}
                    button
                    onClick={() => navigate(`/articles/${relatedArticle.id}`)}
                    sx={{ 
                      borderRadius: 1,
                      '&:hover': { backgroundColor: 'action.hover' }
                    }}
                  >
                    <ListItemText
                      primary={
                        <Typography variant="subtitle2" noWrap>
                          {relatedArticle.title}
                        </Typography>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary" noWrap>
                            {relatedArticle.summary}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {relatedArticle.source} • {formatDate(relatedArticle.published_date)}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Add to Storyline Dialog */}
      <AddToStorylineDialog
        open={addToStorylineDialogOpen}
        onClose={() => setAddToStorylineDialogOpen(false)}
        article={article}
        onSuccess={handleAddToStorylineSuccess}
      />
    </Box>
  );
};

export default ArticleDetail;
