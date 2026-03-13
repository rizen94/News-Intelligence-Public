/**
 * Investigate — Tracked events, entity profiles, context search.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardContent,
  CardActionArea,
  Typography,
  Box,
  Button,
  Skeleton,
  Chip,
  Divider,
} from '@mui/material';
import { contextCentricApi, type TrackedEvent } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

const EVENT_TYPE_COLORS: Record<string, 'error' | 'warning' | 'info' | 'success' | 'default'> = {
  conflict: 'error',
  disaster: 'error',
  economic: 'warning',
  election: 'info',
  legislation: 'info',
  diplomatic: 'success',
  investigation: 'default',
  policy: 'default',
};

export default function InvestigatePage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [events, setEvents] = useState<TrackedEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const res = await contextCentricApi.getTrackedEvents({ domain_key: domain, limit: 50 }).catch(() => ({ items: [] as TrackedEvent[] }));
        if (!cancelled) setEvents(res?.items ?? []);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [domain]);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Investigate
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" onClick={() => navigate(`/${domain}/investigate/entities`)}>
            Entities
          </Button>
          <Button variant="outlined" size="small" onClick={() => navigate(`/${domain}/investigate/search`)}>
            Search
          </Button>
        </Box>
      </Box>

      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
        Tracked events
      </Typography>

      {loading ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[0, 1, 2].map((i) => <Skeleton key={i} variant="rectangular" height={80} sx={{ borderRadius: 1 }} />)}
        </Box>
      ) : events.length === 0 ? (
        <Card variant="outlined"><CardContent><Typography color="text.secondary">No tracked events yet.</Typography></CardContent></Card>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {events.map((e) => (
            <Card key={e.id} variant="outlined">
              <CardActionArea onClick={() => navigate(`/${domain}/investigate/events/${e.id}`)}>
                <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                        {e.event_name || `Event #${e.id}`}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
                        <Chip
                          label={e.event_type}
                          size="small"
                          color={EVENT_TYPE_COLORS[e.event_type ?? ''] ?? 'default'}
                          variant="outlined"
                        />
                        {e.geographic_scope && (
                          <Typography variant="caption" color="text.secondary">{e.geographic_scope}</Typography>
                        )}
                        {e.start_date && (
                          <Typography variant="caption" color="text.disabled">
                            Since {new Date(e.start_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );
}
