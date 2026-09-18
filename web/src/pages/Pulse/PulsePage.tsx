/**
 * Pulse — ranked episode/container movement digest.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import { PageShell, LoadingState } from '@/components/ui';
import { pulseApi } from '@/services/api/pulse';
import { followsApi } from '@/services/api/follows';
import { usePublicDemoMode } from '@/contexts/PublicDemoContext';
import { formatDomainLabel, getDefaultDomainKey } from '@/utils/domainHelper';
import { statusLabel } from '@/utils/statusLabel';
import type { PulseCard } from '@/types/pulse';
import type { FollowItem } from '@/types/follows';

const WINDOW_OPTIONS = [
  { label: '24h', hours: 24 },
  { label: '48h', hours: 48 },
  { label: '7d', hours: 168 },
];

function kindLabel(storyKind?: string | null): string {
  const k = (storyKind || '').toLowerCase();
  if (k === 'event_narrative') return 'Arc';
  if (k === 'matter_docket') return 'Docket';
  if (k === 'evidence_thread') return 'Evidence thread';
  if (k === 'research_topic') return 'Research';
  if (k === 'market_regulatory_arc') return 'Market arc';
  if (k === 'container_index') return 'Container index';
  return storyKind || 'Episode';
}

function stateColor(state?: string | null): 'default' | 'primary' | 'warning' | 'success' {
  const s = (state || '').toLowerCase();
  if (s === 'active') return 'primary';
  if (s === 'cooling' || s === 'dormant') return 'warning';
  if (s === 'reactivated') return 'success';
  return 'default';
}

function cardHref(card: PulseCard): string {
  const dk = card.domain_key || getDefaultDomainKey();
  const id = card.id;
  const kind = (card.story_kind || '').toLowerCase();
  if (card.object_kind === 'container') {
    return `/${dk}/investigate?container=${id}`;
  }
  if (kind === 'matter_docket') return `/${dk}/dockets/${id}`;
  // Research / evidence ledgers — not curated arc catalog keys.
  if (kind === 'evidence_thread' || kind === 'research_topic') {
    return `/${dk}/research/subjects`;
  }
  // Narrative episode ids are storyline rows — never /arcs/:id/chronicle.
  return `/${dk}/storylines/${id}`;
}

function movementText(card: PulseCard): string {
  const moves = card.movement_summary || [];
  if (card.movement_stub) return card.movement_stub;
  if (!moves.length) return 'Recent container activity';
  return moves
    .slice(0, 2)
    .map(m => m.title)
    .filter(Boolean)
    .join(' · ');
}

export default function PulsePage() {
  const { domain } = useParams<{ domain?: string }>();
  const navigate = useNavigate();
  const { readonly: demoReadonly } = usePublicDemoMode();
  const [windowHours, setWindowHours] = useState(48);
  const [domainFilter, setDomainFilter] = useState<string | undefined>(domain);
  const [items, setItems] = useState<PulseCard[]>([]);
  const [follows, setFollows] = useState<FollowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [followError, setFollowError] = useState<string | null>(null);
  const [followNotice, setFollowNotice] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<{ el: HTMLElement; card: PulseCard } | null>(null);

  const followKey = useCallback(
    (card: PulseCard) =>
      `${card.object_kind}:${card.domain_key}:${card.id}`,
    []
  );

  const followMap = useMemo(() => {
    const m = new Map<string, FollowItem>();
    for (const f of follows) {
      m.set(`${f.object_kind}:${f.domain_key}:${f.object_id}`, f);
    }
    return m;
  }, [follows]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pulseRes, followRes] = await Promise.all([
        pulseApi.getPulse({
          window_hours: windowHours,
          limit: 30,
          domain: domainFilter,
        }),
        demoReadonly ? Promise.resolve(null) : followsApi.list(),
      ]);
      if (!pulseRes?.success || !pulseRes.data) {
        setError(pulseRes?.message || 'Failed to load pulse');
        setItems([]);
      } else {
        setItems(pulseRes.data.items || []);
      }
      if (followRes?.success) {
        setFollows(followRes.data || []);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [windowHours, domainFilter, demoReadonly]);

  useEffect(() => {
    setDomainFilter(domain);
  }, [domain]);

  useEffect(() => {
    load();
  }, [load]);

  const handleFollow = async (card: PulseCard, tier: 'quiet' | 'living') => {
    setFollowError(null);
    setFollowNotice(null);
    setMenuAnchor(null);
    try {
      const res = await followsApi.follow({
        object_kind: card.object_kind === 'container' ? 'container' : 'episode',
        domain_key: card.domain_key,
        object_id: card.id,
        tier,
      });
      if (!res.success) {
        setFollowError('Follow failed');
        return;
      }
      const meta = (res.data?.metadata || {}) as Record<string, unknown>;
      const pubErr = meta.living_publish_error as string | undefined;
      if (tier === 'living' && pubErr) {
        setFollowNotice(
          `Living follow saved, but auto-publish was blocked (${pubErr}). Check Following for the draft package.`
        );
      } else if (tier === 'living') {
        setFollowNotice('Living story follow created.');
      }
      await load();
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: string | { msg?: string }[] } } };
      const detail = ax.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map(d => d?.msg).filter(Boolean).join('; ')
            : (e as Error).message;
      setFollowError(msg || 'Follow failed');
    }
  };

  return (
    <PageShell title='Pulse' subtitle='Ranked episode and container movement'>
      <Stack direction='row' spacing={1} sx={{ mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <ToggleButtonGroup
          size='small'
          exclusive
          value={windowHours}
          onChange={(_, v) => v && setWindowHours(v)}
        >
          {WINDOW_OPTIONS.map(o => (
            <ToggleButton key={o.hours} value={o.hours}>
              {o.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <Button
          size='small'
          variant={domainFilter ? 'outlined' : 'contained'}
          onClick={() => setDomainFilter(undefined)}
        >
          All domains
        </Button>
        {domain && (
          <Chip
            label={formatDomainLabel(domain)}
            color={domainFilter === domain ? 'primary' : 'default'}
            onClick={() => setDomainFilter(domain)}
            variant={domainFilter === domain ? 'filled' : 'outlined'}
          />
        )}
        {!demoReadonly && (
          <Button
            size='small'
            component={RouterLink}
            to={`/${domain || getDefaultDomainKey()}/following`}
          >
            Following
          </Button>
        )}
      </Stack>

      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {followError && (
        <Alert severity='error' sx={{ mb: 2 }} onClose={() => setFollowError(null)}>
          {followError}
        </Alert>
      )}
      {followNotice && (
        <Alert severity='warning' sx={{ mb: 2 }} onClose={() => setFollowNotice(null)}>
          {followNotice}
        </Alert>
      )}

      {loading ? (
        <LoadingState message='Loading pulse…' />
      ) : items.length === 0 ? (
        <Typography color='text.secondary'>No movement in this window.</Typography>
      ) : (
        <Stack spacing={1.5}>
          {items.map(card => {
            const fk = followKey(card);
            const existing = followMap.get(fk);
            const isContainer = card.object_kind === 'container';
            return (
              <Card
                key={fk}
                variant='outlined'
                sx={isContainer ? { borderStyle: 'dashed', opacity: 0.95 } : undefined}
              >
                <CardActionArea onClick={() => navigate(cardHref(card))}>
                  <CardContent>
                    <Stack direction='row' spacing={1} alignItems='flex-start'>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant='subtitle1' fontWeight={700} noWrap>
                          {card.title}
                        </Typography>
                        <Stack direction='row' spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap' }}>
                          <Chip size='small' label={formatDomainLabel(card.domain_key)} />
                          <Chip size='small' label={kindLabel(card.story_kind)} variant='outlined' />
                          {card.episode_state && (
                            <Chip
                              size='small'
                              color={stateColor(card.episode_state)}
                              label={statusLabel(card.episode_state)}
                            />
                          )}
                          <Chip
                            size='small'
                            color='info'
                            label={`+${card.velocity} events / ${windowHours}h`}
                          />
                        </Stack>
                        <Typography variant='body2' color='text.secondary' sx={{ mt: 1 }}>
                          {movementText(card)}
                        </Typography>
                        {card.published_story_id && (
                          <Button
                            size='small'
                            sx={{ mt: 1 }}
                            component={RouterLink}
                            to={`/${card.domain_key}/editor/stories/${card.published_story_id}`}
                            onClick={e => e.stopPropagation()}
                          >
                            Full story ↗
                          </Button>
                        )}
                      </Box>
                      {!demoReadonly && (
                        <IconButton
                          aria-label='Follow'
                          onClick={e => {
                            e.stopPropagation();
                            if (existing) {
                              navigate(`/${card.domain_key || getDefaultDomainKey()}/following`);
                            } else {
                              setMenuAnchor({ el: e.currentTarget, card });
                            }
                          }}
                        >
                          {existing ? <BookmarkIcon color='primary' /> : <BookmarkBorderIcon />}
                        </IconButton>
                      )}
                    </Stack>
                  </CardContent>
                </CardActionArea>
              </Card>
            );
          })}
        </Stack>
      )}

      <Menu
        anchorEl={menuAnchor?.el}
        open={Boolean(menuAnchor)}
        onClose={() => setMenuAnchor(null)}
      >
        <MenuItem onClick={() => menuAnchor && handleFollow(menuAnchor.card, 'quiet')}>
          Follow (quiet)
        </MenuItem>
        <MenuItem
          disabled={menuAnchor?.card.object_kind === 'container'}
          onClick={() => menuAnchor && handleFollow(menuAnchor.card, 'living')}
        >
          Follow with story (living)
        </MenuItem>
      </Menu>
    </PageShell>
  );
}
