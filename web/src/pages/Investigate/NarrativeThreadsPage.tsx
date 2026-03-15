/**
 * Narrative threads (Phase 3 T3.3 / Phase 5).
 * List threads, build from storylines for a domain, run synthesis.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Skeleton,
  Typography,
  Alert,
  Snackbar,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import Refresh from '@mui/icons-material/Refresh';
import Build from '@mui/icons-material/Build';
import MenuBook from '@mui/icons-material/MenuBook';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { contextCentricApi, type NarrativeThread } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

export default function NarrativeThreadsPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [items, setItems] = useState<NarrativeThread[]>([]);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [synthesisOpen, setSynthesisOpen] = useState(false);
  const [synthesisText, setSynthesisText] = useState<string | null>(null);
  const [synthesisLoading, setSynthesisLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; severity: 'success' | 'error' | 'info' } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await contextCentricApi.getNarrativeThreads({ domain_key: domain || undefined, limit: 100 }).catch(() => ({ items: [] }));
      setItems(res?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, [domain]);

  useEffect(() => {
    load();
  }, [load]);

  const handleBuild = async () => {
    if (!domain) return;
    setBuilding(true);
    try {
      const res = await contextCentricApi.buildNarrativeThreads({ domain_key: domain, limit: 50 });
      setMessage({
        text: `Built ${res.built} thread(s).${res.errors?.length ? ` Errors: ${res.errors.slice(0, 2).join('; ')}` : ''}`,
        severity: res.errors?.length && res.built === 0 ? 'error' : 'success',
      });
      await load();
    } catch (e) {
      setMessage({ text: (e as Error)?.message ?? 'Build failed', severity: 'error' });
    } finally {
      setBuilding(false);
    }
  };

  const handleSynthesize = async () => {
    setSynthesisLoading(true);
    setSynthesisOpen(true);
    setSynthesisText(null);
    try {
      const res = await contextCentricApi.synthesizeNarrativeThreads(domain ? { domain_key: domain } : undefined);
      setSynthesisText(res?.synthesis ?? 'No synthesis returned.');
    } catch (e) {
      setSynthesisText(`Error: ${(e as Error)?.message ?? 'Synthesis failed'}`);
    } finally {
      setSynthesisLoading(false);
    }
  };

  return (
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate`)} sx={{ mb: 2 }}>
        Back to Investigate
      </Button>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Narrative threads
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" startIcon={<Refresh />} onClick={load} disabled={loading}>
            Refresh
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<Build />}
            onClick={handleBuild}
            disabled={building || !domain}
          >
            {building ? 'Building…' : `Build for ${domain || '…'}`}
          </Button>
          <Button variant="contained" size="small" startIcon={<MenuBook />} onClick={handleSynthesize} disabled={synthesisLoading}>
            {synthesisLoading ? 'Synthesizing…' : 'Synthesize'}
          </Button>
        </Box>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Threads are built from storylines (summary + linked articles). Build for the current domain, then run Synthesize to combine thread summaries.
      </Typography>
      {loading ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} variant="rectangular" height={72} sx={{ borderRadius: 1 }} />
          ))}
        </Box>
      ) : items.length === 0 ? (
        <Card variant="outlined">
          <CardContent>
            <Typography color="text.secondary">
              No narrative threads yet. Use <strong>Build for {domain || 'domain'}</strong> to create threads from storylines in this domain.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {items.map((t) => (
            <Card key={t.id} variant="outlined">
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Chip label={t.domain_key} size="small" variant="outlined" />
                  <Typography variant="caption" color="text.disabled">
                    Storyline #{t.storyline_id}
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ mt: 0.5 }} color="text.secondary">
                  {t.summary_snippet || '(No summary)'}
                </Typography>
                {t.linked_article_ids?.length > 0 && (
                  <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
                    {t.linked_article_ids.length} article(s)
                  </Typography>
                )}
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
      <Dialog open={synthesisOpen} onClose={() => setSynthesisOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Synthesis</DialogTitle>
        <DialogContent>
          {synthesisLoading ? (
            <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 1 }} />
          ) : (
            <Typography component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.875rem' }}>
              {synthesisText}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSynthesisOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={!!message}
        autoHideDuration={6000}
        onClose={() => setMessage(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={message?.severity ?? 'info'} onClose={() => setMessage(null)}>
          {message?.text}
        </Alert>
      </Snackbar>
    </Box>
  );
}
