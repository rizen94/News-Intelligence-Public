/**
 * Reasoning panel — typed causal edges + CoT steps (Phase A).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Chip, List, ListItem, ListItemText, Typography } from '@mui/material';
import { getApi } from '@/services/api/client';

type CausalEdge = {
  id: number;
  cause_kind: string;
  cause_id: number;
  effect_kind: string;
  effect_id: number;
  relation?: string;
  confidence?: number;
  evidence_grade?: string;
};

type ReasoningPayload = {
  reasoning_steps?: Array<Record<string, unknown> | string>;
  narrative?: string;
  causal_edges?: CausalEdge[];
  has_typed_edges?: boolean;
  edge_ids?: number[];
};

type Props = {
  domain?: string;
  storylineId?: number;
  trackedEventId?: number;
};

export default function ReasoningPanel({ domain, storylineId, trackedEventId }: Props) {
  const [data, setData] = useState<ReasoningPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const api = getApi();
      let path = '';
      if (storylineId != null && domain) {
        path = `/api/reasoning/${domain}/${storylineId}`;
      } else if (trackedEventId != null) {
        path = `/api/reasoning/event/${trackedEventId}`;
      } else {
        setData(null);
        return;
      }
      const res = await api.get(path);
      setData((res.data?.reasoning as ReasoningPayload) || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load reasoning');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [domain, storylineId, trackedEventId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <Typography variant='body2' color='text.secondary'>
        Loading reasoning…
      </Typography>
    );
  }
  if (error) {
    return <Alert severity='info'>{error}</Alert>;
  }
  if (!data) {
    return null;
  }

  const edges = data.causal_edges || [];
  const steps = data.reasoning_steps || [];

  return (
    <Box>
      <Typography variant='subtitle1' fontWeight={600} gutterBottom>
        Reasoning
      </Typography>
      {!data.has_typed_edges && edges.length === 0 ? (
        <Alert severity='warning' sx={{ mb: 1 }}>
          No typed causal edges yet — causal language is suppressed until evidence is graded.
        </Alert>
      ) : (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
          {edges.map(e => (
            <Chip
              key={e.id}
              size='small'
              label={`edge#${e.id} ${e.cause_kind}:${e.cause_id}→${e.effect_kind}:${e.effect_id} (${e.evidence_grade || 'weak'})`}
              variant='outlined'
            />
          ))}
        </Box>
      )}
      {steps.length > 0 && (
        <List dense disablePadding>
          {steps.map((s, i) => {
            const text =
              typeof s === 'string'
                ? s
                : String((s as Record<string, unknown>).claim || (s as Record<string, unknown>).action || JSON.stringify(s));
            return (
              <ListItem key={i} disableGutters>
                <ListItemText primary={`${i + 1}. ${text}`} />
              </ListItem>
            );
          })}
        </List>
      )}
      {data.narrative ? (
        <Typography variant='body2' sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
          {data.narrative}
        </Typography>
      ) : null}
    </Box>
  );
}
