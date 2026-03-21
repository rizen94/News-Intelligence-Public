/**
 * Context-centric search (claims, contexts, patterns).
 */
import React, { useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  TextField,
  Button,
  Box,
  List,
  ListItemText,
} from '@mui/material';
import { contextCentricApi } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

export default function SearchPage() {
  const { domain } = useDomain();
  const [q, setQ] = useState('');
  const [results, setResults] = useState<{
    claims: unknown[];
    contexts: unknown[];
    pattern_discoveries: unknown[];
  } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await contextCentricApi.search({
        q: q.trim(),
        domain_key: domain,
        limit: 20,
      });
      setResults(res ?? null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant='h5' sx={{ mb: 2, fontWeight: 600 }}>
        Search
      </Typography>
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <TextField
            fullWidth
            size='small'
            placeholder='Search claims, contexts…'
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <Button
            variant='contained'
            onClick={handleSearch}
            disabled={loading}
            sx={{ mt: 2 }}
          >
            Search
          </Button>
        </CardContent>
      </Card>
      {results && (
        <Card>
          <CardHeader title='Results' />
          <CardContent>
            <Typography variant='subtitle2'>
              Claims ({results.claims?.length ?? 0})
            </Typography>
            <List dense>
              {(
                results.claims as {
                  subject_text?: string;
                  predicate_text?: string;
                  object_text?: string;
                }[]
              )
                .slice(0, 5)
                .map((c, i) => (
                  <ListItemText
                    key={i}
                    primary={
                      `${c.subject_text ?? ''} ${c.predicate_text ?? ''} ${
                        c.object_text ?? ''
                      }`.trim() || '—'
                    }
                  />
                ))}
            </List>
            <Typography variant='subtitle2' sx={{ mt: 2 }}>
              Contexts ({results.contexts?.length ?? 0})
            </Typography>
            <List dense>
              {(results.contexts as { title?: string }[])
                .slice(0, 5)
                .map((c, i) => (
                  <ListItemText key={i} primary={c.title || '—'} />
                ))}
            </List>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
