/**
 * Market Research Page
 * Finance domain - Market trends, sector analysis, and company performance
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  LinearProgress,
  Alert,
  CircularProgress,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Button,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Analytics,
  BarChart,
  ShowChart,
  Refresh,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import apiService from '../../../services/apiService';
import { useDomainRoute } from '../../../hooks/useDomainRoute';

const MarketResearch: React.FC = () => {
  const { domain, getDomainPath } = useDomainRoute();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marketTrends, setMarketTrends] = useState<any>(null);
  const [dataSources, setDataSources] = useState<any>(null);
  const [marketData, setMarketData] = useState<any>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [fetchingSymbol, setFetchingSymbol] = useState<string | null>(null);
  const [goldData, setGoldData] = useState<any>(null);
  const [goldFetching, setGoldFetching] = useState(false);
  const [timeframe, setTimeframe] = useState('7d');
  const [sector, setSector] = useState('all');

  const loadMarketTrends = useCallback(async() => {
    if (domain !== 'finance') {
      setError('This page is only available for the Finance domain');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await apiService.getMarketTrends({
        timeframe,
        sector: sector !== 'all' ? sector : undefined,
      }, domain);

      if (response.success) {
        setMarketTrends(response.data);
      } else {
        setError(response.error || 'Failed to load market trends');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading market trends');
    } finally {
      setLoading(false);
    }
  }, [domain, timeframe, sector]);

  const loadDataSources = useCallback(async () => {
    if (domain !== 'finance') return;
    try {
      const res = await apiService.getFinanceDataSources(domain);
      if (res?.success && res?.data?.sources) setDataSources(res.data);
    } catch (_e) { /* ignore */ }
  }, [domain]);

  const loadMarketData = useCallback(async (sym?: string) => {
    if (domain !== 'finance') return;
    try {
      const res = await apiService.getFinanceMarketData(
        sym ? { source: 'fred', symbol: sym } : { source: 'fred' },
        domain,
      );
      if (res?.success && res?.data) setMarketData(res.data);
    } catch (_e) { /* ignore */ }
  }, [domain]);

  const doFetchFred = useCallback(async (symbol: string) => {
    if (!symbol || domain !== 'finance') return;
    setFetchingSymbol(symbol);
    try {
      const res = await apiService.triggerFredFetch({ symbol }, domain);
      if (res?.success) {
        await loadMarketData(symbol);
      }
    } finally {
      setFetchingSymbol(null);
    }
  }, [domain, loadMarketData]);

  useEffect(() => {
    loadMarketTrends();
  }, [loadMarketTrends]);

  useEffect(() => {
    loadDataSources();
  }, [loadDataSources]);

  useEffect(() => {
    loadMarketData(selectedSymbol || undefined);
  }, [loadMarketData, selectedSymbol]);

  const loadGoldData = useCallback(async (doFetch = false) => {
    if (domain !== 'finance') return;
    try {
      const res = await apiService.getGoldData({ fetch: doFetch }, domain);
      if (res?.success && res?.data) setGoldData(res.data);
    } catch (_e) { /* ignore */ }
  }, [domain]);

  const doFetchGold = useCallback(async () => {
    if (domain !== 'finance') return;
    setGoldFetching(true);
    try {
      const res = await apiService.triggerGoldFetch({}, domain);
      if (res?.success) await loadGoldData(false);
    } finally {
      setGoldFetching(false);
    }
  }, [domain, loadGoldData]);

  useEffect(() => {
    loadGoldData(false);
  }, [loadGoldData]);

  if (domain !== 'finance') {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">
          Market Research is only available in the Finance domain.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Analytics /> Market Research
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadMarketTrends}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Financial Analysis quick link */}
      <Card sx={{ mb: 3, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
            <Box>
              <Typography variant="h6">Financial Analysis</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>
                Ask questions about gold, commodities, or market data. Get cited analysis with evidence.
              </Typography>
            </Box>
            <Button
              variant="contained"
              color="inherit"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)' }}
              onClick={() => navigate(getDomainPath('/analysis'))}
            >
              Open Analysis
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={4}>
            <FormControl fullWidth>
              <InputLabel>Timeframe</InputLabel>
              <Select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                label="Timeframe"
              >
                <MenuItem value="1d">Last 24 Hours</MenuItem>
                <MenuItem value="7d">Last 7 Days</MenuItem>
                <MenuItem value="30d">Last 30 Days</MenuItem>
                <MenuItem value="90d">Last 90 Days</MenuItem>
                <MenuItem value="1y">Last Year</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <FormControl fullWidth>
              <InputLabel>Sector</InputLabel>
              <Select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                label="Sector"
              >
                <MenuItem value="all">All Sectors</MenuItem>
                <MenuItem value="technology">Technology</MenuItem>
                <MenuItem value="finance">Finance</MenuItem>
                <MenuItem value="healthcare">Healthcare</MenuItem>
                <MenuItem value="energy">Energy</MenuItem>
                <MenuItem value="consumer">Consumer</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {!loading && !error && (
        <Grid container spacing={3}>
          {/* Gold Amalgamator */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Gold — unified from multiple sources
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => loadGoldData(true)}
                    disabled={goldFetching}
                  >
                    Load
                  </Button>
                  <Button
                    variant="contained"
                    size="small"
                    onClick={doFetchGold}
                    disabled={goldFetching}
                  >
                    {goldFetching ? 'Fetching…' : 'Fetch all sources'}
                  </Button>
                  <Typography variant="caption" color="text.secondary">
                    Sources: FreeGoldAPI (USD/oz), FRED IQ12260 (index)
                  </Typography>
                </Box>
                {goldData?.observations?.length > 0 ? (
                  <Box>
                    <Typography variant="subtitle2">
                      {goldData.observations.length} observations (prefer {goldData.prefer_unit || 'USD/oz'})
                    </Typography>
                    <Box sx={{ maxHeight: 180, overflow: 'auto', mt: 1 }}>
                      {goldData.observations.slice(-15).reverse().map((o: any, i: number) => (
                        <Typography key={i} variant="body2" component="div">
                          {o.date}: {o.value != null ? Number(o.value).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'} {o.unit || ''}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No gold data. Click &quot;Fetch all sources&quot; to load.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Finance Data Sources (FRED) */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  <ShowChart /> Economic Data (FRED)
                </Typography>
                {dataSources?.sources?.length > 0 ? (
                  <Box>
                    {dataSources.sources.map((src: any) => (
                      <Box key={src.id} sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" color="text.secondary">{src.name}</Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                          {(src.symbols || []).map((sym: string) => (
                            <Chip
                              key={sym}
                              label={sym}
                              size="small"
                              variant={selectedSymbol === sym ? 'filled' : 'outlined'}
                              onClick={() => setSelectedSymbol(sym)}
                              onDelete={selectedSymbol === sym ? () => setSelectedSymbol('') : undefined}
                              sx={{ cursor: 'pointer' }}
                            />
                          ))}
                        </Box>
                      </Box>
                    ))}
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">No data sources configured.</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Fetch FRED & Stored Data */}
          {selectedSymbol && (
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>{selectedSymbol}</Typography>
                  <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Button
                      variant="contained"
                      size="small"
                      disabled={!!fetchingSymbol}
                      onClick={() => doFetchFred(selectedSymbol)}
                    >
                      {fetchingSymbol ? 'Fetching…' : 'Fetch from FRED'}
                    </Button>
                    <Typography variant="caption" color="text.secondary">
                      Requires FRED_API_KEY. Fetched data is stored locally.
                    </Typography>
                  </Box>
                  {marketData?.symbol === selectedSymbol ? (
                    marketData.observations?.length > 0 ? (
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="subtitle2">Stored observations: {marketData.observations.length}</Typography>
                        <Box sx={{ maxHeight: 200, overflow: 'auto', mt: 1 }}>
                          {marketData.observations.slice(-20).reverse().map((o: any, i: number) => (
                            <Typography key={i} variant="body2" component="div">
                              {o.date}: {o.value != null ? Number(o.value).toLocaleString() : '—'}
                            </Typography>
                          ))}
                        </Box>
                      </Box>
                    ) : (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        No observations in store. Click Fetch from FRED to load (requires FRED_API_KEY).
                      </Typography>
                    )
                  ) : null}
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Market Overview */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Market Overview
                </Typography>
                {marketTrends ? (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Market trends and analytics will be displayed here once the backend API is implemented.
                    </Typography>
                    <Box sx={{ mt: 2 }}>
                      <Chip label="API Endpoint: /api/v4/finance/finance/market-trends" color="info" size="small" />
                    </Box>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No market data available. The backend API endpoint needs to be implemented.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Sector Performance */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Sector Performance
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Sector analysis will be displayed here.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Company Performance */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Performers
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Company performance metrics will be displayed here.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default MarketResearch;
