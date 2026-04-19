/**
 * Commodity Intelligence — dashboard for registry commodities (gold, silver, platinum, oil, gas).
 * Commodity list from API; data switches by selected commodity (URL param :commodity).
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
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
  Button,
  FormControlLabel,
  Checkbox,
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
import Logger from '@/utils/logger';
import GoldChoropleth, {
  type GeoEvent,
  type MapOverlayFeatureCollection,
} from '@/components/charts/GoldChoropleth';

/** Fallback when API fails */
const COMMODITIES_FALLBACK: { id: string; label: string }[] = [
  { id: 'gold', label: 'Gold' },
  { id: 'silver', label: 'Silver' },
  { id: 'platinum', label: 'Platinum' },
];

const COMMODITY_COLORS: Record<string, string> = {
  gold: '#b8860b',
  silver: '#c0c0c0',
  platinum: '#e5e4e2',
  oil: '#2c3e50',
  gas: '#3498db',
};

/** Oil/gas use FRED only — not metals.dev */
const ENERGY_COMMODITIES = new Set(['oil', 'gas']);

function priceHistoryEmptyMessage(commodityId: string, label: string): string {
  if (ENERGY_COMMODITIES.has(commodityId)) {
    return `No price history from FRED for ${label}. Oil and gas use FRED only (not metals.dev). Set FRED_API_KEY. Defaults: WTI DCOILWTICO, Henry Hub DHHNGSP in commodity_registry.yaml — or set FRED_OIL_SERIES_ID / FRED_GAS_SERIES_ID.`;
  }
  return `No price history. Trigger a fetch or add METALS_DEV_API_KEY for ${label}.`;
}

const EVENT_TYPE_COLORS: Record<
  string,
  'error' | 'warning' | 'info' | 'success' | 'default'
