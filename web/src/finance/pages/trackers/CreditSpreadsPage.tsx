/**
 * Credit spreads tracker under /finance/trackers — adapted from classic CreditSpreadDashboard.
 * No redirect to classic domain routes; always calls finance API silo.
 * Warning/progress cues render on each chart/metric panel (not a standalone legend grid).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import { monitoringApi } from '../../../services/api/monitoring';
import Logger from '../../../utils/logger';

type SpreadStatus = 'Normal' | 'Elevated' | 'Warning' | 'Danger' | 'Crisis';
type TimeRange = '1y' | '3y';
type DashboardTab = 'fred' | 'etf';

const FINANCE_DOMAIN = 'finance';
const DAYS_MAP: Record<TimeRange, number> = { '1y': 365, '3y': 365 * 3 };

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

type IndicatorBand = { range: string; status: string };

type IndicatorRef = {
  id: string;
  label: string;
  series_id?: string | null;
  source?: string | null;
  live: boolean;
  what: string;
  warning: string;
  progress: string;
  bands?: IndicatorBand[];
};

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
  indicator_refs?: IndicatorRef[];
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
  indicator_refs?: IndicatorRef[];
};

/** Fallback if an older API omits indicator_refs */
const FALLBACK_INDICATOR_REFS: IndicatorRef[] = [
  {
    id: 'hy_oas',
    label: 'HY OAS',
    series_id: 'BAMLH0A0HYM2',
    source: 'FRED / ICE BofA',
    live: true,
    what: 'Option-adjusted spread of US high-yield corporates over Treasuries.',
    warning: 'Widening → credit stress, risk-off, refinancing pressure.',
    progress: 'Narrowing / stable → relief, risk appetite, easier credit.',
    bands: [
      { range: '< 300 bps', status: 'Normal' },
      { range: '300–450 bps', status: 'Elevated' },
      { range: '450–600 bps', status: 'Warning' },
      { range: '600–800 bps', status: 'Danger' },
      { range: '> 800 bps', status: 'Crisis' },
    ],
  },
  {
    id: 'ig_oas',
    label: 'IG OAS',
    series_id: 'BAMLC0A0CM',
    source: 'FRED / ICE BofA',
    live: true,
    what: 'Option-adjusted spread of US investment-grade corporates over Treasuries.',
    warning: 'Widening → IG funding stress; often leads HY in calm→stress turns.',
    progress: 'Narrowing / stable → IG credit normalising.',
    bands: [
      { range: '< 100 bps', status: 'Normal' },
      { range: '100–150 bps', status: 'Elevated' },
      { range: '150–200 bps', status: 'Warning' },
      { range: '> 200 bps', status: 'Crisis' },
    ],
  },
  {
    id: 'usrec',
    label: 'USREC (NBER)',
    series_id: 'USREC',
    source: 'FRED',
    live: true,
    what: 'Binary US recession indicator (NBER dates). Chart gray bands when active.',
    warning: 'Active (=1) → recession window; treat as stress context, not a spread.',
    progress: 'Inactive (=0) → expansion; remove recession shading.',
    bands: [
      { range: '0', status: 'Expansion' },
      { range: '1', status: 'Recession' },
    ],
  },
  {
    id: 'hyg_tlt',
    label: 'HYG − TLT',
    live: true,
    source: 'Yahoo / yfinance',
    what: 'Daily ETF yield proxy: high-yield bond ETF minus long Treasury ETF.',
    warning: 'Widening → same directional stress signal as HY OAS (noisier).',
    progress: 'Narrowing / stable → relief vs Treasuries.',
    bands: [
      { range: '< 300 bps', status: 'Normal' },
      { range: '300–450 bps', status: 'Elevated' },
      { range: '450–600 bps', status: 'Warning' },
      { range: '600–800 bps', status: 'Danger' },
      { range: '> 800 bps', status: 'Crisis' },
    ],
  },
  {
    id: 'lqd_tlt',
    label: 'LQD − TLT',
    live: true,
    source: 'Yahoo / yfinance',
    what: 'Daily ETF yield proxy: IG corporate ETF minus long Treasury ETF.',
    warning: 'Widening → IG stress proxy (can print near-zero/negative in calm markets).',
    progress: 'Narrowing / stable → IG relief vs Treasuries.',
    bands: [
      { range: '< 100 bps', status: 'Normal' },
      { range: '100–150 bps', status: 'Elevated' },
      { range: '150–200 bps', status: 'Warning' },
      { range: '> 200 bps', status: 'Crisis' },
    ],
  },
  {
    id: 'move',
    label: 'MOVE (future)',
    live: false,
    what: 'ICE BofA US bond-market volatility index — not fetched yet.',
    warning: 'Rising vol → rates/credit uncertainty (when wired).',
    progress: 'Falling vol → calmer rates backdrop (when wired).',
    bands: [],
  },
  {
    id: 'sofr',
    label: 'SOFR (future)',
    live: false,
    what: 'Secured Overnight Financing Rate — funding backdrop; not fetched yet.',
    warning: 'Sharp rises → funding stress context (when wired).',
    progress: 'Stable/easing → calmer funding (when wired).',
    bands: [],
  },
];

