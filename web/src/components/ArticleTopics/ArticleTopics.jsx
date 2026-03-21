import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Divider,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  AutoAwesome,
  CheckCircle,
  Cancel,
  RateReview,
  ThumbUp,
  ThumbDown,
  Refresh,
} from '@mui/icons-material';
import apiService from '../../services/apiService';

const ArticleTopics = ({ articleId }) => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  useEffect(() => {
    if (articleId) {
      loadArticleTopics();
    }
  }, [articleId]);

  const loadArticleTopics = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticleTopics(articleId);

      if (response.success) {
        setTopics(response.data.topics || []);
      } else {
        setError(response.error || 'Failed to load topics');
      }
    } catch (err) {
      setError('Error loading topics: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleProcessTopics = async () => {
    try {
      setProcessing(true);
      setError(null);
      const response = await apiService.processArticleTopics(articleId);

      if (response.success) {
        await loadArticleTopics();
      } else {
        setError(response.error || 'Failed to process topics');
      }
    } catch (err) {
      setError('Error processing topics: ' + err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleSubmitFeedback = async (isCorrect, feedbackNotes) => {
    if (!selectedAssignment) return;

    try {
      setFeedbackLoading(true);
      const response = await apiService.submitTopicFeedback(
        selectedAssignment.id,
        {
          is_correct: isCorrect,
          feedback_notes: feedbackNotes,
          validated_by: 'current_user', // TODO: Get from auth context
        }
      );

      if (response.success) {
        await loadArticleTopics();
        setFeedbackDialogOpen(false);
        setSelectedAssignment(null);
        setError(null);
      } else {
        setError(response.error || 'Failed to submit feedback');
      }
    } catch (err) {
      setError('Error submitting feedback: ' + err.message);
    } finally {
      setFeedbackLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant='h6'>Topics</Typography>
          <Button
            size='small'
            variant='outlined'
            startIcon={
              processing ? <CircularProgress size={16} /> : <AutoAwesome />
            }
            onClick={handleProcessTopics}
            disabled={processing}
          >
            {processing ? 'Processing...' : 'Extract Topics'}
          </Button>
        </Box>

        {error && (
          <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {topics.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 3 }}>
            <Typography variant='body2' color='text.secondary' gutterBottom>
              No topics assigned yet
            </Typography>
            <Button
              size='small'
              variant='outlined'
              startIcon={<AutoAwesome />}
              onClick={handleProcessTopics}
              disabled={processing}
            >
              Extract Topics with AI
            </Button>
          </Box>
        ) : (
          <List>
            {topics.map((topic, index) => (
              <React.Fragment key={index}>
                <ListItem>
                  <ListItemText
                    primary={
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <Typography variant='body1'>
                          {topic.topic_name}
                        </Typography>
                        <Chip
                          label={topic.category || 'other'}
                          size='small'
                          variant='outlined'
                        />
                        {topic.is_validated && (
                          <Chip
                            icon={
                              topic.is_correct ? <CheckCircle /> : <Cancel />
                            }
                            label={topic.is_correct ? 'Correct' : 'Incorrect'}
                            size='small'
                            color={topic.is_correct ? 'success' : 'error'}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box sx={{ mt: 1 }}>
                        <Typography variant='body2' color='text.secondary'>
                          Confidence:{' '}
                          {(topic.confidence_score * 100).toFixed(1)}% |{' '}
                          Relevance: {(topic.relevance_score * 100).toFixed(1)}%
                        </Typography>
                        {topic.feedback_notes && (
                          <Typography
                            variant='caption'
                            color='text.secondary'
                            sx={{ mt: 0.5, display: 'block' }}
                          >
                            Note: {topic.feedback_notes}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    {!topic.is_validated ? (
                      <Tooltip title='Review this assignment'>
                        <IconButton
                          size='small'
                          onClick={() => {
                            setSelectedAssignment({
                              id: topic.id || index, // Use index as fallback
                              topic_name: topic.topic_name,
                              confidence_score: topic.confidence_score,
                            });
                            setFeedbackDialogOpen(true);
                          }}
                        >
                          <RateReview />
                        </IconButton>
                      </Tooltip>
                    ) : (
                      <Tooltip title='Already reviewed'>
                        <IconButton size='small' disabled>
                          <CheckCircle color='success' />
                        </IconButton>
                      </Tooltip>
                    )}
                  </ListItemSecondaryAction>
                </ListItem>
                {index < topics.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        )}

        {/* Feedback Dialog */}
        <Dialog
          open={feedbackDialogOpen}
          onClose={() => {
            setFeedbackDialogOpen(false);
            setSelectedAssignment(null);
          }}
          maxWidth='sm'
          fullWidth
        >
          <DialogTitle>Review Topic Assignment</DialogTitle>
          <DialogContent>
            {selectedAssignment && (
              <Box sx={{ mt: 2 }}>
                <Typography variant='body2' color='text.secondary' gutterBottom>
                  Topic: <strong>{selectedAssignment.topic_name}</strong>
                </Typography>
                <Typography variant='body2' color='text.secondary' gutterBottom>
                  Confidence:{' '}
                  {(selectedAssignment.confidence_score * 100).toFixed(1)}%
                </Typography>
                <Divider sx={{ my: 2 }} />
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label='Feedback Notes (Optional)'
                  placeholder='Add any notes about this assignment...'
                  id='feedback-notes'
                  sx={{ mb: 2 }}
                />
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button
              onClick={() => {
                setFeedbackDialogOpen(false);
                setSelectedAssignment(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                const notes =
                  document.getElementById('feedback-notes')?.value || '';
                handleSubmitFeedback(false, notes);
              }}
              color='error'
              startIcon={<ThumbDown />}
              disabled={feedbackLoading}
            >
              Incorrect
            </Button>
            <Button
              onClick={() => {
                const notes =
                  document.getElementById('feedback-notes')?.value || '';
                handleSubmitFeedback(true, notes);
              }}
              color='success'
              startIcon={<ThumbUp />}
              disabled={feedbackLoading}
              variant='contained'
            >
              {feedbackLoading ? <CircularProgress size={20} /> : 'Correct'}
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default ArticleTopics;
