/**
 * Commodity Intelligence — one dashboard for gold, silver, platinum.
 * Data switches by selected commodity (URL param :commodity). Same view, different data.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Typography,
  Grid,
  Skeleton,
  Chip,
  ToggleButtonGroup,
  ToggleButton,
  List,
  ListItemButton,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useDomain } from '@/contexts/DomainContext';
import { monitoringApi } from '@/services/api/monitoring';
import GoldChoropleth, { type GeoEvent } from '@/components/charts/GoldChoropleth';

export type CommoditySlug = 'gold' | 'silver' | 'platinum';

const COMMODITIES: { id: CommoditySlug; label: string }[] = [
  { id: 'gold', label: 'Gold' },
  { id: 'silver', label: 'Silver' },
  { id: 'platinum', label: 'Platinum' },
];

const COMMODITY_COLORS: Record<CommoditySlug, string> = {
  gold: '#b8860b',
  silver: '#c0c0c0',
  platinum: '#e5e4e2',
};

const EVENT_TYPE_COLORS: Record<string, 'error' | 'warning' | 'info' | 'success' | 'default'> = {
  conflict: 'error',
  disaster: 'error',
  economic: 'warning',
  election: 'info',
  legislation: 'info',
  diplomatic: 'success',
  investigation: 'default',
  policy: 'default',
  appointment: 'default',
};

type TimeRange = '30d' | '90d' | '1y' | '5y';
const DAYS_MAP: Record<TimeRange, number> = { '30d': 30, '90d': 90, '1y': 365, '5y': 365 * 5 };

function isValidCommodity(s: string): s is CommoditySlug {
  return s === 'gold' || s === 'silver' || s === 'platinum';
}

export default function CommodityDashboard() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const { commodity: commodityParam } = useParams<{ commodity: string }>();
  const commodity: CommoditySlug = isValidCommodity(commodityParam ?? '') ? commodityParam! : 'gold';

  const [timeRange, setTimeRange] = useState<TimeRange>('90d');
  const [history, setHistory] = useState<{ date: string; value: number }[]>([]);
  const [spot, setSpot] = useState<{
    price?: number;
    unit?: string;
    change?: number;
    change_percent?: number;
    high?: number;
    low?: number;
  } | null>(null);
  const [authority, setAuthority] = useState<Record<string, { rates?: Record<string, number>; timestamp?: string }>>({});
  const [geoEvents, setGeoEvents] = useState<{ events: GeoEvent[]; by_region: Record<string, number[]> }>({
    events: [],
    by_region: {},
  });
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [selectedEventIds, setSelectedEventIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    if (domain !== 'finance') return;
    setLoading(true);
    const days = DAYS_MAP[timeRange];
    try {
      const [histRes, spotRes, authRes, geoRes] = await Promise.all([
        monitoringApi.getCommodityHistory(commodity, { days, fetch_if_empty: true }, domain),
        monitoringApi.getCommoditySpot(commodity, domain),
        monitoringApi.getCommodityAuthority(commodity, {}, domain),
        monitoringApi.getCommodityGeoEvents({ limit: 50 }, domain),
      ]);
      const obs = (histRes?.data?.observations ?? []) as { date: string; value: number }[];
      setHistory(obs);
      setSpot(spotRes?.data ?? null);
      setAuthority((authRes?.data as Record<string, { rates?: Record<string, number>; timestamp?: string }>) ?? {});
      setGeoEvents({
        events: (geoRes?.data?.events ?? []) as GeoEvent[],
        by_region: (geoRes?.data?.by_region ?? {}) as Record<string, number[]>,
      });
    } finally {
      setLoading(false);
    }
  }, [domain, commodity, timeRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCommodityChange = (_: React.MouseEvent<HTMLElement>, value: CommoditySlug | null) => {
    if (value) navigate(`/${domain}/commodity/${value}`);
  };

  const handleCountryClick = useCallback((countryName: string, eventIds: number[]) => {
    setSelectedCountry(countryName);
    setSelectedEventIds(eventIds);
  }, []);

  const filteredEvents =
    selectedEventIds.length ? geoEvents.events.filter((e) => selectedEventIds.includes(e.id)) : geoEvents.events;
  const chartColor = COMMODITY_COLORS[commodity];
  const commodityLabel = COMMODITIES.find((c) => c.id === commodity)?.label ?? commodity;

  if (domain !== 'finance') {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="text.secondary">Commodity view is available only in the Finance domain.</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Commodity intelligence
        </Typography>
        <ToggleButtonGroup
          value={commodity}
          exclusive
          onChange={handleCommodityChange}
          size="small"
          aria-label="Select commodity"
        >
          {COMMODITIES.map((c) => (
            <ToggleButton key={c.id} value={c.id} aria-label={c.label}>
              {c.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {/* Section A: Price overview */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={8}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardHeader
              title={`${commodityLabel} price history`}
              action={
                <ToggleButtonGroup
                  size="small"
                  value={timeRange}
                  exclusive
                  onChange={(_, v) => v != null && setTimeRange(v)}
                >
                  <ToggleButton value="30d">30d</ToggleButton>
                  <ToggleButton value="90d">90d</ToggleButton>
                  <ToggleButton value="1y">1y</ToggleButton>
                  <ToggleButton value="5y">5y</ToggleButton>
                </ToggleButtonGroup>
              }
            />
            <CardContent sx={{ pt: 0 }}>
              {loading ? (
                <Skeleton variant="rectangular" height={280} sx={{ borderRadius: 1 }} />
              ) : history.length === 0 ? (
                <Typography color="text.secondary">
                  No price history. Trigger a fetch or add METALS_DEV_API_KEY for {commodityLabel}.
                </Typography>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={history} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="commodityGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={chartColor} stopOpacity={0.4} />
                        <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                    <Tooltip formatter={(v: number) => [`${v?.toFixed(2)} USD/oz`, 'Price']} />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={chartColor}
                      fill="url(#commodityGrad)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardHeader title={`${commodityLabel} spot`} />
            <CardContent>
              {loading ? (
                <Skeleton variant="text" width="60%" />
              ) : spot?.price != null ? (
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main' }}>
                    ${spot.price.toFixed(2)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {spot.unit ?? 'USD/oz'}
                  </Typography>
                  {(spot.change != null || spot.change_percent != null) && (
                    <Chip
                      size="small"
                      label={
                        spot.change_percent != null
                          ? `${spot.change_percent >= 0 ? '+' : ''}${spot.change_percent.toFixed(2)}%`
                          : spot.change != null
                            ? `${spot.change >= 0 ? '+' : ''}${spot.change}`
                            : ''
                      }
                      color={spot.change_percent != null ? (spot.change_percent >= 0 ? 'success' : 'error') : 'default'}
                      sx={{ ml: 1, mt: 0.5 }}
                    />
                  )}
                  {(spot.high != null || spot.low != null) && (
                    <Typography variant="caption" display="block" sx={{ mt: 1 }} color="text.secondary">
                      H: ${spot.high?.toFixed(2)} L: ${spot.low?.toFixed(2)}
                    </Typography>
                  )}
                </Box>
              ) : (
                <Typography color="text.secondary">No spot data.</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Section B: Choropleth */}
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardHeader title="Geographic intelligence" subheader="Event density by region" />
        <CardContent>
          {selectedCountry && (
            <Chip
              label={`Filter: ${selectedCountry}`}
              onDelete={() => {
                setSelectedCountry(null);
                setSelectedEventIds([]);
              }}
              size="small"
              sx={{ mb: 1 }}
            />
          )}
          <GoldChoropleth
            events={geoEvents.events}
            byRegion={geoEvents.by_region}
            onCountryClick={handleCountryClick}
            width={Math.min(960, typeof window !== 'undefined' ? window.innerWidth - 48 : 960)}
            height={400}
          />
          {Object.keys(authority).length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
              {Object.entries(authority).map(([auth, data]) => (
                <Chip
                  key={auth}
                  size="small"
                  variant="outlined"
                  label={`${auth.toUpperCase()}: ${data?.rates ? Object.values(data.rates)[0]?.toFixed(2) ?? '—' : '—'}`}
                />
              ))}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Section C: Event timeline */}
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardHeader title="Event timeline" subheader="Tracked events (finance)" />
        <CardContent>
          {loading ? (
            <Skeleton variant="rectangular" height={120} />
          ) : filteredEvents.length === 0 ? (
            <Typography color="text.secondary">No events yet.</Typography>
          ) : (
            <List dense>
              {filteredEvents.slice(0, 15).map((e, i) => (
                <React.Fragment key={e.id}>
                  <ListItemButton onClick={() => navigate(`/${domain}/investigate/events/${e.id}`)}>
                    <ListItemText
                      primary={e.event_name || `Event #${e.id}`}
                      secondary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                          <Chip
                            label={e.event_type ?? '—'}
                            size="small"
                            color={EVENT_TYPE_COLORS[e.event_type ?? ''] ?? 'default'}
                            variant="outlined"
                          />
                          {e.geographic_scope && (
                            <Typography variant="caption" color="text.secondary">
                              {e.geographic_scope}
                            </Typography>
                          )}
                          {e.start_date && (
                            <Typography variant="caption" color="text.disabled">
                              {new Date(e.start_date).toLocaleDateString(undefined, {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })}
                            </Typography>
                          )}
                        </Box>
                      }
                      primaryTypographyProps={{ fontWeight: 600 }}
                    />
                  </ListItemButton>
                  {i < filteredEvents.length - 1 && <Divider component="li" />}
                </React.Fragment>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Section D: Intel panels */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Card variant="outlined">
            <CardHeader title="Global market" subheader="Spot & authority comparison" />
            <CardContent>
              {spot?.price != null && (
                <Typography variant="body2">
                  Latest: ${spot.price.toFixed(2)} {spot.unit ?? 'USD/oz'}
                </Typography>
              )}
              {Object.keys(authority).length > 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  LBMA / MCX / IBJA regional prices available above.
                </Typography>
              )}
              {!spot?.price && Object.keys(authority).length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No global data yet.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant="outlined">
            <CardHeader title="National & regulatory" subheader="Country-level events" />
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Events with geographic scope appear in the map and timeline. Select a country on the map to filter.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant="outlined">
            <CardHeader title="Industrial & supply chain" subheader="EDGAR, mining, logistics" />
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Mining company filings and supply-chain contexts will appear here as the pipeline ingests EDGAR and
                commodity-related articles.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