> = {
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
const DAYS_MAP: Record<TimeRange, number> = {
  '30d': 30,
  '90d': 90,
  '1y': 365,
  '5y': 365 * 5,
};

export default function CommodityDashboard() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const { commodity: commodityParam } = useParams<{ commodity: string }>();

  const [commoditiesList, setCommoditiesList] =
    useState<{ id: string; label: string }[]>(COMMODITIES_FALLBACK);
  const [timeRange, setTimeRange] = useState<TimeRange>('90d');
  const [history, setHistory] = useState<
    { date: string; value: number; unit?: string }[]
  >([]);
  const [spot, setSpot] = useState<{
    price?: number;
    unit?: string;
    change?: number;
    change_percent?: number;
    high?: number;
    low?: number;
  } | null>(null);
  const [authority, setAuthority] = useState<
    Record<string, { rates?: Record<string, number>; timestamp?: string }>
  >({});
  const [geoEvents, setGeoEvents] = useState<{
    events: GeoEvent[];
    by_region: Record<string, number[]>;
  }>({
    events: [],
    by_region: {},
  });
  const [mapOverlays, setMapOverlays] = useState<MapOverlayFeatureCollection | null>(
    null
  );
  const [includeCrossDomainGeo, setIncludeCrossDomainGeo] = useState(true);
  const [includeMapOverlays, setIncludeMapOverlays] = useState(true);
  const [includeSupplyChainGeo, setIncludeSupplyChainGeo] = useState(false);
  const [contextLens, setContextLens] = useState<{
    lens_text: string;
    cited_event_ids: number[];
  } | null>(null);
  const [regulatoryEvents, setRegulatoryEvents] = useState<
    {
      id: number;
      event_type: string;
      event_name: string;
      start_date: string | null;
      geographic_scope: string | null;
    }[]
  >([]);
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [selectedEventIds, setSelectedEventIds] = useState<number[]>([]);
  const [newsItems, setNewsItems] = useState<
    {
      id: unknown;
      title: string;
      snippet: string;
      url: string;
      source: string;
      published_at: string;
    }[]
  >([]);
  const [supplyChainItems, setSupplyChainItems] = useState<
    {
      id: unknown;
      title: string;
      snippet: string;
      url: string;
      source: string;
      published_at: string;
    }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [fetchPricesBusy, setFetchPricesBusy] = useState(false);

  const commodity = (() => {
    const id = (commodityParam ?? '').toLowerCase();
    const valid = commoditiesList.some(c => c.id.toLowerCase() === id);
    return valid ? id : commoditiesList[0]?.id ?? 'gold';
  })();

  useEffect(() => {
    if (domain !== 'finance') return;
    monitoringApi.getCommodities(domain).then(res => {
      const list = (res?.data ?? []) as { id: string; label: string }[];
      if (Array.isArray(list) && list.length > 0) setCommoditiesList(list);
    });
  }, [domain]);

  useEffect(() => {
    if (
      domain === 'finance' &&
      commodityParam &&
      commodity !== (commodityParam ?? '').toLowerCase()
    ) {
      navigate(`/${domain}/commodity/${commodity}`, { replace: true });
    }
  }, [domain, commodity, commodityParam, navigate]);

  const loadData = useCallback(async () => {
    if (domain !== 'finance') return;
    setLoading(true);
    const days = DAYS_MAP[timeRange];
    try {
      const [histRes, spotRes, authRes, geoRes, regRes, newsRes, supplyRes, lensRes] =
        await Promise.all([
          monitoringApi.getCommodityHistory(
            commodity,
            { days, fetch_if_empty: true },
            domain
          ),
          monitoringApi.getCommoditySpot(commodity, domain),
          monitoringApi.getCommodityAuthority(commodity, {}, domain),
          monitoringApi.getCommodityGeoEvents(
            {
              limit: 50,
              commodity,
              include_cross_domain: includeCrossDomainGeo,
              include_map_overlays: includeMapOverlays,
              include_supply_chain_geo: includeSupplyChainGeo,
            },
            domain
          ),
          monitoringApi.getCommodityRegulatoryEvents(
            { limit: 15, commodity },
            domain
          ),
          monitoringApi.getCommodityNews(
            commodity,
            { hours: 168, max_items: 20 },
            domain
          ),
          monitoringApi.getCommoditySupplyChain(
            commodity,
            { hours: 168, max_items: 15 },
            domain
          ),
          monitoringApi.getCommodityContextLens(commodity, { limit: 6 }, domain),
        ]);
      const obs = (histRes?.data?.observations ?? []) as {
        date: string;
        value: number;
        unit?: string;
      }[];
      setHistory(obs);
      setSpot(spotRes?.data ?? null);
      setAuthority(
        (authRes?.data as Record<
          string,
          { rates?: Record<string, number>; timestamp?: string }
        >) ?? {}
      );
      const gdata = geoRes?.data as {
        events?: GeoEvent[];
        by_region?: Record<string, number[]>;
        map_overlays?: MapOverlayFeatureCollection;
      };
      setGeoEvents({
        events: (gdata?.events ?? []) as GeoEvent[],
        by_region: (gdata?.by_region ?? {}) as Record<string, number[]>,
      });
      setMapOverlays(
        includeMapOverlays && gdata?.map_overlays?.features?.length
          ? gdata.map_overlays
          : null
      );
      const lensData = lensRes?.data as {
        lens_text?: string;
        cited_event_ids?: number[];
      };
      if (lensData?.lens_text) {
        setContextLens({
          lens_text: lensData.lens_text,
          cited_event_ids: lensData.cited_event_ids ?? [],
        });
      } else {
        setContextLens(null);
      }
      setRegulatoryEvents(
        (regRes?.data?.events ?? []) as {
          id: number;
          event_type: string;
          event_name: string;
          start_date: string | null;
          geographic_scope: string | null;
        }[]
      );
      setNewsItems(
        (newsRes?.data?.items ?? []) as {
          id: unknown;
          title: string;
          snippet: string;
          url: string;
          source: string;
          published_at: string;
        }[]
      );
      setSupplyChainItems(
        (supplyRes?.data?.items ?? []) as {
          id: unknown;
          title: string;
          snippet: string;
          url: string;
          source: string;
          published_at: string;
        }[]
      );
    } finally {
      setLoading(false);
    }
  }, [
    domain,
    commodity,
    timeRange,
    includeCrossDomainGeo,
    includeMapOverlays,
    includeSupplyChainGeo,
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCommodityChange = (
    _: React.MouseEvent<HTMLElement>,
    value: string | null
  ) => {
    if (value) navigate(`/${domain}/commodity/${value}`);
  };

  const handleCountryClick = useCallback(
    (countryName: string, eventIds: number[]) => {
      setSelectedCountry(countryName);
      setSelectedEventIds(eventIds);
    },
    []
  );

  const filteredEvents = selectedEventIds.length
    ? geoEvents.events.filter(e => selectedEventIds.includes(e.id))
    : geoEvents.events;
  const chartColor = COMMODITY_COLORS[commodity] ?? '#666';
  const commodityLabel =
    commoditiesList.find(c => c.id.toLowerCase() === commodity)?.label ??
    commodity;

  const chartPriceUnit = useMemo(() => {
    const u = history.find(o => o.unit)?.unit ?? spot?.unit;
    if (u) return u;
    if (commodity === 'oil') return 'USD/bbl';
    if (commodity === 'gas') return 'USD/mmbtu';
    return 'USD/oz';
  }, [history, spot, commodity]);

  if (domain !== 'finance') {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color='text.secondary'>
          Commodity view is available only in the Finance domain.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 2,
          mb: 2,
        }}
      >
        <Typography variant='h5' sx={{ fontWeight: 600 }}>
          Commodity intelligence
        </Typography>
        <ToggleButtonGroup
          value={commodity}
          exclusive
          onChange={handleCommodityChange}
          size='small'
          aria-label='Select commodity'
        >
          {commoditiesList.map(c => (
            <ToggleButton key={c.id} value={c.id} aria-label={c.label}>
              {c.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {/* Section A: Price overview */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={8}>
          <Card variant='outlined' sx={{ height: '100%' }}>
            <CardHeader
              title={`${commodityLabel} price history`}
              action={
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flexWrap: 'wrap',
                    justifyContent: 'flex-end',
                  }}
                >
                  <Button
                    size='small'
                    variant='outlined'
                    disabled={fetchPricesBusy || loading}
                    onClick={async () => {
                      setFetchPricesBusy(true);
                      try {
                        const res = await monitoringApi.triggerCommodityPriceFetch(
                          commodity,
                          { days: 365 },
                          domain
                        );
                        if (!res?.success) {
                          Logger.warn('Commodity price fetch failed', {
                            error: res?.error ?? (res as { detail?: string })?.detail,
                          });
                        }
                        await loadData();
                      } finally {
                        setFetchPricesBusy(false);
                      }
                    }}
                  >
                    {fetchPricesBusy
                      ? 'Fetching…'
                      : ENERGY_COMMODITIES.has(commodity)
                      ? 'Fetch FRED prices'
                      : 'Refresh price store'}
                  </Button>
                  <ToggleButtonGroup
                    size='small'
                    value={timeRange}
                    exclusive
                    onChange={(_, v) => v != null && setTimeRange(v)}
                  >
                    <ToggleButton value='30d'>30d</ToggleButton>
                    <ToggleButton value='90d'>90d</ToggleButton>
                    <ToggleButton value='1y'>1y</ToggleButton>
                    <ToggleButton value='5y'>5y</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
              }
            />
            <CardContent sx={{ pt: 0 }}>
              {loading ? (
                <Skeleton
                  variant='rectangular'
                  height={280}
                  sx={{ borderRadius: 1 }}
                />
              ) : history.length === 0 ? (
                <Typography color='text.secondary'>
                  {priceHistoryEmptyMessage(commodity, commodityLabel)}
                </Typography>
              ) : (
                <ResponsiveContainer width='100%' height={280}>
                  <AreaChart
                    data={history}
                    margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id='commodityGrad'
                        x1='0'
                        y1='0'
                        x2='0'
                        y2='1'
                      >
                        <stop
                          offset='5%'
                          stopColor={chartColor}
                          stopOpacity={0.4}
                        />
                        <stop
                          offset='95%'
                          stopColor={chartColor}
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray='3 3' stroke='#eee' />
                    <XAxis dataKey='date' tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                    <Tooltip
                      formatter={(v: number) => [
                        `${v?.toFixed(2)} ${chartPriceUnit}`,
                        'Price',
                      ]}
                    />
                    <Area
                      type='monotone'
                      dataKey='value'
                      stroke={chartColor}
                      fill='url(#commodityGrad)'
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant='outlined' sx={{ height: '100%' }}>
            <CardHeader title={`${commodityLabel} spot`} />
            <CardContent>
              {loading ? (
                <Skeleton variant='text' width='60%' />
              ) : spot?.price != null ? (
                <Box>
                  <Typography
                    variant='h4'
                    sx={{ fontWeight: 700, color: 'primary.main' }}
                  >
                    ${spot.price.toFixed(2)}
                  </Typography>
                  <Typography variant='caption' color='text.secondary'>
                    {spot.unit ?? 'USD/oz'}
                  </Typography>
                  {(spot.change != null || spot.change_percent != null) && (
                    <Chip
                      size='small'
                      label={
                        spot.change_percent != null
                          ? `${
                              spot.change_percent >= 0 ? '+' : ''
                            }${spot.change_percent.toFixed(2)}%`
                          : spot.change != null
                          ? `${spot.change >= 0 ? '+' : ''}${spot.change}`
                          : ''
                      }
                      color={
                        spot.change_percent != null
                          ? spot.change_percent >= 0
                            ? 'success'
                            : 'error'
                          : 'default'
                      }
                      sx={{ ml: 1, mt: 0.5 }}
                    />
                  )}
                  {(spot.high != null || spot.low != null) && (
                    <Typography
                      variant='caption'
                      display='block'
                      sx={{ mt: 1 }}
                      color='text.secondary'
                    >
                      H: ${spot.high?.toFixed(2)} L: ${spot.low?.toFixed(2)}
                    </Typography>
                  )}
                </Box>
              ) : (
                <Typography color='text.secondary'>No spot data.</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Section B: Choropleth */}
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardHeader
          title='Geographic & logistics context'
          subheader={`Tracked events for ${commodityLabel} with mappable regions. Cross-domain rows are politics/AI items that match this commodity; map lines are reference routes only (not live vessels).`}
        />
        <CardContent>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 2,
              mb: 2,
              alignItems: 'center',
            }}
          >
            <FormControlLabel
              control={
                <Checkbox
                  checked={includeCrossDomainGeo}
                  onChange={(_, c) => setIncludeCrossDomainGeo(c)}
                  size='small'
                />
              }
              label='Cross-domain events'
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={includeMapOverlays}
                  onChange={(_, c) => setIncludeMapOverlays(c)}
                  size='small'
                />
              }
              label='Reference routes / chokepoints'
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={includeSupplyChainGeo}
                  onChange={(_, c) => setIncludeSupplyChainGeo(c)}
                  size='small'
                />
              }
              label='Supply-chain geo (broader match)'
            />
          </Box>
          {contextLens?.lens_text && (
            <Typography
              variant='body2'
              color='text.secondary'
              sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}
            >
              {contextLens.lens_text}
            </Typography>
          )}
          {!loading && geoEvents.events.length === 0 && (
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              No events passed the commodity filter with geographic scope in this
              window. The pipeline adds regions when it can infer them from finance
              contexts and tracked events.
            </Typography>
          )}
          {selectedCountry && (
            <Chip
              label={`Filter: ${selectedCountry}`}
              onDelete={() => {
                setSelectedCountry(null);
                setSelectedEventIds([]);
              }}
              size='small'
              sx={{ mb: 1 }}
            />
          )}
          <GoldChoropleth
            events={geoEvents.events}
            byRegion={geoEvents.by_region}
            onCountryClick={handleCountryClick}
            mapOverlays={mapOverlays}
            showOverlays={includeMapOverlays}
            width={Math.min(
              960,
              typeof window !== 'undefined' ? window.innerWidth - 48 : 960
            )}
            height={400}
          />
          {Object.keys(authority).length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
              {Object.entries(authority).map(([auth, data]) => (
                <Chip
                  key={auth}
                  size='small'
                  variant='outlined'
                  label={`${auth.toUpperCase()}: ${
                    data?.rates
                      ? Object.values(data.rates)[0]?.toFixed(2) ?? '—'
                      : '—'
                  }`}
                />
              ))}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Section C: Event timeline */}
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardHeader
          title='Event timeline'
          subheader='Finance-tagged and optional cross-domain rows for this commodity'
        />
        <CardContent>
          {loading ? (
            <Skeleton variant='rectangular' height={120} />
          ) : filteredEvents.length === 0 ? (
            <Typography color='text.secondary'>No events yet.</Typography>
          ) : (
            <List dense>
              {filteredEvents.slice(0, 15).map((e, i) => (
                <React.Fragment key={e.id}>
                  <ListItemButton
                    onClick={() =>
                      navigate(`/${domain}/investigate/events/${e.id}`)
                    }
                  >
                    <ListItemText
                      primary={e.event_name || `Event #${e.id}`}
                      secondary={
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            flexWrap: 'wrap',
                            mt: 0.5,
                          }}
                        >
                          <Chip
                            label={e.event_type ?? '—'}
                            size='small'
                            color={
                              EVENT_TYPE_COLORS[e.event_type ?? ''] ?? 'default'
                            }
                            variant='outlined'
                          />
                          {e.display_source === 'cross_domain' && (
                            <Chip
                              label='Cross-domain'
                              size='small'
                              color='secondary'
                              variant='filled'
                            />
                          )}
                          {e.geographic_scope && (
                            <Typography
                              variant='caption'
                              color='text.secondary'
                            >
                              {e.geographic_scope}
                            </Typography>
                          )}
                          {e.start_date && (
                            <Typography variant='caption' color='text.disabled'>
                              {new Date(e.start_date).toLocaleDateString(
                                undefined,
                                {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric',
                                }
                              )}
                            </Typography>
                          )}
                        </Box>
                      }
                      primaryTypographyProps={{ fontWeight: 600 }}
                    />
                  </ListItemButton>
                  {i < filteredEvents.length - 1 && <Divider component='li' />}
                </React.Fragment>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Section C2: Commodity news (financial relevance filter applied) */}
      <Card variant='outlined' sx={{ mb: 3 }}>
        <CardHeader
          title='News'
          subheader={`Financial news for ${commodityLabel} (market, trading, regulatory)`}
        />
        <CardContent>
          {loading ? (
            <Skeleton variant='rectangular' height={120} />
          ) : newsItems.length === 0 ? (
            <Typography color='text.secondary'>
              No financial news for {commodityLabel} in the selected period.
            </Typography>
          ) : (
            <List dense>
              {newsItems.slice(0, 15).map((item, i) => (
                <React.Fragment key={String((item as { id?: unknown }).id ?? i)}>
                  <ListItemButton
                    component='a'
                    href={item.url || '#'}
                    target='_blank'
                    rel='noopener noreferrer'
                    disableRipple={!item.url}
                  >
                    <ListItemText
                      primary={item.title || 'Untitled'}
                      secondary={
                        <Box sx={{ mt: 0.5 }}>
                          {item.snippet && (
                            <Typography
                              variant='body2'
                              color='text.secondary'
                              sx={{ display: 'block' }}
                            >
                              {item.snippet.slice(0, 200)}
                              {item.snippet.length > 200 ? '…' : ''}
                            </Typography>
                          )}
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              flexWrap: 'wrap',
                              mt: 0.5,
                            }}
                          >
                            {item.source && (
                              <Chip
                                size='small'
                                label={item.source}
                                variant='outlined'
                              />
                            )}
                            {item.published_at && (
                              <Typography
                                variant='caption'
                                color='text.disabled'
                              >
                                {new Date(item.published_at).toLocaleDateString(
                                  undefined,
                                  {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                  }
                                )}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      }
                      primaryTypographyProps={{ fontWeight: 600 }}
                    />
                  </ListItemButton>
                  {i < newsItems.length - 1 && <Divider component='li' />}
                </React.Fragment>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Section D: Intel panels */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Card variant='outlined'>
            <CardHeader
              title='Global market'
              subheader='Spot & authority comparison'
            />
            <CardContent>
              {spot?.price != null && (
                <Typography variant='body2'>
                  Latest: ${spot.price.toFixed(2)} {spot.unit ?? 'USD/oz'}
                </Typography>
              )}
              {Object.keys(authority).length > 0 && (
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 1 }}
                >
                  LBMA / MCX / IBJA regional prices available above.
                </Typography>
              )}
              {!spot?.price && Object.keys(authority).length === 0 && (
                <Typography variant='body2' color='text.secondary'>
                  No global data yet.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant='outlined'>
            <CardHeader
              title='National & regulatory'
              subheader='International regulatory and national announcements'
            />
            <CardContent>
              {loading ? (
                <Skeleton variant='text' height={24} sx={{ mb: 0.5 }} />
              ) : regulatoryEvents.length > 0 ? (
                <List dense disablePadding>
                  {regulatoryEvents.slice(0, 8).map(ev => (
                    <ListItemButton
                      key={String(ev.id)}
                      sx={{ py: 0.25, px: 0 }}
                      disableRipple
                    >
                      <ListItemText
                        primary={ev.event_name}
                        secondary={
                          ev.start_date
                            ? new Date(ev.start_date).toLocaleDateString()
                            : null
                        }
                        primaryTypographyProps={{
                          variant: 'body2',
                          noWrap: true,
                          title: ev.event_name,
                        }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                      {ev.event_type && ev.event_type !== 'other' && (
                        <Chip
                          size='small'
                          label={ev.event_type}
                          sx={{ ml: 0.5, flexShrink: 0 }}
                          color={EVENT_TYPE_COLORS[ev.event_type] ?? 'default'}
                        />
                      )}
                    </ListItemButton>
                  ))}
                </List>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  We watch major countries and trading hubs: central banks (Fed,
                  ECB, BoE, BoC, SNB), regulators, and national announcements.
                  Events appear here as the pipeline ingests finance RSS and
                  extracts regulatory/policy events; country-level events also
                  appear on the map.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant='outlined'>
            <CardHeader
              title='Industrial & supply chain'
              subheader='EDGAR, mining, logistics'
            />
            <CardContent>
              {loading ? (
                <Skeleton
                  variant='text'
                  width='90%'
                  height={24}
                  sx={{ mb: 0.5 }}
                />
              ) : supplyChainItems.length > 0 ? (
                <List dense disablePadding>
                  {supplyChainItems.slice(0, 8).map((item, i) => (
                    <ListItemButton
                      key={String((item as { id?: unknown }).id ?? i)}
                      sx={{ py: 0.25, px: 0 }}
                      disableRipple
                    >
                      <ListItemText
                        primary={item.title || 'Untitled'}
                        secondary={
                          item.published_at
                            ? new Date(item.published_at).toLocaleDateString(
                                undefined,
                                {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric',
                                }
                              )
                            : null
                        }
                        primaryTypographyProps={{
                          variant: 'body2',
                          noWrap: true,
                          title: item.title,
                        }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              ) : (
                <Typography variant='body2' color='text.secondary'>
                  Mining company filings and supply-chain contexts will appear
                  here as the pipeline ingests EDGAR and commodity-related
                  articles.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
