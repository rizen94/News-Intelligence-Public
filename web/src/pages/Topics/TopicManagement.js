import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Badge,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Rating,
  Tabs,
  Tab,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Snackbar,
} from '@mui/material';
import {
  TrendingUp,
  Article,
  Search,
  Refresh,
  CheckCircle,
  Cancel,
  RateReview,
  Psychology,
  ExpandMore,
  Visibility,
  AutoAwesome,
  Warning,
  ThumbUp,
  ThumbDown,
  Edit,
  BarChart,
  MergeType,
  SelectAll,
} from '@mui/icons-material';
import {
  Checkbox,
} from '@mui/material';
import { apiService } from '../../services/apiService';

const TopicManagement = () => {
  const navigate = useNavigate();
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('accuracy_score');
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [topicArticles, setTopicArticles] = useState([]);
  const [topicsNeedingReview, setTopicsNeedingReview] = useState([]);
  const [activeTab, setActiveTab] = useState(0);
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [processingArticle, setProcessingArticle] = useState(null);
  const [selectedAssignments, setSelectedAssignments] = useState(new Set());
  const [bulkReviewDialogOpen, setBulkReviewDialogOpen] = useState(false);
  const [bulkReviewAction, setBulkReviewAction] = useState(null);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [topicsToMerge, setTopicsToMerge] = useState([]);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success',
  });

  const loadTopics = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        limit: 100,
        offset: 0,
        search: searchQuery || undefined,
        category: selectedCategory || undefined,
        status: statusFilter || undefined,
        sort_by: sortBy,
      };

      const response = await apiService.getManagedTopics(params);

      if (response.success) {
        setTopics(response.data.topics || []);
      } else {
        setError(response.message || 'Failed to load topics');
      }
    } catch (err) {
      setError('Error loading topics: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedCategory, statusFilter, sortBy]);

  const loadTopicsNeedingReview = useCallback(async() => {
    try {
      const response = await apiService.getTopicsNeedingReview(0.6, 50);

      if (response.success) {
        setTopicsNeedingReview(response.data.topics || []);
      }
    } catch (err) {
      console.error('Error loading topics needing review:', err);
    }
  }, []);

  const loadTopicArticles = useCallback(async(topicId) => {
    try {
      const response = await apiService.getManagedTopicArticles(topicId, { limit: 50 });

      if (response.success) {
        setTopicArticles(response.data.articles || []);
      }
    } catch (err) {
      console.error('Error loading topic articles:', err);
    }
  }, []);

  const loadTopicDetails = useCallback(async(topicId) => {
    try {
      const response = await apiService.getManagedTopic(topicId);

      if (response.success) {
        setSelectedTopic(response.data);
        await loadTopicArticles(topicId);
      }
    } catch (err) {
      console.error('Error loading topic details:', err);
    }
  }, [loadTopicArticles]);

  const handleSubmitFeedback = async(isCorrect, feedbackNotes) => {
    if (!selectedAssignment) return;

    try {
      setFeedbackLoading(true);
      const response = await apiService.submitTopicFeedback(
        selectedAssignment.id,
        {
          is_correct: isCorrect,
          feedback_notes: feedbackNotes,
          validated_by: 'current_user', // TODO: Get from auth context
        },
      );

      if (response.success) {
        // Reload topics to show updated accuracy
        await loadTopics();
        await loadTopicsNeedingReview();
        if (selectedTopic) {
          await loadTopicDetails(selectedTopic.id);
        }
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

  const handleBulkReview = async(isCorrect, feedbackNotes) => {
    if (selectedAssignments.size === 0) return;

    try {
      setFeedbackLoading(true);
      const assignments = Array.from(selectedAssignments);
      const results = await Promise.allSettled(
        assignments.map(assignmentId =>
          apiService.submitTopicFeedback(assignmentId, {
            is_correct: isCorrect,
            feedback_notes: feedbackNotes,
            validated_by: 'current_user',
          }),
        ),
      );

      const successCount = results.filter(r => r.status === 'fulfilled' && r.value.success).length;

      if (successCount > 0) {
        await loadTopics();
        await loadTopicsNeedingReview();
        if (selectedTopic) {
          await loadTopicDetails(selectedTopic.id);
        }
        setSelectedAssignments(new Set());
        setBulkReviewDialogOpen(false);
        setError(null);
        setSnackbar({
          open: true,
          message: `Successfully reviewed ${successCount} assignment${successCount > 1 ? 's' : ''}`,
          severity: 'success',
        });
      } else {
        setError('Failed to submit bulk feedback');
      }
    } catch (err) {
      setError('Error submitting bulk feedback: ' + err.message);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const handleToggleAssignment = (assignmentId) => {
    const newSelected = new Set(selectedAssignments);
    if (newSelected.has(assignmentId)) {
      newSelected.delete(assignmentId);
    } else {
      newSelected.add(assignmentId);
    }
    setSelectedAssignments(newSelected);
  };

  const handleSelectAllAssignments = () => {
    const unvalidated = topicArticles
      .filter(a => !a.is_validated)
      .map(a => a.assignment_id || a.id);

    if (selectedAssignments.size === unvalidated.length) {
      setSelectedAssignments(new Set());
    } else {
      setSelectedAssignments(new Set(unvalidated));
    }
  };

  const handleMergeTopics = async() => {
    if (topicsToMerge.length < 2) {
      setError('Please select at least 2 topics to merge');
      return;
    }

    try {
      setFeedbackLoading(true);
      setError(null);
      
      const topicIds = topicsToMerge.map(t => t.id);
      const result = await apiService.mergeTopics(topicIds);
      
      if (result.success) {
        setSnackbar({
          open: true,
          message: result.data?.message || `Successfully merged ${topicsToMerge.length} topics`,
          severity: 'success',
        });
        setMergeDialogOpen(false);
        setTopicsToMerge([]);
        // Reload topics to show updated list
        loadTopics();
      } else {
        setError(result.error || 'Failed to merge topics');
        setSnackbar({
          open: true,
          message: result.error || 'Failed to merge topics',
          severity: 'error',
        });
      }
    } catch (err) {
      const errorMessage = err.message || 'Error merging topics';
      setError(errorMessage);
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error',
      });
    } finally {
      setFeedbackLoading(false);
    }
  };

  const handleProcessArticle = async(articleId) => {
    try {
      setProcessingArticle(articleId);
      const response = await apiService.processArticleTopics(articleId);

      if (response.success) {
        // Reload topics
        await loadTopics();
        if (selectedTopic) {
          await loadTopicDetails(selectedTopic.id);
        }
        setError(null);
      } else {
        setError(response.error || 'Failed to process article');
      }
    } catch (err) {
      setError('Error processing article: ' + err.message);
    } finally {
      setProcessingArticle(null);
    }
  };

  useEffect(() => {
    loadTopics();
    loadTopicsNeedingReview();
  }, [loadTopics, loadTopicsNeedingReview]);

  const getAccuracyColor = (accuracy) => {
    if (accuracy >= 0.8) return 'success';
    if (accuracy >= 0.6) return 'warning';
    return 'error';
  };

  const getAccuracyLabel = (accuracy) => {
    if (accuracy >= 0.8) return 'High';
    if (accuracy >= 0.6) return 'Medium';
    return 'Low';
  };

  const FeedbackDialog = () => (
    <Dialog
      open={feedbackDialogOpen}
      onClose={() => {
        setFeedbackDialogOpen(false);
        setSelectedAssignment(null);
      }}
      maxWidth='sm'
      fullWidth
    >
      <DialogTitle>
        Review Topic Assignment
      </DialogTitle>
      <DialogContent>
        {selectedAssignment && (
          <Box sx={{ mt: 2 }}>
            <Typography variant='body2' color='text.secondary' gutterBottom>
              Article: {selectedAssignment.article_title || 'Unknown'}
            </Typography>
            <Typography variant='body2' color='text.secondary' gutterBottom>
              Topic: {selectedAssignment.topic_name || 'Unknown'}
            </Typography>
            <Typography variant='body2' color='text.secondary' gutterBottom>
              Confidence: {(selectedAssignment.confidence_score * 100).toFixed(1)}%
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
          onClick={() => handleSubmitFeedback(false, document.getElementById('feedback-notes')?.value || '')}
          color='error'
          startIcon={<ThumbDown />}
          disabled={feedbackLoading}
        >
          Incorrect
        </Button>
        <Button
          onClick={() => handleSubmitFeedback(true, document.getElementById('feedback-notes')?.value || '')}
          color='success'
          startIcon={<ThumbUp />}
          disabled={feedbackLoading}
          variant='contained'
        >
          {feedbackLoading ? <CircularProgress size={20} /> : 'Correct'}
        </Button>
      </DialogActions>
    </Dialog>
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h4' gutterBottom>
        🏷️ Topic Management & Learning
      </Typography>

      <Typography variant='body1' color='text.secondary' sx={{ mb: 3 }}>
        Manage topics, review assignments, and improve accuracy through iterative learning.
        The system learns from your feedback to provide better topic assignments over time.
      </Typography>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems='center'>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label='Search Topics'
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <Search sx={{ mr: 1, color: 'text.secondary' }} />
                  ),
                }}
                placeholder='Search topics...'
              />
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  label='Category'
                >
                  <MenuItem value=''>All</MenuItem>
                  <MenuItem value='politics'>Politics</MenuItem>
                  <MenuItem value='business'>Business</MenuItem>
                  <MenuItem value='technology'>Technology</MenuItem>
                  <MenuItem value='health'>Health</MenuItem>
                  <MenuItem value='environment'>Environment</MenuItem>
                  <MenuItem value='international'>International</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  label='Status'
                >
                  <MenuItem value=''>All</MenuItem>
                  <MenuItem value='active'>Active</MenuItem>
                  <MenuItem value='reviewed'>Reviewed</MenuItem>
                  <MenuItem value='archived'>Archived</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  label='Sort By'
                >
                  <MenuItem value='accuracy_score'>Accuracy</MenuItem>
                  <MenuItem value='confidence_score'>Confidence</MenuItem>
                  <MenuItem value='review_count'>Reviews</MenuItem>
                  <MenuItem value='name'>Name</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant='outlined'
                startIcon={<Refresh />}
                onClick={() => {
                  loadTopics();
                  loadTopicsNeedingReview();
                }}
                disabled={loading}
              >
                Refresh
              </Button>
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant='outlined'
                startIcon={<MergeType />}
                onClick={() => setMergeDialogOpen(true)}
                disabled={loading}
              >
                Merge Topics
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity='error' sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
          variant='fullWidth'
        >
          <Tab icon={<Article />} label='All Topics' iconPosition='start' />
          <Tab
            icon={<Warning />}
            label={
              <Badge badgeContent={topicsNeedingReview.length} color='error'>
                Needs Review
              </Badge>
            }
            iconPosition='start'
          />
          {selectedTopic && (
            <Tab
              icon={<Visibility />}
              label='Topic Details'
              iconPosition='start'
            />
          )}
        </Tabs>
      </Paper>

      {/* Tab Content: All Topics */}
      {activeTab === 0 && (
        <>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Grid container spacing={3}>
              {topics.map((topic) => (
                <Grid item xs={12} md={6} lg={4} key={topic.id}>
                  <Card
                    sx={{
                      height: '100%',
                      cursor: 'pointer',
                      '&:hover': { boxShadow: 3 },
                      border:
                        selectedTopic?.id === topic.id
                          ? '2px solid'
                          : 'none',
                      borderColor: 'primary.main',
                    }}
                    onClick={() => {
                      setSelectedTopic(topic);
                      loadTopicDetails(topic.id);
                      setActiveTab(2);
                    }}
                  >
                    <CardContent>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          mb: 2,
                        }}
                      >
                        <Typography
                          variant='h6'
                          component='div'
                          sx={{ fontWeight: 'bold' }}
                        >
                          {topic.name}
                        </Typography>
                        <Badge badgeContent={topic.article_count} color='primary'>
                          <Article />
                        </Badge>
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Chip
                          label={topic.category || 'other'}
                          size='small'
                          color='primary'
                          variant='outlined'
                          sx={{ mr: 1 }}
                        />
                        <Chip
                          label={topic.is_auto_generated ? 'Auto' : 'Manual'}
                          size='small'
                          variant='outlined'
                        />
                      </Box>

                      {/* Accuracy Metrics */}
                      <Box sx={{ mb: 2 }}>
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            mb: 1,
                          }}
                        >
                          <Typography variant='body2' color='text.secondary'>
                            Accuracy:
                          </Typography>
                          <Chip
                            label={`${(topic.accuracy_score * 100).toFixed(0)}%`}
                            size='small'
                            color={getAccuracyColor(topic.accuracy_score)}
                          />
                        </Box>
                        <LinearProgress
                          variant='determinate'
                          value={topic.accuracy_score * 100}
                          color={getAccuracyColor(topic.accuracy_score)}
                          sx={{ height: 8, borderRadius: 4 }}
                        />
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Typography variant='body2' color='text.secondary'>
                          Confidence: {(topic.confidence_score * 100).toFixed(1)}%
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          Reviews: {topic.review_count} (
                          {topic.correct_assignments} correct,{' '}
                          {topic.incorrect_assignments} incorrect)
                        </Typography>
                      </Box>

                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <Typography variant='caption' color='text.secondary'>
                          {topic.status}
                        </Typography>
                        <IconButton
                          size='small'
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTopic(topic);
                            loadTopicDetails(topic.id);
                            setActiveTab(2);
                          }}
                        >
                          <Visibility />
                        </IconButton>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}

      {/* Tab Content: Topics Needing Review */}
      {activeTab === 1 && (
        <>
          {topicsNeedingReview.length === 0 ? (
            <Card>
              <CardContent>
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <CheckCircle
                    sx={{ fontSize: 48, color: 'success.main', mb: 2 }}
                  />
                  <Typography variant='h6' color='text.secondary' gutterBottom>
                    All topics reviewed!
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    No topics currently need review. Great job!
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          ) : (
            <Grid container spacing={3}>
              {topicsNeedingReview.map((topic) => (
                <Grid item xs={12} md={6} key={topic.topic_id}>
                  <Card
                    sx={{
                      border: '2px solid',
                      borderColor: 'error.main',
                    }}
                  >
                    <CardContent>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          mb: 2,
                        }}
                      >
                        <Typography variant='h6'>{topic.topic_name}</Typography>
                        <Chip
                          label={`${(topic.accuracy_score * 100).toFixed(0)}%`}
                          color='error'
                          size='small'
                        />
                      </Box>

                      <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
                        Review Count: {topic.review_count} | Incorrect:{' '}
                        {topic.incorrect_assignments}
                      </Typography>

                      <LinearProgress
                        variant='determinate'
                        value={topic.accuracy_score * 100}
                        color='error'
                        sx={{ height: 8, borderRadius: 4, mb: 2 }}
                      />

                      <Button
                        fullWidth
                        variant='contained'
                        startIcon={<RateReview />}
                        onClick={() => {
                          setSelectedTopic({ id: topic.topic_id, name: topic.topic_name });
                          loadTopicDetails(topic.topic_id);
                          setActiveTab(2);
                        }}
                      >
                        Review Topic
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}

      {/* Tab Content: Topic Details */}
      {activeTab === 2 && selectedTopic && (
        <Card>
          <CardContent>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 3,
              }}
            >
              <Typography variant='h5' gutterBottom sx={{ mb: 0 }}>
                {selectedTopic.name}
              </Typography>
              <Chip
                label={selectedTopic.category || 'other'}
                color='primary'
              />
            </Box>

            {/* Topic Metrics */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={12} md={3}>
                <Card variant='outlined'>
                  <CardContent>
                    <Typography variant='h6' color='primary'>
                      {selectedTopic.article_count || 0}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Articles
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card variant='outlined'>
                  <CardContent>
                    <Typography
                      variant='h6'
                      color={getAccuracyColor(selectedTopic.accuracy_score)}
                    >
                      {(selectedTopic.accuracy_score * 100).toFixed(1)}%
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Accuracy
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card variant='outlined'>
                  <CardContent>
                    <Typography variant='h6' color='primary'>
                      {selectedTopic.review_count || 0}
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Reviews
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={3}>
                <Card variant='outlined'>
                  <CardContent>
                    <Typography variant='h6' color='primary'>
                      {(selectedTopic.confidence_score * 100).toFixed(1)}%
                    </Typography>
                    <Typography variant='body2' color='text.secondary'>
                      Confidence
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Accuracy Progress */}
            <Box sx={{ mb: 3 }}>
              <Typography variant='h6' gutterBottom>
                Learning Progress
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    mb: 1,
                  }}
                >
                  <Typography variant='body2' color='text.secondary'>
                    Accuracy Score
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    {selectedTopic.correct_assignments || 0} correct /{' '}
                    {(selectedTopic.correct_assignments || 0) +
                      (selectedTopic.incorrect_assignments || 0)}{' '}
                    total
                  </Typography>
                </Box>
                <LinearProgress
                  variant='determinate'
                  value={selectedTopic.accuracy_score * 100}
                  color={getAccuracyColor(selectedTopic.accuracy_score)}
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
            </Box>

            {/* Topic Articles with Feedback */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', mr: 2 }}>
                  <Typography variant='h6'>
                    Articles ({topicArticles.length})
                  </Typography>
                  {topicArticles.filter(a => !a.is_validated).length > 0 && (
                    <Button
                      size='small'
                      variant='outlined'
                      startIcon={<SelectAll />}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectAllAssignments();
                      }}
                    >
                      {selectedAssignments.size === topicArticles.filter(a => !a.is_validated).length
                        ? 'Deselect All'
                        : 'Select All Unreviewed'}
                    </Button>
                  )}
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {selectedAssignments.size > 0 && (
                  <Box sx={{ mb: 2, p: 2, bgcolor: 'action.selected', borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Typography variant='body2'>
                        {selectedAssignments.size} assignment{selectedAssignments.size > 1 ? 's' : ''} selected
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                          size='small'
                          variant='contained'
                          color='success'
                          startIcon={<ThumbUp />}
                          onClick={() => {
                            setBulkReviewAction('correct');
                            setBulkReviewDialogOpen(true);
                          }}
                        >
                          Mark Correct
                        </Button>
                        <Button
                          size='small'
                          variant='contained'
                          color='error'
                          startIcon={<ThumbDown />}
                          onClick={() => {
                            setBulkReviewAction('incorrect');
                            setBulkReviewDialogOpen(true);
                          }}
                        >
                          Mark Incorrect
                        </Button>
                        <Button
                          size='small'
                          onClick={() => setSelectedAssignments(new Set())}
                        >
                          Clear
                        </Button>
                      </Box>
                    </Box>
                  </Box>
                )}
                <List>
                  {topicArticles.map((article) => {
                    const assignmentId = article.assignment_id || article.id;
                    const isSelected = selectedAssignments.has(assignmentId);
                    const isUnvalidated = !article.is_validated;

                    return (
                      <ListItem key={article.id} divider>
                        {isUnvalidated && (
                          <Checkbox
                            checked={isSelected}
                            onChange={() => handleToggleAssignment(assignmentId)}
                            sx={{ mr: 1 }}
                          />
                        )}
                        {!isUnvalidated && <Box sx={{ width: 40 }} />}
                        <ListItemText
                          primary={
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                              }}
                            >
                              <Typography variant='body1'>
                                {article.title}
                              </Typography>
                              {article.is_validated && (
                                <Chip
                                  icon={
                                    article.is_correct ? (
                                      <CheckCircle />
                                    ) : (
                                      <Cancel />
                                    )
                                  }
                                  label={article.is_correct ? 'Correct' : 'Incorrect'}
                                  size='small'
                                  color={article.is_correct ? 'success' : 'error'}
                                />
                              )}
                            </Box>
                          }
                          secondary={
                            <Box>
                              <Typography variant='body2' color='text.secondary'>
                                {article.source_domain} •{' '}
                                {article.published_at
                                  ? new Date(article.published_at).toLocaleDateString()
                                  : 'N/A'}
                              </Typography>
                              <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                                <Chip
                                  label={`${(article.confidence_score * 100).toFixed(0)}% confidence`}
                                  size='small'
                                  variant='outlined'
                                />
                                {!article.is_validated && (
                                  <Chip
                                    label='Needs Review'
                                    size='small'
                                    color='warning'
                                  />
                                )}
                              </Box>
                              {article.feedback_notes && (
                                <Typography variant='caption' color='text.secondary' sx={{ mt: 0.5, display: 'block' }}>
                                  Note: {article.feedback_notes}
                                </Typography>
                              )}
                            </Box>
                          }
                        />
                        <ListItemSecondaryAction>
                          {!article.is_validated ? (
                            <Button
                              size='small'
                              startIcon={<RateReview />}
                              onClick={() => {
                                setSelectedAssignment({
                                  id: article.assignment_id || article.id,
                                  article_title: article.title,
                                  topic_name: selectedTopic.name,
                                  confidence_score: article.confidence_score,
                                });
                                setFeedbackDialogOpen(true);
                              }}
                            >
                              Review
                            </Button>
                          ) : (
                            <Tooltip title='Already reviewed'>
                              <IconButton size='small' disabled>
                                <CheckCircle color='success' />
                              </IconButton>
                            </Tooltip>
                          )}
                        </ListItemSecondaryAction>
                      </ListItem>
                    );
                  })}
                </List>
              </AccordionDetails>
            </Accordion>
          </CardContent>
        </Card>
      )}

      <FeedbackDialog />

      {/* Bulk Review Dialog */}
      <Dialog
        open={bulkReviewDialogOpen}
        onClose={() => {
          setBulkReviewDialogOpen(false);
          setBulkReviewAction(null);
        }}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>
          Bulk Review {selectedAssignments.size} Assignment{selectedAssignments.size > 1 ? 's' : ''}
        </DialogTitle>
        <DialogContent>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
            Mark all selected assignments as {bulkReviewAction === 'correct' ? 'correct' : 'incorrect'}?
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={3}
            label='Feedback Notes (Optional)'
            placeholder='Add notes that will apply to all selected assignments...'
            id='bulk-feedback-notes'
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setBulkReviewDialogOpen(false);
              setBulkReviewAction(null);
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              const notes = document.getElementById('bulk-feedback-notes')?.value || '';
              handleBulkReview(bulkReviewAction === 'correct', notes);
            }}
            color={bulkReviewAction === 'correct' ? 'success' : 'error'}
            variant='contained'
            disabled={feedbackLoading}
          >
            {feedbackLoading ? <CircularProgress size={20} /> : `Mark as ${bulkReviewAction === 'correct' ? 'Correct' : 'Incorrect'}`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Topic Merge Dialog */}
      <Dialog
        open={mergeDialogOpen}
        onClose={() => {
          setMergeDialogOpen(false);
          setTopicsToMerge([]);
        }}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MergeType />
            Merge Topics
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
            Select topics to merge. The first topic will be kept, and others will be merged into it.
          </Typography>
          <List>
            {topics.map(topic => (
              <ListItem key={topic.id}>
                <Checkbox
                  checked={topicsToMerge.some(t => t.id === topic.id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setTopicsToMerge([...topicsToMerge, topic]);
                    } else {
                      setTopicsToMerge(topicsToMerge.filter(t => t.id !== topic.id));
                    }
                  }}
                />
                <ListItemText
                  primary={topic.name}
                  secondary={`${topic.article_count || 0} articles • ${(topic.accuracy_score * 100).toFixed(0)}% accuracy`}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setMergeDialogOpen(false);
              setTopicsToMerge([]);
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleMergeTopics}
            variant='contained'
            disabled={topicsToMerge.length < 2 || feedbackLoading}
            startIcon={<MergeType />}
          >
            {feedbackLoading ? <CircularProgress size={20} /> : `Merge ${topicsToMerge.length} Topics`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default TopicManagement;

