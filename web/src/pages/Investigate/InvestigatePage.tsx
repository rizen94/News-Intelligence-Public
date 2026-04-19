/**
 * Investigate — Tracked events, entity profiles, context search.
 * Phase 1: Create / edit tracked events (v6 quality-first).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  Skeleton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import Add from '@mui/icons-material/Add';
import {
  contextCentricApi,
  type TrackedEvent,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import ThreadCard from '@/components/Thread/ThreadCard';

const EVENT_TYPES = [
  'election',
  'legislation',
  'investigation',
  'policy',
  'economic',
  'diplomatic',
  'conflict',
  'disaster',
  'market_event',
];

const emptyForm = {
  event_type: 'election',
  event_name: '',
  start_date: '',
  end_date: '',
  geographic_scope: '',
  domain_keys: [] as string[],
};

export default function InvestigatePage() {
  const { domain, availableDomains } = useDomain();
  const navigate = useNavigate();
  const [events, setEvents] = useState<TrackedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(emptyForm);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await contextCentricApi
        .getTrackedEvents({ domain_key: domain, limit: 50 })
        .catch(() => ({ items: [] as TrackedEvent[] }));
      setEvents(res?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, [domain]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const handleCreateOpen = () => {
    setCreateForm({ ...emptyForm, domain_keys: [domain].filter(Boolean) });
    setCreateError(null);
    setCreateOpen(true);
  };

  const handleCreateSubmit = async () => {
    if (!createForm.event_name.trim()) {
      setCreateError('Event name is required');
      return;
    }
    setCreateSubmitting(true);
    setCreateError(null);
    try {
      const created = await contextCentricApi.createTrackedEvent({
        event_type: createForm.event_type,
        event_name: createForm.event_name.trim(),
        start_date: createForm.start_date || undefined,
        end_date: createForm.end_date || undefined,
        geographic_scope: createForm.geographic_scope.trim() || undefined,
        domain_keys: createForm.domain_keys.length
          ? createForm.domain_keys
          : undefined,
      });
      setCreateOpen(false);
      setCreateForm(emptyForm);
      await loadEvents();
      if (created?.id) navigate(`/${domain}/investigate/events/${created.id}`);
    } catch (e: unknown) {
      setCreateError((e as Error)?.message ?? 'Failed to create event');
    } finally {
      setCreateSubmitting(false);
    }
  };

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
        }}
      >
        <Typography variant='h5' sx={{ fontWeight: 600 }}>
          Investigate
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant='contained'
            size='small'
            startIcon={<Add />}
            onClick={handleCreateOpen}
          >
            Create event
          </Button>
          <Button
            variant='outlined'
            size='small'
            onClick={() => navigate(`/${domain}/investigate/entities`)}
          >
            Entities
          </Button>
          <Button
            variant='outlined'
            size='small'
            onClick={() => navigate(`/${domain}/investigate/search`)}
          >
            Search
          </Button>
          <Button
            variant='outlined'
            size='small'
            onClick={() => navigate(`/${domain}/investigate/documents`)}
          >
            Documents
          </Button>
          <Button
            variant='outlined'
            size='small'
            onClick={() => navigate(`/${domain}/investigate/narrative-threads`)}
          >
            Narrative threads
          </Button>
        </Box>
      </Box>

      <Dialog
        open={createOpen}
        onClose={() => !createSubmitting && setCreateOpen(false)}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>Create tracked event</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label='Event name'
              value={createForm.event_name}
              onChange={e =>
                setCreateForm(f => ({ ...f, event_name: e.target.value }))
              }
              required
              fullWidth
              size='small'
            />
            <TextField
              select
              SelectProps={{ native: true }}
              label='Event type'
              value={createForm.event_type}
              onChange={e =>
                setCreateForm(f => ({ ...f, event_type: e.target.value }))
              }
              fullWidth
              size='small'
            >
              {EVENT_TYPES.map(t => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </TextField>
            <TextField
              label='Start date'
              type='date'
              value={createForm.start_date}
              onChange={e =>
                setCreateForm(f => ({ ...f, start_date: e.target.value }))
              }
              InputLabelProps={{ shrink: true }}
              fullWidth
              size='small'
            />
            <TextField
              label='End date'
              type='date'
              value={createForm.end_date}
              onChange={e =>
                setCreateForm(f => ({ ...f, end_date: e.target.value }))
              }
              InputLabelProps={{ shrink: true }}
              fullWidth
              size='small'
            />
            <TextField
              label='Geographic scope'
              value={createForm.geographic_scope}
              onChange={e =>
                setCreateForm(f => ({ ...f, geographic_scope: e.target.value }))
              }
              fullWidth
              size='small'
              placeholder='e.g. US, EU'
            />
            <Box>
              <Typography
                variant='caption'
                color='text.secondary'
                sx={{ display: 'block', mb: 0.5 }}
              >
                Domains
              </Typography>
              {availableDomains.map(d => (
                <FormControlLabel
                  key={d.key}
                  control={
                    <Checkbox
                      checked={createForm.domain_keys.includes(d.key)}
                      onChange={(_, checked) =>
                        setCreateForm(f => ({
                          ...f,
                          domain_keys: checked
                            ? [...f.domain_keys, d.key]
                            : f.domain_keys.filter(k => k !== d.key),
                        }))
                      }
                    />
                  }
                  label={`${d.name} (${d.key})`}
                />
              ))}
            </Box>
            {createError && (
              <Typography color='error' variant='body2'>
                {createError}
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setCreateOpen(false)}
            disabled={createSubmitting}
          >
            Cancel
          </Button>
          <Button
            variant='contained'
            onClick={handleCreateSubmit}
            disabled={createSubmitting}
          >
            {createSubmitting ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      <Typography variant='body2' color='text.secondary' sx={{ mb: 1.5 }}>
        Narrative threads (Investigate → Narrative threads) are synthesized
        cross-story views; storylines under Stories are article-driven threads.
        Create tracked events here; use Entities and Search for intelligence.
      </Typography>
      <Typography variant='subtitle2' color='text.secondary' sx={{ mb: 1 }}>
        Tracked events
      </Typography>

      {loading ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[0, 1, 2].map(i => (
            <Skeleton
              key={i}
              variant='rectangular'
              height={80}
              sx={{ borderRadius: 1 }}
            />
          ))}
        </Box>
      ) : events.length === 0 ? (
        <Card variant='outlined'>
          <CardContent>
            <Typography color='text.secondary'>
              No tracked events yet.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' },
            gap: 1.5,
          }}
        >
          {events.map(e => (
            <ThreadCard
              key={e.id}
              kind='event'
              title={e.event_name || `Event #${e.id}`}
              subtitle={
                e.start_date
                  ? `Since ${new Date(e.start_date).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                    })}`
                  : undefined
              }
              why={e.geographic_scope ?? undefined}
              chip={e.event_type ?? undefined}
              href={`/${domain}/investigate/events/${e.id}?from=investigate`}
              ctaLabel='Open event'
            />
          ))}
        </Box>
      )}
    </Box>
  );
}
