import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  LinearProgress,
  Link,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Check as CheckIcon,
  Close as RejectIcon,
  OpenInNew as OpenInNewIcon,
  PlayArrow as DiscoverIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

import apiService from '../../services/apiService';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { useNotification } from '../../hooks/useNotification';
import { getUserFriendlyError } from '../../utils/errorHandler';
import LoadingState from '../../components/shared/LoadingState';
import EmptyState from '../../components/shared/EmptyState';

interface ReviewSuggestion {
  suggestion_id: number;
  storyline_id: number;
  storyline_title: string;
  article: {
    id: number;
    title: string;
    summary?: string;
    url?: string;
    source_domain?: string;
    published_at?: string;
  };
  scores: {
    combined: number;
    relevance: number;
    quality: number;
    semantic: number;
  };
  reasoning?: string;
  suggested_at?: string;
}

const REJECT_REASONS = [
  { code: 'not_relevant', label: 'Not relevant' },
  { code: 'duplicate', label: 'Duplicate coverage' },
  { code: 'low_quality', label: 'Low quality source' },
  { code: 'wrong_storyline', label: 'Wrong storyline' },
  { code: 'other', label: 'Other' },
];

const StorylineReviewQueue: React.FC = () => {
  const { domain } = useDomainRoute();
  const { showNotification } = useNotification();
  const [loading, setLoading] = useState(true);
  const [suggestions, setSuggestions] = useState<ReviewSuggestion[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [processing, setProcessing] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<ReviewSuggestion | null>(null);
  const [rejectBulk, setRejectBulk] = useState(false);
  const [rejectReason, setRejectReason] = useState('not_relevant');
  const [rejectNotes, setRejectNotes] = useState('');

  const pageSize = 100;

  const loadQueue = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiService.getReviewQueue({
        domain,
        limit: pageSize,
        offset,
      });
      if (res?.success) {
        setSuggestions(res.data?.suggestions || []);
        setTotal(res.data?.total ?? res.data?.count ?? 0);
      } else {
        showNotification(getUserFriendlyError(res?.error || 'Failed to load queue'), 'error');
      }
    } catch (err) {
      showNotification(getUserFriendlyError(err), 'error');
    } finally {
      setLoading(false);
    }
  }, [domain, offset, showNotification]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const filtered = suggestions.filter(s => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      s.article.title?.toLowerCase().includes(q) ||
      s.storyline_title?.toLowerCase().includes(q) ||
      s.article.source_domain?.toLowerCase().includes(q)
    );
  });

  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllFiltered = () => {
    setSelected(new Set(filtered.map(s => s.suggestion_id)));
  };

  const clearSelection = () => setSelected(new Set());

  const handleApprove = async (item: ReviewSuggestion) => {
    const { suggestion_id, storyline_id } = item;
    try {
      setProcessing(prev => new Set(prev).add(suggestion_id));
      const res = await apiService.approveSuggestion(storyline_id, suggestion_id, domain);
      if (res?.success) {
        setSuggestions(prev => prev.filter(s => s.suggestion_id !== suggestion_id));
        setSelected(prev => {
          const next = new Set(prev);
          next.delete(suggestion_id);
          return next;
        });
        setTotal(prev => Math.max(0, prev - 1));
        showNotification('Article added to storyline', 'success');
      } else {
        showNotification(res?.error || res?.detail || 'Approve failed', 'error');
      }
    } catch (err) {
      showNotification(getUserFriendlyError(err), 'error');
    } finally {
      setProcessing(prev => {
        const next = new Set(prev);
        next.delete(suggestion_id);
        return next;
      });
    }
  };

  const openRejectDialog = (item: ReviewSuggestion | null, bulk: boolean) => {
    setRejectTarget(item);
    setRejectBulk(bulk);
    setRejectReason('not_relevant');
    setRejectNotes('');
    setRejectDialogOpen(true);
  };

  const confirmReject = async () => {
    const reasonLabel =
      REJECT_REASONS.find(r => r.code === rejectReason)?.label || rejectReason;
    const notes = rejectNotes.trim() || reasonLabel;
    setRejectDialogOpen(false);

    if (rejectBulk && selected.size > 0) {
      const res = await apiService.bulkRejectSuggestions(domain, {
        suggestion_ids: Array.from(selected),
        reason_code: rejectReason,
        review_notes: notes,
      });
      if (res?.success) {
        const rejected = res.rejected || 0;
        setSuggestions(prev =>
          prev.filter(s => !selected.has(s.suggestion_id))
        );
        setTotal(prev => Math.max(0, prev - rejected));
        clearSelection();
        showNotification(`Rejected ${rejected} suggestion(s)`, 'info');
        loadQueue();
      } else {
        showNotification(res?.error || 'Bulk reject failed', 'error');
      }
      return;
    }

    if (!rejectTarget) return;
    const { suggestion_id, storyline_id } = rejectTarget;
    try {
      setProcessing(prev => new Set(prev).add(suggestion_id));
      const res = await apiService.rejectSuggestion(
        storyline_id,
        suggestion_id,
        notes,
        domain
      );
      if (res?.success) {
        setSuggestions(prev => prev.filter(s => s.suggestion_id !== suggestion_id));
        setTotal(prev => Math.max(0, prev - 1));
        showNotification('Suggestion rejected', 'info');
      } else {
        showNotification(res?.error || res?.detail || 'Reject failed', 'error');
      }
    } catch (err) {
      showNotification(getUserFriendlyError(err), 'error');
    } finally {
      setProcessing(prev => {
        const next = new Set(prev);
        next.delete(suggestion_id);
        return next;
      });
    }
  };

  const handleBulkApprove = async () => {
    if (selected.size === 0) return;
    const res = await apiService.bulkApproveSuggestions(domain, {
      suggestion_ids: Array.from(selected),
    });
    if (res?.success) {
      const approved = res.approved || 0;
      setSuggestions(prev =>
        prev.filter(s => !selected.has(s.suggestion_id))
      );
      setTotal(prev => Math.max(0, prev - approved));
      clearSelection();
      showNotification(`Approved ${approved} suggestion(s)`, 'success');
      loadQueue();
    } else {
      showNotification(res?.error || 'Bulk approve failed', 'error');
    }
  };

  const handleDiscover = async () => {
    try {
      setDiscovering(true);
      const res = await apiService.triggerDomainAutomationDiscovery(domain, {
        force_refresh: true,
        limit: 15,
      });
      if (res?.success) {
        showNotification(
          `Discovery complete — ${res.total_suggested ?? 0} new suggestion(s)`,
          'success'
        );
        loadQueue();
      } else {
        showNotification(res?.error || 'Discovery failed', 'error');
      }
    } catch (err) {
      showNotification(getUserFriendlyError(err), 'error');
    } finally {
      setDiscovering(false);
    }
  };

  const scoreColor = (score: number) => {
    if (score >= 0.7) return 'success';
    if (score >= 0.5) return 'warning';
    return 'default';
  };

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        flexWrap='wrap'
        gap={2}
        mb={3}
      >
        <Box>
          <Typography variant='h4' gutterBottom>
            Storyline Review Queue
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            Approve or reject articles suggested by storyline automation ({domain})
          </Typography>
        </Box>
        <Stack direction='row' spacing={1} alignItems='center' flexWrap='wrap'>
          <Chip
            label={`${total} pending`}
            color={total > 0 ? 'warning' : 'default'}
            variant={total > 0 ? 'filled' : 'outlined'}
          />
          <Button
            variant='contained'
            color='secondary'
            startIcon={discovering ? <CircularProgress size={16} /> : <DiscoverIcon />}
            onClick={handleDiscover}
            disabled={discovering || loading}
          >
            Run discovery
          </Button>
          <Button
            variant='outlined'
            startIcon={<RefreshIcon />}
            onClick={loadQueue}
            disabled={loading}
          >
            Refresh
          </Button>
        </Stack>
      </Box>

      {selected.size > 0 && (
        <Stack direction='row' spacing={1} sx={{ mb: 2 }} flexWrap='wrap'>
          <Chip label={`${selected.size} selected`} onDelete={clearSelection} />
          <Button size='small' variant='contained' color='success' onClick={handleBulkApprove}>
            Approve selected
          </Button>
          <Button
            size='small'
            variant='outlined'
            color='error'
            onClick={() => openRejectDialog(null, true)}
          >
            Reject selected
          </Button>
        </Stack>
      )}

      <Stack direction='row' spacing={1} sx={{ mb: 2 }} alignItems='center'>
        <TextField
          fullWidth
          size='small'
          placeholder='Filter by storyline, article title, or source…'
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ maxWidth: 480 }}
        />
        <Button size='small' onClick={selectAllFiltered} disabled={filtered.length === 0}>
          Select all
        </Button>
      </Stack>

      {loading ? (
        <LoadingState message='Loading review queue…' />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={suggestions.length === 0 ? 'No pending suggestions' : 'No matches'}
          description={
            suggestions.length === 0
              ? 'Run discovery or wait for automation in suggest-only mode.'
              : 'Try a different filter term.'
          }
        />
      ) : (
        <Stack spacing={2}>
          {filtered.map(item => (
            <Card key={item.suggestion_id} variant='outlined'>
              <CardContent>
                <Box display='flex' gap={1} alignItems='flex-start'>
                  <Checkbox
                    checked={selected.has(item.suggestion_id)}
                    onChange={() => toggleSelect(item.suggestion_id)}
                    sx={{ mt: -0.5 }}
                  />
                  <Box flex={1}>
                    <Box
                      display='flex'
                      justifyContent='space-between'
                      alignItems='flex-start'
                      gap={2}
                      mb={1}
                    >
                      <Box flex={1}>
                        <Typography variant='subtitle2' color='text.secondary' gutterBottom>
                          <Link
                            component={RouterLink}
                            to={`/${domain}/storylines/${item.storyline_id}`}
                            underline='hover'
                          >
                            {item.storyline_title}
                          </Link>
                        </Typography>
                        <Typography variant='h6' component='div'>
                          {item.article.title}
                        </Typography>
                      </Box>
                      <Stack direction='row' spacing={0.5}>
                        <Tooltip title='Approve — add to storyline'>
                          <span>
                            <IconButton
                              color='success'
                              size='small'
                              disabled={processing.has(item.suggestion_id)}
                              onClick={() => handleApprove(item)}
                            >
                              {processing.has(item.suggestion_id) ? (
                                <CircularProgress size={18} />
                              ) : (
                                <CheckIcon />
                              )}
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title='Reject suggestion'>
                          <span>
                            <IconButton
                              color='error'
                              size='small'
                              disabled={processing.has(item.suggestion_id)}
                              onClick={() => openRejectDialog(item, false)}
                            >
                              <RejectIcon />
                            </IconButton>
                          </span>
                        </Tooltip>
                        {item.article.url && (
                          <Tooltip title='Open article'>
                            <IconButton
                              size='small'
                              component='a'
                              href={item.article.url}
                              target='_blank'
                              rel='noopener noreferrer'
                            >
                              <OpenInNewIcon fontSize='small' />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Stack>
                    </Box>

                    {item.article.summary && (
                      <Typography variant='body2' color='text.secondary' sx={{ mb: 1.5 }}>
                        {item.article.summary}
                      </Typography>
                    )}

                    <Stack direction='row' spacing={1} flexWrap='wrap' useFlexGap sx={{ mb: 1 }}>
                      {item.article.source_domain && (
                        <Chip label={item.article.source_domain} size='small' variant='outlined' />
                      )}
                      {item.article.published_at && (
                        <Chip
                          label={new Date(item.article.published_at).toLocaleDateString()}
                          size='small'
                          variant='outlined'
                        />
                      )}
                      <Chip
                        label={`Score ${(item.scores.combined * 100).toFixed(0)}%`}
                        size='small'
                        color={scoreColor(item.scores.combined)}
                      />
                    </Stack>

                    {item.reasoning && (
                      <Typography variant='caption' color='text.secondary' display='block'>
                        {item.reasoning}
                      </Typography>
                    )}

                    {processing.has(item.suggestion_id) && <LinearProgress sx={{ mt: 1 }} />}
                  </Box>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      {total > pageSize && (
        <Stack direction='row' spacing={2} sx={{ mt: 2 }}>
          <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>
            Previous
          </Button>
          <Button
            disabled={offset + pageSize >= total}
            onClick={() => setOffset(offset + pageSize)}
          >
            Next
          </Button>
        </Stack>
      )}

      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} maxWidth='xs' fullWidth>
        <DialogTitle>Reject suggestion{rejectBulk ? 's' : ''}</DialogTitle>
        <DialogContent>
          <FormControl fullWidth size='small' sx={{ mt: 1, mb: 2 }}>
            <InputLabel>Reason</InputLabel>
            <Select
              value={rejectReason}
              label='Reason'
              onChange={e => setRejectReason(e.target.value)}
            >
              {REJECT_REASONS.map(r => (
                <MenuItem key={r.code} value={r.code}>
                  {r.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            size='small'
            label='Notes (optional)'
            value={rejectNotes}
            onChange={e => setRejectNotes(e.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
          <Button color='error' variant='contained' onClick={confirmReject}>
            Reject
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StorylineReviewQueue;
