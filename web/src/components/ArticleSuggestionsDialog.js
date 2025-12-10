import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  Card,
  CardContent,
  Chip,
  Stack,
  Divider,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  Check as CheckIcon,
  Close as RejectIcon,
  Search as SearchIcon,
  AutoAwesome as AutoAwesomeIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { apiService } from '../services/apiService';
import { useDomain } from '../contexts/DomainContext';

const ArticleSuggestionsDialog = ({
  open,
  onClose,
  storylineId,
  onArticleAdded,
}) => {
  const { domain } = useDomain();
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [processing, setProcessing] = useState(new Set());
  const [discoverStatus, setDiscoverStatus] = useState({ message: null, severity: 'info' });

  useEffect(() => {
    if (open && storylineId) {
      loadSuggestions();
      setDiscoverStatus({ message: null, severity: 'info' });
    }
  }, [open, storylineId]);

  const loadSuggestions = async() => {
    try {
      setLoading(true);
      const response = await apiService.getArticleSuggestions(storylineId, 'pending');

      if (response.success) {
        setSuggestions(response.data.suggestions || []);
      }
    } catch (err) {
      console.error('Error loading suggestions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async(suggestionId, articleId) => {
    try {
      setProcessing((prev) => new Set(prev).add(suggestionId));
      const response = await apiService.approveSuggestion(storylineId, suggestionId, domain);

      if (response && response.success) {
        setSuggestions((prev) => prev.filter((s) => s.suggestion_id !== suggestionId));
        setDiscoverStatus({ message: 'Article added to storyline successfully', severity: 'success' });
        setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 3000);
        if (onArticleAdded) {
          onArticleAdded();
        }
      } else {
        const errorMsg = response?.error || response?.message || 'Failed to approve suggestion';
        setDiscoverStatus({ message: errorMsg, severity: 'error' });
        setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
      }
    } catch (err) {
      console.error('Error approving suggestion:', err);
      setDiscoverStatus({ message: 'Failed to approve suggestion', severity: 'error' });
      setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
    } finally {
      setProcessing((prev) => {
        const next = new Set(prev);
        next.delete(suggestionId);
        return next;
      });
    }
  };

  const handleReject = async(suggestionId) => {
    try {
      setProcessing((prev) => new Set(prev).add(suggestionId));
      const response = await apiService.rejectSuggestion(storylineId, suggestionId, 'Not relevant', domain);

      if (response && response.success) {
        setSuggestions((prev) => prev.filter((s) => s.suggestion_id !== suggestionId));
        setDiscoverStatus({ message: 'Suggestion rejected', severity: 'info' });
        setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 2000);
      } else {
        const errorMsg = response?.error || response?.message || 'Failed to reject suggestion';
        setDiscoverStatus({ message: errorMsg, severity: 'error' });
        setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
      }
    } catch (err) {
      console.error('Error rejecting suggestion:', err);
      setDiscoverStatus({ message: 'Failed to reject suggestion', severity: 'error' });
      setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
    } finally {
      setProcessing((prev) => {
        const next = new Set(prev);
        next.delete(suggestionId);
        return next;
      });
    }
  };

  const handleDiscover = async() => {
    try {
      setLoading(true);
      setDiscoverStatus({ message: 'Finding articles...', severity: 'info' });
      const response = await apiService.discoverArticles(storylineId, true, domain);

      if (response && response.success) {
        const message = `Found ${response.articles_found || 0} articles. ${response.articles_suggested || 0} added to suggestions.`;
        setDiscoverStatus({ message, severity: 'success' });
        await loadSuggestions();
        setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
      } else {
        const errorMsg = response?.error || response?.message || 'Failed to find articles';
        setDiscoverStatus({ message: errorMsg, severity: 'error' });
        setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
      }
    } catch (err) {
      console.error('Error finding articles:', err);
      setDiscoverStatus({ message: 'Failed to find articles', severity: 'error' });
      setTimeout(() => setDiscoverStatus({ message: null, severity: 'info' }), 5000);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 0.7) return 'success';
    if (score >= 0.5) return 'warning';
    return 'default';
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth='md'
      fullWidth
      PaperProps={{
        sx: { minHeight: '600px' },
      }}
    >
      <DialogTitle>
        <Box display='flex' justifyContent='space-between' alignItems='center'>
          <Box display='flex' alignItems='center' gap={1}>
            <AutoAwesomeIcon color='primary' />
            <Typography variant='h6'>Find Articles</Typography>
          </Box>
          <Box display='flex' gap={1}>
            <Tooltip title='Find Articles'>
              <IconButton
                onClick={handleDiscover}
                disabled={loading}
                size='small'
                color='primary'
              >
                <SearchIcon />
              </IconButton>
            </Tooltip>
            <IconButton onClick={onClose} size='small'>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent>
        {discoverStatus.message && (
          <Alert severity={discoverStatus.severity} sx={{ mb: 2 }} onClose={() => setDiscoverStatus({ message: null, severity: 'info' })}>
            {discoverStatus.message}
          </Alert>
        )}
        {loading && suggestions.length === 0 ? (
          <Box display='flex' flexDirection='column' alignItems='center' justifyContent='center' p={4}>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography variant='body2' color='text.secondary'>
              Finding articles...
            </Typography>
          </Box>
        ) : suggestions.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <AutoAwesomeIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
            <Typography variant='h6' color='text.secondary' gutterBottom>
              No pending suggestions
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 3 }}>
              Find relevant articles for this storyline using AI-powered search.
            </Typography>
            <Button
              variant='contained'
              startIcon={loading ? <CircularProgress size={16} /> : <SearchIcon />}
              onClick={handleDiscover}
              disabled={loading}
              size='large'
            >
              {loading ? 'Finding Articles...' : 'Find Articles'}
            </Button>
          </Box>
        ) : (
          <Stack spacing={2}>
            {suggestions.map((suggestion) => (
              <Card key={suggestion.suggestion_id} variant='outlined'>
                <CardContent>
                  <Box display='flex' justifyContent='space-between' mb={1}>
                    <Typography variant='h6' component='div'>
                      {suggestion.article.title}
                    </Typography>
                    <Box display='flex' gap={1}>
                      <Tooltip title='Approve and add to storyline'>
                        <span>
                          <IconButton
                            size='small'
                            color='success'
                            onClick={() => handleApprove(suggestion.suggestion_id, suggestion.article.id)}
                            disabled={processing.has(suggestion.suggestion_id)}
                          >
                            {processing.has(suggestion.suggestion_id) ? (
                              <CircularProgress size={16} />
                            ) : (
                              <CheckIcon />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title='Reject suggestion'>
                        <span>
                          <IconButton
                            size='small'
                            color='error'
                            onClick={() => handleReject(suggestion.suggestion_id)}
                            disabled={processing.has(suggestion.suggestion_id)}
                          >
                            {processing.has(suggestion.suggestion_id) ? (
                              <CircularProgress size={16} />
                            ) : (
                              <RejectIcon />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Box>
                  </Box>

                  {suggestion.article.summary && (
                    <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
                      {suggestion.article.summary}
                    </Typography>
                  )}

                  <Box display='flex' gap={1} flexWrap='wrap' sx={{ mb: 2 }}>
                    <Chip
                      label={suggestion.article.source_domain}
                      size='small'
                      variant='outlined'
                    />
                    {suggestion.article.published_at && (
                      <Chip
                        label={new Date(suggestion.article.published_at).toLocaleDateString()}
                        size='small'
                        variant='outlined'
                      />
                    )}
                  </Box>

                  {suggestion.reasoning && (
                    <Typography variant='caption' color='text.secondary' sx={{ mb: 1, display: 'block' }}>
                      <strong>Why suggested:</strong> {suggestion.reasoning}
                    </Typography>
                  )}

                  <Divider sx={{ my: 1 }} />

                  <Box>
                    <Typography variant='caption' color='text.secondary' gutterBottom display='block'>
                      Relevance Scores:
                    </Typography>
                    <Stack direction='row' spacing={1} flexWrap='wrap'>
                      <Chip
                        label={`Combined: ${(suggestion.scores.combined * 100).toFixed(0)}%`}
                        size='small'
                        color={getScoreColor(suggestion.scores.combined)}
                      />
                      <Chip
                        label={`Relevance: ${(suggestion.scores.relevance * 100).toFixed(0)}%`}
                        size='small'
                        variant='outlined'
                      />
                      <Chip
                        label={`Quality: ${(suggestion.scores.quality * 100).toFixed(0)}%`}
                        size='small'
                        variant='outlined'
                      />
                      <Chip
                        label={`Semantic: ${(suggestion.scores.semantic * 100).toFixed(0)}%`}
                        size='small'
                        variant='outlined'
                      />
                    </Stack>
                  </Box>

                  {suggestion.matched_keywords && suggestion.matched_keywords.length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant='caption' color='text.secondary' gutterBottom display='block'>
                        Matched Keywords:
                      </Typography>
                      <Stack direction='row' spacing={0.5} flexWrap='wrap' gap={0.5}>
                        {suggestion.matched_keywords.map((kw) => (
                          <Chip key={kw} label={kw} size='small' color='primary' variant='outlined' />
                        ))}
                      </Stack>
                    </Box>
                  )}

                  {processing.has(suggestion.suggestion_id) && (
                    <LinearProgress sx={{ mt: 1 }} />
                  )}
                </CardContent>
              </Card>
            ))}
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button
          onClick={loadSuggestions}
          startIcon={<RefreshIcon />}
          variant='outlined'
        >
          Refresh
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ArticleSuggestionsDialog;

