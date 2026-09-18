/**
 * Following — quiet and living follows with movement since last read.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { PageShell, LoadingState } from '@/components/ui';
import { followsApi } from '@/services/api/follows';
import { usePublicDemoMode } from '@/contexts/PublicDemoContext';
import { formatDomainLabel } from '@/utils/domainHelper';
import type { FollowItem, FollowMovementItem } from '@/types/follows';

function objectHref(f: FollowItem): string {
  const dk = f.domain_key || 'politics';
  if (f.object_kind === 'container') return `/${dk}/investigate?container=${f.object_id}`;
  if (f.object_kind === 'package') return `/${dk}/editor/packages/${f.object_id}`;
  const meta = f.metadata || {};
  const profileId = meta.knowledge_profile_id as number | undefined;
  if (f.tier === 'living' && profileId) {
    return `/${dk}/research/profiles/${profileId}`;
  }
  const storyId = meta.story_id as number | undefined;
  if (f.tier === 'living' && storyId) return `/${dk}/editor/stories/${storyId}`;
  return `/${dk}/storylines/${f.object_id}`;
}

export default function FollowingPage() {
  const { domain } = useParams<{ domain?: string }>();
  const { readonly: demoReadonly } = usePublicDemoMode();
  const [movement, setMovement] = useState<FollowMovementItem[]>([]);
  const [all, setAll] = useState<FollowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [movRes, listRes] = await Promise.all([
        followsApi.movement(),
        followsApi.list(),
      ]);
      if (movRes.success) setMovement(movRes.data || []);
      if (listRes.success) setAll(listRes.data || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (demoReadonly) {
      setLoading(false);
      return;
    }
    load();
  }, [load, demoReadonly]);

  const handleMarkRead = async (id: number) => {
    await followsApi.markRead(id);
    await load();
  };

  const handleUnfollow = async (id: number) => {
    await followsApi.unfollow(id);
    await load();
  };

  const handleDemote = async (id: number) => {
    await followsApi.patch(id, { demote_quiet: true });
    await load();
  };

  const handlePromote = async (id: number) => {
    setError(null);
    setNotice(null);
    try {
      const res = await followsApi.patch(id, { promote_living: true });
      const data = res.data as Record<string, unknown> | undefined;
      const meta = (data?.metadata || {}) as Record<string, unknown>;
      const pub = data?.publish as Record<string, unknown> | undefined;
      const pubErr =
        (meta.living_publish_error as string | undefined) ||
        (pub?.block_reason as string | undefined) ||
        (pub?.reason as string | undefined);
      if (pubErr) {
        setNotice(`Promoted to living; publish blocked (${pubErr}). Open the package in Editor to finish.`);
      } else {
        setNotice('Promoted to living story.');
      }
      await load();
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: string } } };
      setError(ax.response?.data?.detail || (e as Error).message);
    }
  };

  const handleResume = async (id: number) => {
    await followsApi.patch(id, { status: 'active' });
    await load();
  };

  const handlePause = async (id: number) => {
    await followsApi.patch(id, { status: 'paused' });
    await load();
  };

  if (demoReadonly) {
    return (
      <PageShell title='Following'>
        <Alert severity='info'>Following is unavailable in read-only demo mode.</Alert>
      </PageShell>
    );
  }

  const quiet = all.filter(f => f.tier === 'quiet' && f.status === 'active');
  const living = all.filter(f => f.tier === 'living' && f.status === 'active');
  const paused = all.filter(f => f.status === 'paused');

  const renderRow = (f: FollowItem | FollowMovementItem, showMovement = false) => {
    const title =
      'title' in f && f.title
        ? String(f.title)
        : `${f.object_kind} ${f.domain_key}/${f.object_id}`;
    const republishLog = (f.metadata?.republish_log as unknown[]) || [];
    const publishErr = f.metadata?.living_publish_error as string | undefined;
    return (
      <ListItem
        key={f.id}
        secondaryAction={
          <Stack direction='row' spacing={0.5}>
            {showMovement && (
              <Button size='small' onClick={() => handleMarkRead(f.id)}>
                Mark read
              </Button>
            )}
            {f.tier === 'living' && (
              <Button size='small' onClick={() => handleDemote(f.id)}>
                Demote
              </Button>
            )}
            {f.tier === 'quiet' && f.object_kind === 'episode' && f.status === 'active' && (
              <Button size='small' onClick={() => handlePromote(f.id)}>
                Living
              </Button>
            )}
            {f.status === 'active' && f.tier === 'quiet' && (
              <Button size='small' onClick={() => handlePause(f.id)}>
                Pause
              </Button>
            )}
            {f.status === 'paused' && (
              <Button size='small' onClick={() => handleResume(f.id)}>
                Resume
              </Button>
            )}
            <IconButton edge='end' aria-label='Unfollow' onClick={() => handleUnfollow(f.id)}>
              <CloseIcon fontSize='small' />
            </IconButton>
          </Stack>
        }
        sx={{ alignItems: 'flex-start' }}
      >
        <ListItemText
          primary={
            <Stack direction='row' spacing={1} alignItems='center' flexWrap='wrap'>
              <Button component={RouterLink} to={objectHref(f)} size='small' sx={{ p: 0, minWidth: 0 }}>
                {title}
              </Button>
              <Chip size='small' label={f.tier} color={f.tier === 'living' ? 'primary' : 'default'} />
              {f.domain_key && (
                <Chip size='small' variant='outlined' label={formatDomainLabel(f.domain_key)} />
              )}
            </Stack>
          }
          secondary={
            <Box component='span' sx={{ display: 'block', mt: 0.5 }}>
              {showMovement && 'velocity' in f && (
                <Typography variant='caption' display='block'>
                  +{f.velocity} events · score {(f as FollowMovementItem).score?.toFixed(1)}
                </Typography>
              )}
              {publishErr && (
                <Typography variant='caption' color='error' display='block'>
                  Publish blocked: {publishErr}
                </Typography>
              )}
              {republishLog.length > 0 && (
                <Typography variant='caption' color='text.secondary' display='block'>
                  {republishLog.length} republish(es) — latest{' '}
                  {String((republishLog[republishLog.length - 1] as { at?: string })?.at || '')}
                </Typography>
              )}
              {f.last_surfaced_at && (
                <Typography variant='caption' color='text.secondary' display='block'>
                  Last surfaced {new Date(f.last_surfaced_at).toLocaleString()}
                </Typography>
              )}
            </Box>
          }
        />
      </ListItem>
    );
  };

  return (
    <PageShell
      title='Following'
      subtitle='Quiet track and living stories'
      actions={
        <Button
          size='small'
          component={RouterLink}
          to={`/${domain || 'politics'}/pulse`}
        >
          Back to Pulse
        </Button>
      }
    >
      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {notice && (
        <Alert severity='warning' sx={{ mb: 2 }} onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {loading ? (
        <LoadingState message='Loading follows…' />
      ) : (
        <>
          <Typography variant='h6' fontWeight={700} sx={{ mb: 1 }}>
            Since you were here
          </Typography>
          {movement.length === 0 ? (
            <Typography variant='body2' color='text.secondary' sx={{ mb: 3 }}>
              No movement on followed items in the current window.
            </Typography>
          ) : (
            <List dense sx={{ mb: 3 }}>
              {movement.map(f => renderRow(f, true))}
            </List>
          )}

          <Typography variant='h6' fontWeight={700} sx={{ mb: 1 }}>
            Living ({living.length})
          </Typography>
          <List dense sx={{ mb: 3 }}>
            {living.length === 0 ? (
              <Typography variant='body2' color='text.secondary' sx={{ px: 2 }}>
                No living follows yet — promote from Pulse.
              </Typography>
            ) : (
              living.map(f => renderRow(f))
            )}
          </List>

          <Typography variant='h6' fontWeight={700} sx={{ mb: 1 }}>
            Quiet ({quiet.length})
          </Typography>
          <List dense sx={{ mb: 3 }}>
            {quiet.map(f => renderRow(f))}
          </List>

          {paused.length > 0 && (
            <>
              <Typography variant='h6' fontWeight={700} sx={{ mb: 1 }}>
                Paused (cooling)
              </Typography>
              <List dense>{paused.map(f => renderRow(f))}</List>
            </>
          )}
        </>
      )}
    </PageShell>
  );
}
