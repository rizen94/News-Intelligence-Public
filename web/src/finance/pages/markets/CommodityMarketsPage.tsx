/**
 * Commodity view under /finance/markets/commodity/:commodity.
 * Reuses monitoring commodity APIs; keeps navigation inside the Finance product tree.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
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
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { monitoringApi } from '../../../services/api/monitoring';
import Logger from '../../../utils/logger';

const FINANCE_DOMAIN = 'finance';
const FALLBACK = [
  { id: 'gold', label: 'Gold' },
  { id: 'silver', label: 'Silver' },
  { id: 'platinum', label: 'Platinum' },
  { id: 'oil', label: 'Oil (WTI)' },
  { id: 'gas', label: 'Natural gas' },
];

type Spot = { price?: number; unit?: string; as_of?: string; source?: string };

export default function CommodityMarketsPage() {
  const { commodity: commodityParam } = useParams<{ commodity: string }>();
  const navigate = useNavigate();
  const commodity = (commodityParam || 'gold').toLowerCase();
  const [list, setList] = useState(FALLBACK);
  const [history, setHistory] = useState<{ date: string; value: number }[]>([]);
  const [spot, setSpot] = useState<Spot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await monitoringApi.getCommodities(FINANCE_DOMAIN);
        const items = res?.data?.commodities || res?.data;
        if (!cancelled && Array.isArray(items) && items.length) {
          setList(
            items.map((c: { id: string; label?: string }) => ({
              id: c.id,
              label: c.label || c.id,
            }))
          );
        }
      } catch {
        /* keep fallback */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [hist, sp] = await Promise.all([
          monitoringApi.getCommodityHistory(commodity, { days: 365 }, FINANCE_DOMAIN),
          monitoringApi.getCommoditySpot(commodity, FINANCE_DOMAIN),
        ]);
        if (cancelled) return;
        const obs = hist?.data?.observations || hist?.data || [];
        setHistory(
          (Array.isArray(obs) ? obs : [])
            .map((o: { date?: string; value?: number; price?: number }) => ({
              date: o.date || '',
              value: Number(o.value ?? o.price ?? NaN),
            }))
            .filter((o: { date: string; value: number }) => o.date && !Number.isNaN(o.value))
        );
        setSpot((sp?.data as Spot) || null);
      } catch (err) {
        Logger.apiError('Commodity markets load failed', err as Error);
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [commodity]);

  const label = useMemo(
    () => list.find(c => c.id === commodity)?.label || commodity,
    [list, commodity]
  );

  const onFetch = async () => {
    setFetching(true);
    try {
      await monitoringApi.triggerCommodityPriceFetch(commodity, {}, FINANCE_DOMAIN);
      const hist = await monitoringApi.getCommodityHistory(
        commodity,
        { days: 365 },
        FINANCE_DOMAIN
      );
      const obs = hist?.data?.observations || hist?.data || [];
      setHistory(
        (Array.isArray(obs) ? obs : [])
          .map((o: { date?: string; value?: number; price?: number }) => ({
            date: o.date || '',
            value: Number(o.value ?? o.price ?? NaN),
          }))
          .filter((o: { date: string; value: number }) => o.date && !Number.isNaN(o.value))
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setFetching(false);
    }
  };

  return (
    <div>
      <h1 className='finance-page-title'>Commodities</h1>
      <p className='finance-page-lede'>
        Registry commodities under the Finance product home. Full classic dashboard with
        geo/news overlays remains at{' '}
        <Link to={`/finance/commodity/${commodity}`}>/finance/commodity/{commodity}</Link>.
      </p>

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <FormControl size='small' sx={{ minWidth: 180 }}>
          <InputLabel id='fin-commodity-label'>Commodity</InputLabel>
          <Select
            labelId='fin-commodity-label'
            label='Commodity'
            value={commodity}
            onChange={e => navigate(`/finance/markets/commodity/${e.target.value}`)}
          >
            {list.map(c => (
              <MenuItem key={c.id} value={c.id}>
                {c.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant='outlined' size='small' disabled={fetching} onClick={() => void onFetch()}>
          {fetching ? 'Fetching…' : 'Fetch prices'}
        </Button>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={32} />
        </Box>
      ) : (
        <>
          <Typography variant='h6' sx={{ mb: 1 }}>
            {label} spot{' '}
            {spot?.price != null ? (
              <strong>
                {spot.price.toFixed(2)} {spot.unit || ''}
              </strong>
            ) : (
              <Typography component='span' color='text.secondary'>
                unavailable
              </Typography>
            )}
          </Typography>
          {spot?.as_of && (
            <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 2 }}>
              As of {spot.as_of}
              {spot.source ? ` · ${spot.source}` : ''}
            </Typography>
          )}
          {history.length === 0 ? (
            <Typography color='text.secondary'>
              No stored history. Use Fetch prices (needs FRED / metals keys where applicable).
            </Typography>
          ) : (
            <ResponsiveContainer width='100%' height={320}>
              <AreaChart data={history} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id='finCommGrad' x1='0' y1='0' x2='0' y2='1'>
                    <stop offset='0%' stopColor='#0d5c63' stopOpacity={0.35} />
                    <stop offset='100%' stopColor='#0d5c63' stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray='3 3' stroke='#eee' />
                <XAxis dataKey='date' tick={{ fontSize: 11 }} minTickGap={40} />
                <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                <Tooltip />
                <Area
                  type='monotone'
                  dataKey='value'
                  stroke='#0d5c63'
                  fill='url(#finCommGrad)'
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </>
      )}
    </div>
  );
}
