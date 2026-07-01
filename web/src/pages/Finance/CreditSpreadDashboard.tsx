/**
 * Credit spread dashboard — FRED HY/IG OAS with recession shading + ETF yield calculator.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  Skeleton,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useDomain } from '@/contexts/DomainContext';
import { monitoringApi } from '@/services/api/monitoring';
import Logger from '@/utils/logger';

type SpreadStatus = 'Normal' | 'Elevated' | 'Warning' | 'Danger' | 'Crisis';
type TimeRange = '1y' | '3y';
type DashboardTab = 'fred' | 'etf';

/** Finance silo — credit spread API lives under /api/finance/finance/... */
const FINANCE_DOMAIN = 'finance';

const DAYS_MAP: Record<TimeRange, number> = {
  '1y': 365,
  '3y': 365 * 3,
};

const STATUS_COLOR: Record<
  SpreadStatus,
  'success' | 'info' | 'warning' | 'error' | 'default'
> = {
  Normal: 'success',
  Elevated: 'info',
  Warning: 'warning',
  Danger: 'error',
  Crisis: 'error',
};

const HY_THRESHOLDS = [
  { bps: 300, label: 'Elevated' },
  { bps: 450, label: 'Warning' },
  { bps: 600, label: 'Danger' },
  { bps: 800, label: 'Crisis' },
];

const HY_LEVELS: { range: string; status: SpreadStatus; interpretation: string }[] = [
  { range: '< 300 bps', status: 'Normal', interpretation: 'Low stress' },
  { range: '300–450 bps', status: 'Elevated', interpretation: 'Some concern' },
  { range: '450–600 bps', status: 'Warning', interpretation: 'Approaching stress' },
  { range: '600–800 bps', status: 'Danger', interpretation: 'Bubble risk high' },
  { range: '> 800 bps', status: 'Crisis', interpretation: 'Credit markets freezing' },
];

const IG_LEVELS: { range: string; status: SpreadStatus }[] = [
  { range: '< 100 bps', status: 'Normal' },
  { range: '100–150 bps', status: 'Elevated' },
  { range: '150–200 bps', status: 'Warning' },
  { range: '> 200 bps', status: 'Crisis' },
];

type FredPayload = {
  hy_spread?: { date: string; value_bps: number }[];
  ig_spread?: { date: string; value_bps: number }[];
  recession_periods?: { start: string; end: string }[];
  latest?: {
    hy_bps?: number;
    ig_bps?: number;
    hy_status?: SpreadStatus;
    ig_status?: SpreadStatus;
  };
  series_ids?: Record<string, string>;
  data_window_note?: string | null;
};

type EtfSpreadRow = {
  credit_etf: string;
  treasury_etf: string;
  credit_yield_pct: number;
  treasury_yield_pct: number;
  spread_bps: number;
  status: SpreadStatus;
};

type EtfPayload = {
  hyg_tlt?: EtfSpreadRow | null;
  lqd_tlt?: EtfSpreadRow | null;
  latest?: {
    hy_bps?: number;
    ig_bps?: number;
    hy_status?: SpreadStatus;
    ig_status?: SpreadStatus;
  };
  formula?: string;
};

function mergeChartRows(
  hy: { date: string; value_bps: number }[],
  ig: { date: string; value_bps: number }[]
) {
  const byDate = new Map<string, { date: string; hy_bps?: number; ig_bps?: number }>();
  for (const row of hy) {
    byDate.set(row.date, { date: row.date, hy_bps: row.value_bps });
  }
  for (const row of ig) {
    const existing = byDate.get(row.date) ?? { date: row.date };
    existing.ig_bps = row.value_bps;
    byDate.set(row.date, existing);
  }
  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function StatusChip({ status }: { status?: SpreadStatus }) {
  if (!status) return null;
  return <Chip size='small' label={status} color={STATUS_COLOR[status]} />;
}

function SpreadStatCard({
  title,
  bps,
  status,
  loading,
}: {
  title: string;
  bps?: number;
  status?: SpreadStatus;
  loading: boolean;
}) {
  return (
    <Card variant='outlined' sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant='subtitle2' color='text.secondary' gutterBottom>
          {title}
        </Typography>
        {loading ? (
          <Skeleton width='40%' height={40} />
        ) : bps != null ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant='h4' sx={{ fontWeight: 700 }}>
              {bps.toFixed(0)}
            </Typography>
            <Typography variant='body2' color='text.secondary'>
              bps
            </Typography>
            <StatusChip status={status} />
          </Box>
        ) : (
          <Typography color='text.secondary'>No data</Typography>
        )}
      </CardContent>
    </Card>
  );
}

