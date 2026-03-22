import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import {
  Box,
  Typography,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  Button,
  Card,
  CardContent,
  Collapse,
  Divider,
  IconButton,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
  LinearProgress,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ArticleIcon from '@mui/icons-material/Article';
import GavelIcon from '@mui/icons-material/Gavel';
import PublicIcon from '@mui/icons-material/Public';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import WarningIcon from '@mui/icons-material/Warning';
import AutoStoriesIcon from '@mui/icons-material/AutoStories';
import apiService from '../../services/apiService';

interface TimelineEvent {
  id: number;
  title: string;
  description: string;
  event_type: string;
  event_date: string | null;
  date_precision: string;
  location: string;
  key_actors: Array<{ name: string; role: string }>;
  importance: number;
  source_count: number;
  is_ongoing: boolean;
  outcome: string;
  source?: {
    article_title: string;
    domain: string;
    published_at: string | null;
  };
}

interface TimelineGap {
  after_event_id: number;
  before_event_id: number;
  gap_days: number;
  from_date: string;
  to_date: string;
}

interface Milestone {
  type: string;
  event_id: number;
  label: string;
}

interface TimelineData {
  storyline_id: number;
  events: TimelineEvent[];
  gaps: TimelineGap[];
  milestones: Milestone[];
  event_count: number;
  time_span: { start: string; end: string; days: number } | null;
  source_count: number;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  court_ruling: '#e53935',
  legal_action: '#d32f2f',
  arrest: '#c62828',
  investigation: '#ff6f00',
  policy_decision: '#1565c0',
  legislation: '#0d47a1',
  election: '#6a1b9a',
  conflict: '#bf360c',
  protest: '#e65100',
  agreement: '#2e7d32',
  economic_event: '#00695c',
  public_statement: '#37474f',
  appointment: '#4527a0',
  resignation: '#880e4f',
  natural_disaster: '#ff5722',
  scientific_discovery: '#00838f',
  meeting: '#455a64',
  report_release: '#546e7a',
  death: '#212121',
  other: '#757575',
};

const EVENT_TYPE_ICONS: Record<string, React.ReactNode> = {
  court_ruling: <GavelIcon />,
  legal_action: <GavelIcon />,
  conflict: <WarningIcon />,
  policy_decision: <PublicIcon />,
  economic_event: <TrendingUpIcon />,
};

const StoryTimeline: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { domain } = useDomainRoute();
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [narrative, setNarrative] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());
  const [narrativeMode, setNarrativeMode] = useState<'chronological' | 'briefing'>('chronological');

  const loadTimeline = useCallback(async () => {
    if (!id || !domain) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiService.getStorylineTimeline(id, domain);
      if (result?.success) {
        setTimeline(result.data);
      } else {
        setError(result?.error || 'Failed to load timeline');
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [id, domain]);

  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

  const loadNarrative = async () => {
    if (!id || !domain) return;
    setNarrativeLoading(true);
    try {
      const result = await apiService.getStorylineNarrative(id, narrativeMode, domain);
      if (result?.success) {
        setNarrative(result.data.narrative || result.data.briefing || '');
      }
    } catch {
      setNarrative('Failed to generate narrative.');
    } finally {
      setNarrativeLoading(false);
    }
  };

  const toggleEvent = (eventId: number) => {
    setExpandedEvents(prev => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  };

  const milestoneSet = new Set(timeline?.milestones?.map(m => m.event_id) || []);
  const gapAfterEvent = new Map(
    (timeline?.gaps || []).map(g => [g.after_event_id, g])
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !timeline) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error || 'No timeline data available'}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', p: 3 }}>
      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Story Timeline
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <Chip label={`${timeline.event_count} events`} color="primary" />
          <Chip label={`${timeline.source_count} sources`} color="secondary" />
          {timeline.time_span && (
            <Chip
              label={`${timeline.time_span.days} days (${timeline.time_span.start} — ${timeline.time_span.end})`}
              variant="outlined"
            />
          )}
        </Box>

        {/* Milestone summary */}
        {timeline.milestones.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Key Milestones
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {timeline.milestones.map((m, i) => (
                <Chip
                  key={i}
                  label={m.label}
                  size="small"
                  variant="outlined"
                  color={m.type === 'resolution' ? 'success' : m.type === 'escalation' ? 'warning' : 'info'}
                />
              ))}
            </Box>
          </Box>
        )}
      </Paper>

      {/* Narrative section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <AutoStoriesIcon />
          <Typography variant="h6">Narrative</Typography>
          <ToggleButtonGroup
            value={narrativeMode}
            exclusive
            onChange={(_, v) => v && setNarrativeMode(v)}
            size="small"
          >
            <ToggleButton value="chronological">Full</ToggleButton>
            <ToggleButton value="briefing">Briefing</ToggleButton>
          </ToggleButtonGroup>
          <Button
            variant="contained"
            size="small"
            onClick={loadNarrative}
            disabled={narrativeLoading}
          >
            {narrativeLoading ? 'Generating...' : 'Generate'}
          </Button>
        </Box>
        {narrativeLoading && <LinearProgress sx={{ mb: 2 }} />}
        {narrative && (
          <Typography
            variant="body1"
            sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}
          >
            {narrative}
          </Typography>
        )}
      </Paper>

      {/* Timeline */}
      <Timeline position="right">
        {timeline.events.map((evt) => {
          const isMilestone = milestoneSet.has(evt.id);
          const gap = gapAfterEvent.get(evt.id);
          const color = EVENT_TYPE_COLORS[evt.event_type] || '#757575';
          const expanded = expandedEvents.has(evt.id);

          return (
            <React.Fragment key={evt.id}>
              <TimelineItem>
                <TimelineOppositeContent sx={{ flex: 0.25, pt: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    {evt.event_date || 'Date unknown'}
                  </Typography>
                  {evt.date_precision !== 'exact' && evt.date_precision !== 'unknown' && (
                    <Typography variant="caption" color="text.disabled">
                      ~{evt.date_precision}
                    </Typography>
                  )}
                </TimelineOppositeContent>

                <TimelineSeparator>
                  <TimelineDot
                    sx={{
                      bgcolor: color,
                      width: isMilestone ? 20 : 14,
                      height: isMilestone ? 20 : 14,
                      boxShadow: isMilestone ? `0 0 8px ${color}` : 'none',
                    }}
                  >
                    {EVENT_TYPE_ICONS[evt.event_type] || <ArticleIcon sx={{ fontSize: 12 }} />}
                  </TimelineDot>
                  <TimelineConnector />
                </TimelineSeparator>

                <TimelineContent sx={{ pb: 3 }}>
                  <Card
                    variant="outlined"
                    sx={{
                      borderLeft: `4px solid ${color}`,
                      ...(isMilestone && { boxShadow: 2 }),
                    }}
                  >
                    <CardContent sx={{ pb: '8px !important' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="subtitle1" fontWeight={isMilestone ? 700 : 500}>
                            {evt.title}
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                            <Chip label={evt.event_type.replace('_', ' ')} size="small" sx={{ bgcolor: color, color: '#fff', fontSize: '0.7rem' }} />
                            {evt.is_ongoing && <Chip label="ongoing" size="small" color="warning" variant="outlined" />}
                            {evt.source_count > 1 && (
                              <Chip label={`${evt.source_count} sources`} size="small" color="info" variant="outlined" />
                            )}
                            {evt.location && evt.location !== 'unknown' && (
                              <Chip label={evt.location} size="small" variant="outlined" />
                            )}
                          </Box>
                        </Box>
                        <IconButton size="small" onClick={() => toggleEvent(evt.id)}>
                          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                        </IconButton>
                      </Box>

                      <Collapse in={expanded}>
                        <Box sx={{ mt: 2 }}>
                          {evt.description && (
                            <Typography variant="body2" sx={{ mb: 1 }}>
                              {evt.description}
                            </Typography>
                          )}
                          {evt.key_actors && evt.key_actors.length > 0 && (
                            <Box sx={{ mb: 1 }}>
                              <Typography variant="caption" color="text.secondary">Key Actors:</Typography>
                              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                                {evt.key_actors.map((a, i) => (
                                  <Chip key={i} label={`${a.name}${a.role ? ` (${a.role})` : ''}`} size="small" variant="outlined" />
                                ))}
                              </Box>
                            </Box>
                          )}
                          {evt.source && (
                            <>
                              <Divider sx={{ my: 1 }} />
                              <Typography variant="caption" color="text.secondary">
                                Source: {evt.source.domain} — {evt.source.article_title}
                                {evt.source.published_at && ` (${new Date(evt.source.published_at).toLocaleDateString()})`}
                              </Typography>
                            </>
                          )}
                        </Box>
                      </Collapse>
                    </CardContent>
                  </Card>
                </TimelineContent>
              </TimelineItem>

              {/* Gap indicator */}
              {gap && (
                <TimelineItem>
                  <TimelineOppositeContent sx={{ flex: 0.25 }} />
                  <TimelineSeparator>
                    <TimelineDot sx={{ bgcolor: 'transparent', border: '2px dashed #bbb', boxShadow: 'none' }} />
                    <TimelineConnector sx={{ borderStyle: 'dashed' }} />
                  </TimelineSeparator>
                  <TimelineContent>
                    <Tooltip title={`${gap.from_date} to ${gap.to_date}`}>
                      <Chip
                        label={`${gap.gap_days}-day gap`}
                        size="small"
                        variant="outlined"
                        color="default"
                        sx={{ fontStyle: 'italic' }}
                      />
                    </Tooltip>
                  </TimelineContent>
                </TimelineItem>
              )}
            </React.Fragment>
          );
        })}
      </Timeline>
    </Box>
  );
};

export default StoryTimeline;
