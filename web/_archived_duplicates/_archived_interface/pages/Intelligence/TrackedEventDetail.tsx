/**
 * Tracked Event detail — Phase 4.4 context-centric.
 * Event with chronicles (developments, analysis, predictions).
 */
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Alert,
  Button,
  CircularProgress,
  Chip,
  Divider,
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineDot,
  TimelineConnector,
  TimelineContent,
} from '@mui/material';
import ArrowBack as ArrowBackIcon from '@mui/icons-material/ArrowBack';
import Event as EventIcon from '@mui/icons-material/Event';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { contextCentricApi, type TrackedEvent } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const TrackedEventDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { getDomainPath } = useDomainRoute();
  const [event, setEvent] = useState<TrackedEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const numId = parseInt(id, 10);
    if (Number.isNaN(numId)) {
      setError('Invalid event ID');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    contextCentricApi
      .getTrackedEvent(numId)
      .then(setEvent)
      .catch((e) => {
        Logger.apiError('Tracked event load failed', e as Error);
        setError((e as Error).message ?? 'Failed to load event');
        setEvent(null);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !event) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} component={Link} to={getDomainPath('/intelligence/tracked-events')}>
          Back to Tracked Events
        </Button>
        <Alert severity="error" sx={{ mt: 2 }}>
          {error ?? 'Event not found'}
        </Alert>
      </Box>
    );
  }

  const chronicles = event.chronicles ?? [];

  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} component={Link} to={getDomainPath('/intelligence/tracked-events')}>
        Back to Tracked Events
      </Button>

      <Paper sx={{ mt: 2, p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          <EventIcon color="action" />
          <Typography variant="h4" component="h1">
            {event.event_name ?? `Event #${event.id}`}
          </Typography>
          {event.event_type && <Chip label={event.event_type} size="small" variant="outlined" sx={{ ml: 1 }} />}
          {event.geographic_scope && (
            <Chip label={event.geographic_scope} size="small" variant="outlined" />
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          {event.start_date && (
            <Typography variant="body2" color="text.secondary">
              Start: {new Date(event.start_date).toLocaleDateString()}
            </Typography>
          )}
          {event.end_date && (
            <Typography variant="body2" color="text.secondary">
              End: {new Date(event.end_date).toLocaleDateString()}
            </Typography>
          )}
        </Box>

        {event.key_participant_entity_ids && event.key_participant_entity_ids.length > 0 && (
          <Typography variant="body2" color="text.secondary">
            Key participants (entity profile IDs): {event.key_participant_entity_ids.join(', ')}
          </Typography>
        )}

        {chronicles.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="h6" gutterBottom>
              Chronicles
            </Typography>
            <Timeline position="right">
              {chronicles.map((c, i) => (
                <TimelineItem key={c.id}>
                  <TimelineSeparator>
                    <TimelineDot />
                    {i < chronicles.length - 1 && <TimelineConnector />}
                  </TimelineSeparator>
                  <TimelineContent>
                    <Typography variant="caption" color="text.secondary">
                      {c.update_date ? new Date(c.update_date).toLocaleDateString() : '—'}
                      {c.momentum_score != null && ` · Momentum: ${c.momentum_score}`}
                    </Typography>
                    {c.developments && (
                      <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {c.developments}
                      </Typography>
                    )}
                    {c.analysis && (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        {c.analysis}
                      </Typography>
                    )}
                    {c.predictions && (
                      <Typography variant="body2" color="primary.main" sx={{ mt: 0.5 }}>
                        {c.predictions}
                      </Typography>
                    )}
                  </TimelineContent>
                </TimelineItem>
              ))}
            </Timeline>
          </>
        )}

        {chronicles.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No chronicles yet. Event chronicles are updated by the event_tracking task.
          </Typography>
        )}
      </Paper>
    </Box>
  );
};

export default TrackedEventDetail;
