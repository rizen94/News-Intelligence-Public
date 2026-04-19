/**
 * Unified “thread” card — storyline, watched, tracked event, or context (discover).
 * Used on Dashboard, Briefing, Investigate, Watchlist for consistent navigation.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardActionArea,
  CardContent,
  Typography,
  Box,
  Chip,
} from '@mui/material';
import ChevronRight from '@mui/icons-material/ChevronRight';

export type ThreadKind = 'storyline' | 'watched' | 'event' | 'context';

const KIND_LABEL: Record<ThreadKind, string> = {
  storyline: 'Storyline',
  watched: 'Watched',
  event: 'Event',
  context: 'Context',
};

export interface ThreadCardProps {
  kind: ThreadKind;
  title: string;
  /** Last activity / timestamp label */
  subtitle?: string | null;
  /** One-line “why it matters” */
  why?: string | null;
  href: string;
  ctaLabel?: string;
  badge?: string | null;
  chip?: string | null;
}

export default function ThreadCard({
  kind,
  title,
  subtitle,
  why,
  href,
  ctaLabel = 'Open',
  badge,
  chip,
}: ThreadCardProps) {
  const navigate = useNavigate();

  return (
    <Card variant='outlined' sx={{ height: '100%' }}>
      <CardActionArea
        onClick={() => navigate(href)}
        sx={{ alignItems: 'stretch', height: '100%' }}
      >
        <CardContent
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 0.75,
            '&:last-child': { pb: 2 },
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              flexWrap: 'wrap',
              width: '100%',
            }}
          >
            <Chip size='small' label={KIND_LABEL[kind]} variant='outlined' />
            {chip && (
              <Chip size='small' label={chip} color='primary' variant='outlined' />
            )}
            {badge && (
              <Chip size='small' label={badge} color='secondary' variant='filled' />
            )}
          </Box>
          <Typography variant='subtitle1' sx={{ fontWeight: 600, lineHeight: 1.3 }}>
            {title || '(Untitled)'}
          </Typography>
          {subtitle && (
            <Typography variant='caption' color='text.secondary'>
              {subtitle}
            </Typography>
          )}
          {why && (
            <Typography
              variant='body2'
              color='text.secondary'
              sx={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {why}
            </Typography>
          )}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              mt: 'auto',
              pt: 0.5,
              color: 'primary.main',
            }}
          >
            <Typography variant='body2' component='span' sx={{ fontWeight: 500 }}>
              {ctaLabel}
            </Typography>
            <ChevronRight sx={{ fontSize: 18 }} />
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
