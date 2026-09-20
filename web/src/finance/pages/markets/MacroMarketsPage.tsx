/**
 * Core FRED macro series under /finance/markets/macro.
 * Uses existing market-data + fetch-fred APIs.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { monitoringApi } from '../../../services/api/monitoring';
import Logger from '../../../utils/logger';

const FINANCE_DOMAIN = 'finance';

const MACRO_SERIES = [
  { id: 'FEDFUNDS', label: 'Federal funds rate' },
  { id: 'DGS10', label: '10-year Treasury' },
  { id: 'CPIAUCSL', label: 'CPI all items' },
  { id: 'DTWEXBGS', label: 'Trade-weighted USD' },
  { id: 'T10YIE', label: '10y breakeven inflation' },
  { id: 'M2SL', label: 'M2 money stock' },
  { id: 'UNRATE', label: 'Unemployment rate' },
];

export default function MacroMarketsPage() {
  const [seriesId, setSeriesId] = useState(MACRO_SERIES[0].id);
  const [points, setPoints] = useState<{ date: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await monitoringApi.getFinanceMarketData(
        { source: 'fred', symbol: seriesId },
        FINANCE_DOMAIN
      );
      if (!res.success) {
        setError(res.error || 'Failed to load market data');
        setPoints([]);
        return;
      }
      const obs = res.data?.observations || [];
      setPoints(
        obs
          .map((o: { date?: string; value?: number | string }) => {
            const value = Number(o.value);
            return { date: o.date || '', value };
          })
          .filter((o: { date: string; value: number }) => o.date && !Number.isNaN(o.value))
      );
    } catch (err) {
      Logger.apiError('Macro series load failed', err as Error);
      setError((err as Error).message);
      setPoints([]);
    } finally {
      setLoading(false);
    }
  }, [seriesId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onFetch = async () => {
    setFetching(true);
    setError(null);
    try {
      const res = await monitoringApi.triggerFredFetch({ symbol: seriesId }, FINANCE_DOMAIN);
      if (res?.success === false) {
        setError(res.error || 'FRED fetch failed');
      }
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setFetching(false);
    }
  };

  const label = MACRO_SERIES.find(s => s.id === seriesId)?.label || seriesId;

  return (
    <div>
      <h1 className='finance-page-title'>FRED macro</h1>
      <p className='finance-page-lede'>
        Core macro series from the finance market store. Fetch pulls live FRED observations when
        FRED_API_KEY is configured.
      </p>

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <FormControl size='small' sx={{ minWidth: 220 }}>
          <InputLabel id='fin-macro-label'>Series</InputLabel>
          <Select
            labelId='fin-macro-label'
            label='Series'
            value={seriesId}
            onChange={e => setSeriesId(e.target.value)}
          >
            {MACRO_SERIES.map(s => (
              <MenuItem key={s.id} value={s.id}>
                {s.label} ({s.id})
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant='outlined' size='small' disabled={fetching} onClick={() => void onFetch()}>
          {fetching ? 'Fetching…' : 'Fetch from FRED'}
        </Button>
      </Box>

      {error && (
        <Alert severity='warning' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={32} />
        </Box>
      ) : points.length === 0 ? (
        <Typography color='text.secondary'>
          No stored observations for {label}. Use Fetch from FRED to populate the market store.
        </Typography>
      ) : (
        <>
          <Typography variant='subtitle2' color='text.secondary' sx={{ mb: 1 }}>
            {label} · {points.length} points · latest{' '}
            {points[points.length - 1]?.value?.toFixed?.(2) ?? points[points.length - 1]?.value}
          </Typography>
          <ResponsiveContainer width='100%' height={340}>
            <LineChart data={points} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray='3 3' stroke='#eee' />
              <XAxis dataKey='date' tick={{ fontSize: 11 }} minTickGap={40} />
              <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
              <Tooltip />
              <Line
                type='monotone'
                dataKey='value'
                stroke='#0d5c63'
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
