/**
 * Identity spine browser — proxy to NRI spine entities + match preview.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import SearchIcon from '@mui/icons-material/Search';
import {
  contextCentricApi,
  type NriSpineEntity,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import {
  PageShell,
  DataTable,
  LoadingState,
  UiBadge,
  UiCard,
} from '@/components/ui';

const DATASETS = ['', 'wikidata', 'edgar', 'congress', 'wikidata_lazy'];

export default function SpineBrowserPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [dataset, setDataset] = useState('');
  const [entities, setEntities] = useState<NriSpineEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [matchText, setMatchText] = useState('');
  const [matchSchema, setMatchSchema] = useState('');
  const [matchResult, setMatchResult] = useState<Record<string, unknown> | null>(null);
  const [matching, setMatching] = useState(false);

  const loadEntities = useCallback(async () => {
    setLoading(true);
    try {
      const res = await contextCentricApi.getNriSpineEntities({
        dataset: dataset || undefined,
        limit: 100,
      });
      setEntities(res?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, [dataset]);

  useEffect(() => {
    loadEntities();
  }, [loadEntities]);

  const runMatch = async () => {
    if (!matchText.trim()) return;
    setMatching(true);
    try {
      const res = await contextCentricApi.matchNriSpine(
        matchText.trim(),
        matchSchema || undefined,
      );
      setMatchResult(res);
    } finally {
      setMatching(false);
    }
  };

  const matchItems = Array.isArray(matchResult?.matches)
    ? (matchResult.matches as NriSpineEntity[])
    : Array.isArray(matchResult?.items)
      ? (matchResult.items as NriSpineEntity[])
      : [];

  return (
    <PageShell
      title='Spine browser'
      subtitle='Identity spine lookup (Wikidata, EDGAR, Congress)'
      breadcrumbs={[
        { label: 'Investigate', to: `/${domain}/investigate` },
        { label: 'Spine browser' },
      ]}
      actions={
        <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate`)}>
          Hub
        </Button>
      }
    >
      <UiCard title='Match preview' sx={{ mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems='flex-start'>
          <TextField
            label='Entity text'
            value={matchText}
            onChange={e => setMatchText(e.target.value)}
            fullWidth
            size='small'
            placeholder='e.g. Janet Yellen'
          />
          <FormControl size='small' sx={{ minWidth: 140 }}>
            <InputLabel>Schema</InputLabel>
            <Select
              label='Schema'
              value={matchSchema}
              onChange={e => setMatchSchema(e.target.value)}
            >
              <MenuItem value=''>Any</MenuItem>
              <MenuItem value='Person'>Person</MenuItem>
              <MenuItem value='Organization'>Organization</MenuItem>
              <MenuItem value='Company'>Company</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant='contained'
            startIcon={<SearchIcon />}
            onClick={runMatch}
            disabled={matching || !matchText.trim()}
          >
            Match
          </Button>
        </Stack>
        {matchResult && (
          <Box sx={{ mt: 2 }}>
            {matchItems.length === 0 ? (
              <Typography variant='body2' color='text.secondary'>
                No matches returned.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {matchItems.slice(0, 8).map((m, i) => (
                  <Stack key={i} direction='row' spacing={1} alignItems='center'>
                    <Typography variant='body2'>{m.caption ?? m.ftm_id}</Typography>
                    {m.dataset && <UiBadge label={m.dataset} />}
                    {m.score != null && (
                      <Typography variant='caption' color='text.secondary'>
                        {m.score.toFixed(3)}
                      </Typography>
                    )}
                  </Stack>
                ))}
              </Stack>
            )}
          </Box>
        )}
      </UiCard>

      <Stack direction='row' spacing={2} alignItems='center' sx={{ mb: 2 }}>
        <FormControl size='small' sx={{ minWidth: 180 }}>
          <InputLabel>Dataset filter</InputLabel>
          <Select
            label='Dataset filter'
            value={dataset}
            onChange={e => setDataset(e.target.value)}
          >
            {DATASETS.map(d => (
              <MenuItem key={d || 'all'} value={d}>
                {d || 'All datasets'}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button size='small' onClick={loadEntities}>
          Refresh
        </Button>
      </Stack>

      {loading ? (
        <LoadingState message='Loading spine entities…' />
      ) : (
        <DataTable
          rows={entities.map((e, i) => ({ ...e, id: e.ftm_id ?? i }))}
          columns={[
            { key: 'caption', header: 'Caption', render: row => row.caption ?? '—' },
            { key: 'ftm_id', header: 'FtM ID', render: row => row.ftm_id ?? '—' },
            { key: 'schema', header: 'Schema', render: row => row.schema_name ?? '—' },
            { key: 'dataset', header: 'Dataset', render: row => row.dataset ?? '—' },
          ]}
        />
      )}
    </PageShell>
  );
}