function refById(refs: IndicatorRef[], id: string): IndicatorRef | undefined {
  return refs.find(r => r.id === id);
}

function bandForStatus(
  bands: IndicatorBand[] | undefined,
  status?: SpreadStatus | string
): string | null {
  if (!bands?.length || !status) return null;
  const match = bands.find(b => b.status === status);
  if (match) return `${match.status} (${match.range})`;
  return String(status);
}

/** Compact warning/progress cue overlaid on a chart or metric panel */
function ChartIndicatorCue({
  refItem,
  status,
  variant = 'series',
}: {
  refItem?: IndicatorRef;
  status?: SpreadStatus | string;
  variant?: 'series' | 'context';
}) {
  if (!refItem) return null;
  const bandLabel = bandForStatus(refItem.bands, status);
  return (
    <div
      className={`finance-chart-cue${variant === 'context' ? ' is-context' : ''}`}
      data-indicator-id={refItem.id}
    >
      <div className='finance-chart-cue__head'>
        <span className='finance-chart-cue__label'>{refItem.label}</span>
        {status && <StatusChip status={status as SpreadStatus} />}
        {(refItem.series_id || refItem.source) && (
          <span className='finance-chart-cue__meta'>
            {[refItem.series_id, refItem.source].filter(Boolean).join(' · ')}
          </span>
        )}
      </div>
      <dl className='finance-chart-cue__signs'>
        <div>
          <dt className='cue-warn'>Warning</dt>
          <dd>{refItem.warning}</dd>
        </div>
        <div>
          <dt className='cue-progress'>Progress</dt>
          <dd>{refItem.progress}</dd>
        </div>
      </dl>
      {bandLabel && <p className='finance-chart-cue__band'>Status band: {bandLabel}</p>}
    </div>
  );
}

function ChartCues({ children }: { children: React.ReactNode }) {
  return <div className='finance-chart-cues'>{children}</div>;
}

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
  if (!(status in STATUS_COLOR)) {
    return <Chip size='small' label={status} variant='outlined' />;
  }
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