export default function CreditSpreadDashboard() {
  const { domain } = useDomain();
  if (domain !== FINANCE_DOMAIN) {
    return <Navigate to={`/${FINANCE_DOMAIN}/credit-spread`} replace />;
  }
  return <CreditSpreadDashboardContent />;
}

function CreditSpreadDashboardContent() {
  const [tab, setTab] = useState<DashboardTab>('fred');
  const [timeRange, setTimeRange] = useState<TimeRange>('1y');
  const [loadingFred, setLoadingFred] = useState(true);
  const [loadingEtf, setLoadingEtf] = useState(true);
  const [fredData, setFredData] = useState<FredPayload | null>(null);
  const [etfData, setEtfData] = useState<EtfPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadFred = useCallback(async () => {
    setLoadingFred(true);
    setError(null);
    try {
      const res = await monitoringApi.getCreditSpread(
        { days: DAYS_MAP[timeRange], view: 'fred' },
        FINANCE_DOMAIN
      );
      if (res.success) {
        setFredData(res.data as FredPayload);
      } else {
        setError(res.error || 'Failed to load FRED credit spread data');
      }
    } catch (err) {
      Logger.apiError('Credit spread FRED load failed', err as Error);
      setError((err as Error).message);
    } finally {
      setLoadingFred(false);
    }
  }, [timeRange]);

  const loadEtf = useCallback(async () => {
    setLoadingEtf(true);
    try {
      const res = await monitoringApi.getCreditSpread(
        { view: 'etf' },
        FINANCE_DOMAIN
      );
      if (res.success) {
        setEtfData(res.data as EtfPayload);
      }
    } catch (err) {
      Logger.apiError('Credit spread ETF load failed', err as Error);
    } finally {
      setLoadingEtf(false);
    }
  }, []);

  useEffect(() => {
    loadFred();
  }, [loadFred]);

  useEffect(() => {
    if (tab === 'etf') {
      loadEtf();
    }
  }, [tab, loadEtf]);

  const chartData = useMemo(
    () =>
      mergeChartRows(
        fredData?.hy_spread ?? [],
        fredData?.ig_spread ?? []
      ),
    [fredData]
  );

  const latest = tab === 'fred' ? fredData?.latest : etfData?.latest;
  const loading = tab === 'fred' ? loadingFred : loadingEtf;

  return (
    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant='h5' sx={{ fontWeight: 700, mb: 0.5 }}>
        Credit spread
      </Typography>
      <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
        High-yield and investment-grade credit stress vs. Treasuries. FRED ICE BofA OAS
        with NBER recession shading, or daily ETF yield spreads (HYG−TLT, LQD−TLT).
      </Typography>

      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6}>
          <SpreadStatCard
            title='High yield spread'
            bps={latest?.hy_bps}
            status={latest?.hy_status}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <SpreadStatCard
            title='Investment grade spread'
            bps={latest?.ig_bps}
            status={latest?.ig_status}
            loading={loading}
          />
        </Grid>
      </Grid>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab value='fred' label='FRED (historical)' />
        <Tab value='etf' label='ETF calculator (daily)' />
      </Tabs>

      {tab === 'fred' && (
        <>
          {fredData?.data_window_note && (
            <Alert severity='info' sx={{ mb: 2 }}>
              {fredData.data_window_note}
            </Alert>
          )}
          <Card variant='outlined' sx={{ mb: 3 }}>
            <CardHeader
              title='HY & IG option-adjusted spreads'
              subheader={
                fredData?.series_ids
                  ? `HY: ${fredData.series_ids.hy_oas} · IG: ${fredData.series_ids.ig_oas}`
                  : undefined
              }
              action={
                <ToggleButtonGroup
                  size='small'
                  value={timeRange}
                  exclusive
                  onChange={(_, v) => v != null && setTimeRange(v)}
                >
                  <ToggleButton value='1y'>1y</ToggleButton>
                  <ToggleButton value='3y'>3y</ToggleButton>
                </ToggleButtonGroup>
              }
            />
            <CardContent sx={{ pt: 0 }}>
              {loadingFred ? (
                <Skeleton variant='rectangular' height={320} sx={{ borderRadius: 1 }} />
              ) : chartData.length === 0 ? (
                <Typography color='text.secondary'>
                  No FRED observations. Set FRED_API_KEY on the API host.
                </Typography>
              ) : (
                <ResponsiveContainer width='100%' height={320}>
                  <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    {(fredData?.recession_periods ?? []).map((p) => (
                      <ReferenceArea
                        key={`${p.start}-${p.end}`}
                        x1={p.start}
                        x2={p.end}
                        fill='#bdbdbd'
                        fillOpacity={0.25}
                        ifOverflow='hidden'
                      />
                    ))}
                    <CartesianGrid strokeDasharray='3 3' stroke='#eee' />
                    <XAxis dataKey='date' tick={{ fontSize: 11 }} minTickGap={40} />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      domain={['auto', 'auto']}
                      label={{ value: 'bps', angle: -90, position: 'insideLeft', offset: 8 }}
                    />
                    <Tooltip
                      formatter={(v: number, name: string) => [
                        v != null ? `${v.toFixed(0)} bps` : '—',
                        name,
                      ]}
                    />
                    <Legend />
                    <Line
                      type='monotone'
                      dataKey='hy_bps'
                      name='High yield OAS'
                      stroke='#c62828'
                      dot={false}
                      strokeWidth={2}
                      connectNulls
                    />
                    <Line
                      type='monotone'
                      dataKey='ig_bps'
                      name='IG corporate OAS'
                      stroke='#1565c0'
                      dot={false}
                      strokeWidth={2}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
              <Typography variant='caption' color='text.secondary' display='block' sx={{ mt: 1 }}>
                Gray bands = NBER recession periods (USREC).
              </Typography>
            </CardContent>
          </Card>
        </>
      )}

      {tab === 'etf' && (
        <>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {(['hyg_tlt', 'lqd_tlt'] as const).map((key) => {
              const row = etfData?.[key];
              const label = key === 'hyg_tlt' ? 'HYG − TLT' : 'LQD − TLT';
              return (
                <Grid item xs={12} md={6} key={key}>
                  <Card variant='outlined'>
                    <CardHeader title={label} subheader={etfData?.formula} />
                    <CardContent>
                      {loadingEtf ? (
                        <Skeleton height={80} />
                      ) : row ? (
                        <Box>
                          <Typography variant='h4' sx={{ fontWeight: 700 }}>
                            {row.spread_bps.toFixed(0)}{' '}
                            <Typography component='span' variant='body2' color='text.secondary'>
                              bps
                            </Typography>
                          </Typography>
                          <StatusChip status={row.status} />
                          <Typography variant='body2' sx={{ mt: 1 }} color='text.secondary'>
                            {row.credit_etf} yield: {row.credit_yield_pct.toFixed(2)}% ·{' '}
                            {row.treasury_etf} yield: {row.treasury_yield_pct.toFixed(2)}%
                          </Typography>
                        </Box>
                      ) : (
                        <Typography color='text.secondary'>
                          ETF yields unavailable (yfinance / network).
                        </Typography>
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>

          <Card variant='outlined' sx={{ mb: 3 }}>
            <CardHeader title='HYG − TLT threshold bands (bps)' />
            <CardContent>
              <ResponsiveContainer width='100%' height={200}>
                <LineChart
                  data={[
                    {
                      label: 'now',
                      spread: etfData?.hyg_tlt?.spread_bps ?? 350,
                    },
                  ]}
                  margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                >
                  <XAxis dataKey='label' hide />
                  <YAxis domain={[0, 900]} tick={{ fontSize: 11 }} />
                  {HY_THRESHOLDS.map((t) => (
                    <ReferenceLine
                      key={t.bps}
                      y={t.bps}
                      stroke='#9e9e9e'
                      strokeDasharray='4 4'
                      label={{ value: t.label, position: 'right', fontSize: 10 }}
                    />
                  ))}
                  <Line
                    type='monotone'
                    dataKey='spread'
                    stroke='#c62828'
                    strokeWidth={3}
                    dot={{ r: 6 }}
                  />
                  <Tooltip formatter={(v: number) => [`${v?.toFixed(0)} bps`, 'HY spread']} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Card variant='outlined'>
                <CardHeader title='High yield (HYG − TLT)' />
                <Table size='small'>
                  <TableHead>
                    <TableRow>
                      <TableCell>Spread</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Interpretation</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {HY_LEVELS.map((row) => (
                      <TableRow key={row.range}>
                        <TableCell>{row.range}</TableCell>
                        <TableCell>
                          <StatusChip status={row.status} />
                        </TableCell>
                        <TableCell>{row.interpretation}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card variant='outlined'>
                <CardHeader title='Investment grade (LQD − TLT)' />
                <Table size='small'>
                  <TableHead>
                    <TableRow>
                      <TableCell>Spread</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {IG_LEVELS.map((row) => (
                      <TableRow key={row.range}>
                        <TableCell>{row.range}</TableCell>
                        <TableCell>
                          <StatusChip status={row.status} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  );
}
