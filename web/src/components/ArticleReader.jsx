import {
  Close as CloseIcon,
  OpenInNew as OpenInNewIcon,
  Share as ShareIcon,
  Bookmark,
  BookmarkBorder,
  Timeline as TimelineIcon,
  Psychology as PsychologyIcon,
  Source,
  CalendarToday as CalendarIcon,
  Person as PersonIcon,
  Language as LanguageIcon,
} from '@mui/icons-material';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  IconButton,
  Chip,
  Divider,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  CircularProgress,
  Paper,
  Snackbar,
} from '@mui/material';
import React, { useEffect, useState } from 'react';

import apiService from '../services/apiService';
import Logger from '../utils/logger';
import { api } from '../services/apiService';
import { storylinesApi } from '../services/api/storylines';

import StorylineConfirmationDialog from './StorylineConfirmationDialog';

const ArticleReader = ({ article, open, onClose, onAddToStoryline }) => {
  const [fullContent, setFullContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [storylines, setStorylines] = useState([]);
  const [selectedStoryline, setSelectedStoryline] = useState('');
  const [newStorylineTitle, setNewStorylineTitle] = useState('');
  const [showStorylineDialog, setShowStorylineDialog] = useState(false);
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [confirmationDialog, setConfirmationDialog] = useState({
    open: false,
    action: null,
    storyline: null,
  });
  const [actionLoading, setActionLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success',
  });

  useEffect(() => {
    if (open && article) {
      loadFullContent();
      loadStorylines();
      checkBookmarkStatus();
    }
  }, [open, article]);

  const loadFullContent = async() => {
    if (!article) return;

    setLoading(true);
    setError(null);

    try {
      // Try to get full content from the article
      if (article.content && article.content.length > 200) {
        setFullContent(article.content);
      } else {
        // If content is just a summary, try to fetch full content
        const response = await api.post(
          `/article-processing/fetch-full-content/${article.id}`,
        );
        if (response.data?.success && response.data.data?.content) {
          setFullContent(response.data.data.content);
        } else if (response.data?.content) {
          setFullContent(response.data.content);
        } else {
          setFullContent(
            article.content ||
              'Full content not available. Click "Read Original" to view the complete article.',
          );
        }
      }
    } catch (err) {
      Logger.error('Error loading full content:', err);
      setError('Failed to load full article content');
      setFullContent(article.content || 'Content not available');
    } finally {
      setLoading(false);
    }
  };

  const loadStorylines = async() => {
    try {
      const data = await storylinesApi.getStorylines();
      if (data && data.success !== false) setStorylines(data.data?.storylines || data.data || []);
    } catch (e) {
      Logger.error('ArticleReader', 'Failed to load storylines', e);
    }
  };

  const checkBookmarkStatus = async() => {
    // Bookmark functionality not implemented yet
    setIsBookmarked(false);
  };

  const handleAddToStoryline = async() => {
    if (!selectedStoryline && !newStorylineTitle.trim()) {
      setError('Please select a storyline or create a new one');
      return;
    }

    // Show confirmation dialog
    const targetStoryline = selectedStoryline
      ? storylines.find(s => s.id === selectedStoryline)
      : { title: newStorylineTitle.trim() };

    setConfirmationDialog({
      open: true,
      action: 'add_article',
      storyline: targetStoryline,
    });
  };

  const handleConfirmAction = async() => {
    setActionLoading(true);
    setError(null);

    try {
      let storylineId = selectedStoryline;

      // Create new storyline if needed
      if (!selectedStoryline && newStorylineTitle.trim()) {
        const createResponse = await apiService.createStoryline({
          title: newStorylineTitle.trim(),
          description: `Storyline created from article: ${article.title}`,
        });

        if (createResponse.success) {
          storylineId = createResponse.data?.storyline?.id || createResponse.data?.id;
          if (!storylineId) {
            throw new Error('Failed to get storyline ID after creation');
          }
          setStorylines(prev => [...prev, createResponse.data?.storyline || createResponse.data]);
          showSnackbar('New storyline created successfully!', 'success');
        } else {
          throw new Error(
            createResponse.message || createResponse.error || 'Failed to create storyline',
          );
        }
      }

      // Validate storylineId before proceeding
      if (!storylineId) {
        throw new Error('Please select a storyline or create a new one');
      }

      // Convert to number to ensure it's a valid integer
      const storylineIdNum = Number(storylineId);
      const articleIdNum = Number(article.id);

      if (isNaN(storylineIdNum) || isNaN(articleIdNum)) {
        throw new Error('Invalid storyline or article ID');
      }

      // Add article to storyline
      const addResponse = await apiService.addArticleToStoryline(
        storylineIdNum,
        articleIdNum,
      );

      if (addResponse.success) {
        onAddToStoryline?.(storylineIdNum, articleIdNum);
        setShowStorylineDialog(false);
        setSelectedStoryline('');
        setNewStorylineTitle('');
        showSnackbar('Article added to storyline successfully!', 'success');
      } else {
        // Extract error message, handling both string and object formats
        let errorMsg = 'Failed to add article to storyline';
        if (addResponse.error) {
          errorMsg = typeof addResponse.error === 'string'
            ? addResponse.error
            : addResponse.error.detail || addResponse.error.message || JSON.stringify(addResponse.error);
        } else if (addResponse.message) {
          errorMsg = typeof addResponse.message === 'string'
            ? addResponse.message
            : JSON.stringify(addResponse.message);
        }
        throw new Error(errorMsg);
      }
    } catch (err) {
      Logger.error('Error adding to storyline:', err);
      // Extract error message safely, handling both Error objects and plain objects
      let errorMessage = 'Failed to add article to storyline';
      if (err instanceof Error) {
        errorMessage = err.message || errorMessage;
      } else if (typeof err === 'string') {
        errorMessage = err;
      } else if (err && typeof err === 'object') {
        errorMessage = err.message || err.detail || err.error || JSON.stringify(err);
      }
      setError(errorMessage);
      showSnackbar(errorMessage, 'error');
    } finally {
      setActionLoading(false);
      setConfirmationDialog({ open: false, action: null, storyline: null });
    }
  };

  const handleCloseConfirmation = () => {
    if (!actionLoading) {
      setConfirmationDialog({ open: false, action: null, storyline: null });
    }
  };

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({
      open: true,
      message,
      severity,
    });
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  const handleBookmark = async() => {
    // Bookmark functionality not implemented yet
    Logger.info('Bookmark functionality not implemented yet');
  };

  const handleShare = async() => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: article.title,
          text: article.content?.substring(0, 200) + '...',
          url: article.url,
        });
      } catch (err) {
        Logger.info('Share cancelled');
      }
    } else {
      // Fallback to clipboard
      navigator.clipboard.writeText(article.url);
    }
  };

  if (!article) return null;

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth='md'
        fullWidth
        PaperProps={{
          sx: { height: '90vh' },
        }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Box
            display='flex'
            justifyContent='space-between'
            alignItems='center'
          >
            <Typography
              variant='h6'
              component='div'
              sx={{ flexGrow: 1, pr: 2 }}
            >
              {article.title}
            </Typography>
            <Box>
              <IconButton onClick={handleBookmark} size='small'>
                {isBookmarked ? (
                  <Bookmark color='primary' />
                ) : (
                  <BookmarkBorder />
                )}
              </IconButton>
              <IconButton onClick={handleShare} size='small'>
                <ShareIcon />
              </IconButton>
              <IconButton onClick={onClose} size='small'>
                <CloseIcon />
              </IconButton>
            </Box>
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          {loading ? (
            <Box
              display='flex'
              justifyContent='center'
              alignItems='center'
              py={4}
            >
              <CircularProgress size={24} sx={{ mr: 2 }} />
              <Typography variant='body2'>
                Loading article content...
              </Typography>
            </Box>
          ) : error ? (
            <Alert severity='error' sx={{ mb: 2 }}>
              {error}
            </Alert>
          ) : null}

          {/* Article Metadata */}
          <Paper elevation={1} sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
            <Box display='flex' flexWrap='wrap' gap={1} mb={2}>
              <Chip
                icon={<Source />}
                label={article.source || article.source_domain || 'Unknown'}
                size='small'
                color='primary'
                variant='outlined'
              />
              {article.category && (
                <Chip
                  label={article.category}
                  size='small'
                  color='secondary'
                  variant='outlined'
                />
              )}
              {article.sentiment_score && (
                <Chip
                  label={`Sentiment: ${(article.sentiment_score * 100).toFixed(
                    0,
                  )}%`}
                  size='small'
                  color={
                    article.sentiment_score > 0.5
                      ? 'success'
                      : article.sentiment_score < -0.5
                        ? 'error'
                        : 'default'
                  }
                  variant='outlined'
                />
              )}
            </Box>

            <Box display='flex' flexWrap='wrap' gap={2} color='text.secondary'>
              {(article.published_at || article.published_date) && (
                <Box display='flex' alignItems='center' gap={0.5}>
                  <CalendarIcon fontSize='small' />
                  <Typography variant='body2'>
                    {new Date(article.published_at || article.published_date).toLocaleDateString()}
                  </Typography>
                </Box>
              )}
              {article.author && (
                <Box display='flex' alignItems='center' gap={0.5}>
                  <PersonIcon fontSize='small' />
                  <Typography variant='body2'>{article.author}</Typography>
                </Box>
              )}
              {article.language && (
                <Box display='flex' alignItems='center' gap={0.5}>
                  <LanguageIcon fontSize='small' />
                  <Typography variant='body2'>
                    {article.language.toUpperCase()}
                  </Typography>
                </Box>
              )}
            </Box>
          </Paper>

          {/* Article Content */}
          <Box sx={{ mb: 3 }}>
            <Typography
              variant='body1'
              component='div'
              sx={{
                lineHeight: 1.8,
                '& p': { mb: 2 },
                '& h1': {
                  fontSize: '1.8rem',
                  fontWeight: 'bold',
                  color: 'primary.main',
                  mb: 2,
                  borderBottom: '2px solid',
                  borderColor: 'primary.main',
                  pb: 1,
                  mt: 0,
                },
                '& h2': {
                  fontSize: '1.4rem',
                  fontWeight: 'bold',
                  color: 'primary.main',
                  mt: 3,
                  mb: 1,
                },
                '& h3': {
                  fontSize: '1.2rem',
                  fontWeight: 'bold',
                  color: 'text.secondary',
                  mt: 2,
                  mb: 1,
                },
                '& strong': {
                  fontWeight: 'bold',
                  color: 'text.primary',
                },
                '& blockquote': {
                  borderLeft: '4px solid',
                  borderColor: 'primary.main',
                  pl: 2,
                  ml: 0,
                  fontStyle: 'italic',
                  backgroundColor: 'grey.50',
                  py: 1,
                  my: 2,
                },
                '& hr': {
                  border: 'none',
                  borderTop: '2px solid',
                  borderColor: 'grey.300',
                  my: 3,
                },
              }}
              dangerouslySetInnerHTML={{
                __html: (
                  fullContent ||
                  article.content ||
                  'Content not available'
                )
                  .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                  .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                  .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                  .replace(/^\*\*(.*)\*\*/gim, '<strong>$1</strong>')
                  .replace(/^---$/gim, '<hr>')
                  .replace(/\n/g, '<br>'),
              }}
            />
          </Box>

          {/* Article Actions */}
          <Divider sx={{ my: 2 }} />
          <Box display='flex' gap={2} flexWrap='wrap'>
            <Button
              variant='outlined'
              startIcon={<OpenInNewIcon />}
              onClick={() => window.open(article.url, '_blank')}
            >
              Read Original
            </Button>
            <Button
              variant='contained'
              startIcon={<TimelineIcon />}
              onClick={() => setShowStorylineDialog(true)}
            >
              Add to Storyline
            </Button>
            <Button
              variant='outlined'
              startIcon={<PsychologyIcon />}
              onClick={() => {
                /* TODO: Add AI analysis */
              }}
            >
              AI Analysis
            </Button>
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Storyline Selection Dialog */}
      <Dialog
        open={showStorylineDialog}
        onClose={() => setShowStorylineDialog(false)}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>Add Article to Storyline</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel>Select Existing Storyline</InputLabel>
              <Select
                value={selectedStoryline}
                onChange={e => setSelectedStoryline(e.target.value)}
                label='Select Existing Storyline'
              >
                {storylines.map(storyline => (
                  <MenuItem key={storyline.id} value={storyline.id}>
                    {storyline.title}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
              Or create a new storyline:
            </Typography>
            <TextField
              fullWidth
              label='New Storyline Title'
              value={newStorylineTitle}
              onChange={e => setNewStorylineTitle(e.target.value)}
              placeholder='Enter storyline title...'
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowStorylineDialog(false)}>Cancel</Button>
          <Button
            onClick={handleAddToStoryline}
            variant='contained'
            disabled={!selectedStoryline && !newStorylineTitle.trim()}
          >
            Add to Storyline
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmation Dialog */}
      <StorylineConfirmationDialog
        open={confirmationDialog.open}
        onClose={handleCloseConfirmation}
        onConfirm={handleConfirmAction}
        action={confirmationDialog.action}
        storyline={confirmationDialog.storyline}
        loading={actionLoading}
      />

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default ArticleReader;
