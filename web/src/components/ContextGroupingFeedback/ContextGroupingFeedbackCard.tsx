/**
 * Human audit: does this context belong with a topic/storyline/pattern grouping?
 * Persists to intelligence.context_grouping_feedback (migration 174).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Divider,
  TextField,
  Button,
  MenuItem,
  Box,
  Typography,
  Alert,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
} from '@mui/material';
import {
  contextCentricApi,
  type ContextGroupingFeedbackItem,
} from '@/services/api/contextCentric';

const GROUPING_TYPES = ['topic', 'storyline', 'pattern', 'other'] as const;
const JUDGMENTS = [
  { value: 'belongs', label: 'Belongs with this grouping' },
  { value: 'does_not_belong', label: 'Does not belong (false association)' },
  { value: 'unsure', label: 'Unsure' },
] as const;

interface Props {
  contextId: number;
}

export default function ContextGroupingFeedbackCard({ contextId }: Props) {
  const [groupingType, setGroupingType] =
    useState<(typeof GROUPING_TYPES)[number]>('topic');
  const [groupingId, setGroupingId] = useState('');
  const [groupingLabel, setGroupingLabel] = useState('');
  const [judgment, setJudgment] =
    useState<(typeof JUDGMENTS)[number]['value']>('belongs');
  const [notes, setNotes] = useState('');
  const [judgedBy, setJudgedBy] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [history, setHistory] = useState<ContextGroupingFeedbackItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await contextCentricApi.getContextGroupingFeedback(
        contextId,
        30
      );
      if (res?.success && res.data?.items) setHistory(res.data.items);
      else setHistory([]);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [contextId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSubmit = async () => {
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      let gid: number | undefined;
      if (groupingId.trim()) {
        const n = parseInt(groupingId.trim(), 10);
        if (Number.isNaN(n)) {
          setError('Grouping ID must be a number (or leave empty).');
          setSubmitting(false);
          return;
        }
        gid = n;
      }
      const res = await contextCentricApi.postContextGroupingFeedback(
        contextId,
        {
          grouping_type: groupingType,
          judgment,
          grouping_id: gid ?? null,
          grouping_label: groupingLabel.trim() || null,
          notes: notes.trim() || null,
          judged_by: judgedBy.trim() || null,
        }
      );
      if (res?.success) {
        setSuccess('Feedback saved. Used for audits and future tuning.');
        setNotes('');
        await loadHistory();
      } else {
        setError(res?.message || 'Save failed');
      }
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ||
        (e as Error)?.message ||
        'Request failed';
      setError(String(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card variant='outlined'>
      <CardHeader
        title='Grouping audit'
        subheader='Record whether this context fits a topic, storyline, or pattern. Requires DB migration 174.'
        titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
      />
      <Divider />
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {error && (
          <Alert severity='error' onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity='success' onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          <TextField
            select
            label='Grouping type'
            size='small'
            value={groupingType}
            onChange={e =>
              setGroupingType(e.target.value as (typeof GROUPING_TYPES)[number])
            }
            sx={{ minWidth: 160 }}
          >
            {GROUPING_TYPES.map(t => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label='Grouping ID (optional)'
            size='small'
            placeholder='e.g. topic id or storyline id'
            value={groupingId}
            onChange={e => setGroupingId(e.target.value)}
            sx={{ width: 200 }}
          />
          <TextField
            label='Grouping label (optional)'
            size='small'
            placeholder='Human-readable name'
            value={groupingLabel}
            onChange={e => setGroupingLabel(e.target.value)}
            sx={{ flex: 1, minWidth: 200 }}
          />
        </Box>
        <TextField
          select
          label='Your judgment'
          size='small'
          value={judgment}
          onChange={e =>
            setJudgment(e.target.value as (typeof JUDGMENTS)[number]['value'])
          }
          fullWidth
        >
          {JUDGMENTS.map(j => (
            <MenuItem key={j.value} value={j.value}>
              {j.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label='Notes (optional)'
          size='small'
          multiline
          minRows={2}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          fullWidth
        />
        <TextField
          label='Your name or initials (optional)'
          size='small'
          value={judgedBy}
          onChange={e => setJudgedBy(e.target.value)}
          sx={{ maxWidth: 280 }}
        />
        <Button
          variant='contained'
          onClick={handleSubmit}
          disabled={submitting}
        >
          {submitting ? <CircularProgress size={22} /> : 'Save judgment'}
        </Button>

        <Typography variant='subtitle2' color='text.secondary' sx={{ mt: 1 }}>
          Recent judgments
        </Typography>
        {historyLoading ? (
          <CircularProgress size={24} />
        ) : history.length === 0 ? (
          <Typography variant='body2' color='text.secondary'>
            No prior feedback for this context.
          </Typography>
        ) : (
          <List dense disablePadding>
            {history.map(h => (
              <ListItem
                key={h.id}
                disableGutters
                sx={{ alignItems: 'flex-start' }}
              >
                <ListItemText
                  primary={`${h.judgment.replace(/_/g, ' ')} · ${
                    h.grouping_type
                  }${h.grouping_id != null ? ` #${h.grouping_id}` : ''}${
                    h.grouping_label ? ` — ${h.grouping_label}` : ''
                  }`}
                  secondary={
                    <>
                      {h.judged_at && new Date(h.judged_at).toLocaleString()}
                      {h.judged_by && ` · ${h.judged_by}`}
                      {h.notes && (
                        <Typography
                          component='span'
                          variant='body2'
                          display='block'
                          sx={{ mt: 0.5 }}
                        >
                          {h.notes}
                        </Typography>
                      )}
                    </>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