export default function CreditSpreadsPage() {
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
      const res = await monitoringApi.getCreditSpread({ view: 'etf' }, FINANCE_DOMAIN);
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
    void loadFred();
  }, [loadFred]);

  useEffect(() => {
    if (tab === 'etf') void loadEtf();
  }, [tab, loadEtf]);

  const chartData = useMemo(
    () => mergeChartRows(fredData?.hy_spread ?? [], fredData?.ig_spread ?? []),
    [fredData]
  );

  const indicatorRefs = useMemo(() => {
    const fromApi = fredData?.indicator_refs ?? etfData?.indicator_refs;
    return fromApi && fromApi.length > 0 ? fromApi : FALLBACK_INDICATOR_REFS;
  }, [fredData, etfData]);

  const hyRef = refById(indicatorRefs, 'hy_oas');
  const igRef = refById(indicatorRefs, 'ig_oas');
  const usrecRef = refById(indicatorRefs, 'usrec');
  const hygRef = refById(indicatorRefs, 'hyg_tlt');
  const lqdRef = refById(indicatorRefs, 'lqd_tlt');

  const recessionActive = (fredData?.recession_periods?.length ?? 0) > 0;
  const usrecStatus = recessionActive ? 'Recession' : 'Expansion';

  const latest = tab === 'fred' ? fredData?.latest : etfData?.latest;
  const loading = tab === 'fred' ? loadingFred : loadingEtf;

  return (
    <div>
      <h1 className='finance-page-title'>Credit spreads</h1>
      <p className='finance-page-lede'>
        High-yield and investment-grade credit stress vs. Treasuries. Warning = widening;
        progress = narrowing / stable. Cues sit on each chart with the series they describe.
      </p>

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
              <ChartCues>
                <ChartIndicatorCue refItem={hyRef} status={fredData?.latest?.hy_status} />
                <ChartIndicatorCue refItem={igRef} status={fredData?.latest?.ig_status} />
                <ChartIndicatorCue
                  refItem={usrecRef}
                  status={usrecStatus}
                  variant='context'
                />
              </ChartCues>
              {loadingFred ? (
                <Skeleton variant='rectangular' height={320} sx={{ borderRadius: 1 }} />
              ) : chartData.length === 0 ? (
                <Typography color='text.secondary'>
                  No FRED observations. Set FRED_API_KEY on the API host.
                </Typography>
              ) : (
                <ResponsiveContainer width='100%' height={320}>
                  <LineChart data={chartData} margin={{ top: 8, right: 48, left: 0, bottom: 0 }}>
                    {(fredData?.recession_periods ?? []).map(p => (
                      <ReferenceArea
                        key={`${p.start}-${p.end}`}
                        x1={p.start}
                        x2={p.end}
                        fill='#bdbdbd'
                        fillOpacity={0.25}
                        ifOverflow='hidden'
                      />
                    ))}
                    {HY_THRESHOLDS.map(t => (
                      <ReferenceLine
                        key={`hy-${t.bps}`}
                        y={t.bps}
                        stroke='#c62828'
                        strokeOpacity={0.35}
                        strokeDasharray='3 4'
                        label={{
                          value: `HY ${t.label}`,
                          position: 'right',
                          fontSize: 9,
                          fill: '#c62828',
                        }}
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
                      stroke='#0d5c63'
                      dot={false}
                      strokeWidth={2}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
              <Typography variant='caption' color='text.secondary' display='block' sx={{ mt: 1 }}>
                Gray bands = NBER recession (USREC). Dashed red lines = HY status thresholds.
              </Typography>
            </CardContent>
          </Card>
        </>
      )}

      {tab === 'etf' && (
        <>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {(['hyg_tlt', 'lqd_tlt'] as const).map(key => {
              const row = etfData?.[key];
              const label = key === 'hyg_tlt' ? 'HYG − TLT' : 'LQD − TLT';
              const cue = key === 'hyg_tlt' ? hygRef : lqdRef;
              return (
                <Grid item xs={12} md={6} key={key}>
                  <Card variant='outlined'>
                    <CardHeader title={label} subheader={etfData?.formula} />
                    <CardContent>
                      <ChartCues>
                        <ChartIndicatorCue refItem={cue} status={row?.status} />
                      </ChartCues>
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
              <ChartCues>
                <ChartIndicatorCue
                  refItem={hygRef}
                  status={etfData?.hyg_tlt?.status}
                />
              </ChartCues>
              <ResponsiveContainer width='100%' height={200}>
                <LineChart
                  data={[{ label: 'now', spread: etfData?.hyg_tlt?.spread_bps ?? 350 }]}
                  margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                >
                  <XAxis dataKey='label' hide />
                  <YAxis domain={[0, 900]} tick={{ fontSize: 11 }} />
                  {HY_THRESHOLDS.map(t => (
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
                    {HY_LEVELS.map(row => (
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
                    {IG_LEVELS.map(row => (
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
    </div>
  );
}
