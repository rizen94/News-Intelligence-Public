/**
 * Storyline reliability audit: linked articles vs chronological_events, ML/doc touch times.
 */
import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  Divider,
  Typography,
  Box,
  Button,
  Chip,
  Alert,
} from '@mui/material';
import OpenInNew from '@mui/icons-material/OpenInNew';

export interface StorylineAuditData {
  storyline_id?: number;
  title?: string;
  storyline_article_count_column?: number;
  storyline_articles_linked?: number;
  timeline_event_count?: number;
  merged_duplicate_events_count?: number;
  timeline_status?: string;
  updated_at?: string | null;
  last_refinement?: string | null;
  document_version?: number | null;
  ml_processing_status?: string | null;
  context_last_updated?: string | null;
}

interface Props {
  domain: string;
  audit: StorylineAuditData | null;
  error?: string | null;
  loading?: boolean;
}

export default function StorylineAuditCard({
  domain,
  audit,
  error,
  loading,
}: Props) {
  if (loading) {
    return (
      <Card variant='outlined' sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant='body2' color='text.secondary'>
            Loading storyline audit…
          </Typography>
        </CardContent>
      </Card>
    );
  }
  if (error) {
    return (
      <Alert severity='warning' sx={{ mb: 2 }}>
        Audit unavailable: {error}
      </Alert>
    );
  }
  if (!audit) return null;

  const linked = audit.storyline_articles_linked ?? 0;
  const evCount = audit.timeline_event_count ?? 0;
  const merged = audit.merged_duplicate_events_count ?? 0;
  const empty = audit.timeline_status === 'empty' || evCount === 0;

  return (
    <Card variant='outlined' sx={{ mb: 2 }}>
      <CardHeader
        title='Storyline & timeline audit'
        subheader='Compare linked articles to public.chronological_events'
        titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
      />
      <Divider />
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 1,
            alignItems: 'center',
          }}
        >
          <Chip
            label={empty ? 'Timeline empty' : `${evCount} timeline events`}
            color={empty ? 'warning' : 'success'}
            size='small'
            variant={empty ? 'filled' : 'outlined'}
          />
          <Chip
            label={`${linked} articles linked`}
            size='small'
            variant='outlined'
          />
          {merged > 0 && (
            <Chip
              label={`${merged} merged duplicate event rows (hidden from primary timeline)`}
              size='small'
              color='info'
              variant='outlined'
            />
          )}
        </Box>
        <Typography variant='body2' color='text.secondary'>
          Storyline <code>article_count</code> column:{' '}
          {audit.storyline_article_count_column ?? '—'} · Linked rows in{' '}
          <code>storyline_articles</code>: {linked}
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          <Typography variant='caption' color='text.secondary'>
            Updated: {audit.updated_at ?? '—'}
          </Typography>
          <Typography variant='caption' color='text.secondary'>
            Last refinement: {audit.last_refinement ?? '—'}
          </Typography>
          <Typography variant='caption' color='text.secondary'>
            Document version: {audit.document_version ?? '—'}
          </Typography>
          <Typography variant='caption' color='text.secondary'>
            ML status: {audit.ml_processing_status ?? '—'}
          </Typography>
          <Typography variant='caption' color='text.secondary'>
            Context updated: {audit.context_last_updated ?? '—'}
          </Typography>
        </Box>
        <Button
          component={RouterLink}
          to={`/${domain}/storylines/${audit.storyline_id}/timeline`}
          variant='outlined'
          size='small'
          endIcon={<OpenInNew sx={{ fontSize: 16 }} />}
          sx={{ alignSelf: 'flex-start' }}
        >
          Open interactive timeline
        </Button>
      </CardContent>
    </Card>
  );
}
