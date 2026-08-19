/**
 * Congress Trading Dashboard — Congressional stock trades from Quiver Quantitative.
 * Displays recent trades, politician activity, and ticker analytics.
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
  IconButton,
  InputAdornment,
  Pagination,
  Paper,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  ArrowDownward as ArrowDownwardIcon,
  ArrowUpward as ArrowUpwardIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  TrendingUp as TrendingUpIcon,
  AccountBalance as AccountBalanceIcon,
  HowToVote as HowToVoteIcon,
  AttachMoney as AttachMoneyIcon,
} from '@mui/icons-material';
import { useDomain } from '@/contexts/DomainContext';
import { politicsApi } from '@/services/api/politics';
import Logger from '@/utils/logger';

type TimeRange = '7d' | '30d' | '90d' | '1y';
type SortField = 'filed_date' | 'politician' | 'ticker' | 'amount' | 'transaction';
type SortOrder = 'asc' | 'desc';

const DAYS_MAP: Record<TimeRange, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
  '1y': 365,
};

type CongressTrade = {
  id: number;
  trade_id: string;
  ticker: string;
  company_name: string;
  politician_name: string;
  politician_bioguide_id: string | null;
  chamber: string;
  party: string;
  state: string;
  transaction_type: string;
  amount_range: string;
  traded_date: string | null;
  filed_date: string;
  owner_type: string | null;
};

type PoliticianSummary = {
  politician_name: string;
  politician_bioguide_id: string | null;
  chamber: string;
  party: string;
  state: string;
  total_trades: number;
  unique_tickers: number;
  first_trade_date: string;
  latest_trade_date: string;
  purchases: number;
  sales: number;
  exchanges: number;
};

type TickerActivity = {
  ticker: string;
  company_name: string;
  total_trades: number;
  unique_politicians: number;
  unique_politicians_id: number;
  purchases: number;
  sales: number;
  latest_trade_date: string;
};

type DashboardTab = 'trades' | 'politicians' | 'tickers';

const PARTY_COLORS: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  Democrat: 'primary',
  Republican: 'error',
  Independent: 'warning',
};

const TRANSACTION_COLORS: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  Purchase: 'success',
  Sale: 'error',
  Exchange: 'warning',
  'Partial Sale': 'error',
};

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatAmount(amount: string | null | undefined): string {
  if (!amount) return '—';
  return amount;
}

function StatusChip({ label, color }: { label: string; color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' }) {
  return <Chip size="small" label={label} color={color} variant="outlined" />;
}

function TransactionIcon({ type }: { type: string }) {
  const isPurchase = type.toLowerCase().includes('purchase');
  const isSale = type.toLowerCase().includes('sale');
  return isPurchase ? (
    <ArrowUpwardIcon fontSize="small" color="success" />
  ) : isSale ? (
    <ArrowDownwardIcon fontSize="small" color="error" />
  ) : (
    <AttachMoneyIcon fontSize="small" color="warning" />
  );
}

export default function CongressTradingDashboard() {
  const { activeDomainKey } = useDomain();
  const [tab, setTab] = useState<DashboardTab>('trades');
  const [timeRange, setTimeRange] = useState<TimeRange>('30d');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('filed_date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [page, setPage] = useState(0);
  const [pageSize] = useState(25);
  const [loading, setLoading] = useState(false);
  const [trades, setTrades] = useState<CongressTrade[]>([]);
  const [totalTrades, setTotalTrades] = useState(0);
  const [politicians, setPoliticians] = useState<PoliticianSummary[]>([]);
  const [tickers, setTickers] = useState<TickerActivity[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Fetch trades
  const fetchTrades = useCallback(async () => {
    if (activeDomainKey !== 'politics') return;
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await politicsApi.getCongressTrades({
        days: DAYS_MAP[timeRange],
        politician: searchQuery || undefined,
        limit: pageSize,
        offset: page * pageSize,
      });
      
      if (result.success) {
        setTrades(result.data || []);
        setTotalTrades(result.pagination?.total || 0);
      } else {
        setError(result.error || 'Failed to fetch trades');
        setTrades([]);
        setTotalTrades(0);
      }
    } catch (err) {
      setError((err as Error).message);
      setTrades([]);
      setTotalTrades(0);
    } finally {
      setLoading(false);
    }
  }, [activeDomainKey, timeRange, searchQuery, page, pageSize]);

  // Fetch politician summaries
  const fetchPoliticians = useCallback(async () => {
    if (activeDomainKey !== 'politics') return;
    
    try {
      const result = await politicsApi.getTopPoliticians(DAYS_MAP[timeRange], 50);
      if (result.success) {
        setPoliticians(result.data || []);
      }
    } catch (err) {
      Logger.apiError('Failed to fetch politicians', err as Error);
    }
  }, [activeDomainKey, timeRange]);

  // Fetch ticker activity
  const fetchTickers = useCallback(async () => {
    if (activeDomainKey !== 'politics') return;
    
    try {
      const result = await politicsApi.getTopTickers(DAYS_MAP[timeRange], 50);
      if (result.success) {
        setTickers(result.data || []);
      }
    } catch (err) {
      Logger.apiError('Failed to fetch tickers', err as Error);
    }
  }, [activeDomainKey, timeRange]);

  // Load data on tab/timeRange change
  useEffect(() => {
    fetchTrades();
    fetchPoliticians();
    fetchTickers();
  }, [fetchTrades, fetchPoliticians, fetchTickers]);

  // Reset page when filters change
  useEffect(() => {
    setPage(0);
  }, [timeRange, searchQuery, sortField, sortOrder]);

  // Sort trades locally (since API doesn't support sort yet)
  const sortedTrades = useMemo(() => {
    return [...trades].sort((a, b) => {
      let aVal: any = a[sortField];
      let bVal: any = b[sortField];
      
      if (sortField === 'filed_date') {
        aVal = new Date(aVal).getTime();
        bVal = new Date(bVal).getTime();
      } else if (sortField === 'amount') {
        // Sort by amount range midpoint (rough)
        const parseAmount = (str: string) => {
          const nums = str?.match(/[\d,]+/g)?.map(n => parseInt(n.replace(/,/g, ''))) || [0];
          return (nums[0] + (nums[1] || nums[0])) / 2;
        };
        aVal = parseAmount(aVal);
        bVal = parseAmount(bVal);
      } else if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
      }
      
      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [trades, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return null;
    return sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />;
  };

  if (activeDomainKey !== 'politics') {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        This dashboard is only available in the Politics domain. Switch to the Politics domain to view congressional trading data.
      </Alert>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 2 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Congressional Trading Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Congressional stock trades sourced from Quiver Quantitative API. Updated every 6 hours via automated collector.
      </Typography>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Tab Navigation */}
      <Tabs value={tab} onChange={(_, v) => setTab(v as DashboardTab)} sx={{ mb: 2 }}>
        <Tab label="Recent Trades" icon={<TrendingUpIcon />} value="trades" />
        <Tab label="Top Politicians" icon={<HowToVoteIcon />} value="politicians" />
        <Tab label="Top Tickers" icon={<AttachMoneyIcon />} value="tickers" />
      </Tabs>

      {/* Time Range & Search */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <ToggleButtonGroup
          value={timeRange}
          exclusive
          onChange={(_, v) => setTimeRange(v as TimeRange)}
          size="small"
          aria-label="Time range"
        >
          <ToggleButton value="7d">7 Days</ToggleButton>
          <ToggleButton value="30d">30 Days</ToggleButton>
          <ToggleButton value="90d">90 Days</ToggleButton>
          <ToggleButton value="1y">1 Year</ToggleButton>
        </ToggleButtonGroup>

        <Box sx={{ flexGrow: 1, maxWidth: 300 }}>
          <TextField
            size="small"
            placeholder="Search politician or ticker..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start"><SearchIcon /></InputAdornment>
              ),
            }}
            sx={{ width: '100%' }}
          />
        </Box>

        <Tooltip title="Refresh data">
          <IconButton onClick={fetchTrades} disabled={loading} color="primary">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Content by Tab */}
      {tab === 'trades' && (
        <>
          {loading && <Box sx={{ py: 4, textAlign: 'center' }}>
            <Skeleton variant="rectangular" height={200} width="100%" animation="wave" />
          </Box>}

          {!loading && (
            <Card>
              <CardHeader 
                title="Congressional Trades" 
                subheader={`${totalTrades} total trades in the last ${timeRange === '7d' ? '7 days' : timeRange === '30d' ? '30 days' : timeRange === '90d' ? '90 days' : 'year'}`}
              />
              <TableContainer sx={{ maxHeight: 600 }}>
                <Table stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: 120 }}>
                        <Tooltip title="Click to sort by filed date">
                          <Typography variant="body2" fontWeight={600} onClick={() => handleSort('filed_date')} style={{ cursor: 'pointer' }}>
                            Filed Date {getSortIcon('filed_date')}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ width: 80 }}>
                        <Tooltip title="Click to sort by ticker">
                          <Typography variant="body2" fontWeight={600} onClick={() => handleSort('ticker')} style={{ cursor: 'pointer' }}>
                            Ticker {getSortIcon('ticker')}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ width: 150 }}>
                        <Tooltip title="Click to sort by politician">
                          <Typography variant="body2" fontWeight={600} onClick={() => handleSort('politician')} style={{ cursor: 'pointer' }}>
                            Politician {getSortIcon('politician')}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ width: 80 }}>
                        <Tooltip title="Click to sort by transaction type">
                          <Typography variant="body2" fontWeight={600} onClick={() => handleSort('transaction')} style={{ cursor: 'pointer' }}>
                            Type {getSortIcon('transaction')}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ width: 120 }}>
                        <Tooltip title="Click to sort by amount">
                          <Typography variant="body2" fontWeight={600} onClick={() => handleSort('amount')} style={{ cursor: 'pointer' }}>
                            Amount {getSortIcon('amount')}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ width: 100 }}>Chamber</TableCell>
                      <TableCell sx={{ width: 100 }}>Party</TableCell>
                      <TableCell>Owner</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sortedTrades.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                          No trades found matching your criteria.
                        </TableCell>
                      </TableRow>
                    ) : (
                      sortedTrades.map((trade) => (
                        <TableRow key={trade.id} hover>
                          <TableCell>{formatDate(trade.filed_date)}</TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight={600}>{trade.ticker}</Typography>
                            <Typography variant="caption" color="text.secondary">{trade.company_name?.substring(0, 30)}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{trade.politician_name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {trade.chamber} • {trade.state}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <TransactionIcon type={trade.transaction_type} />
                              <Typography variant="body2" fontWeight={500}>
                                {trade.transaction_type}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <StatusChip 
                              label={formatAmount(trade.amount_range)} 
                              color={TRANSACTION_COLORS[trade.transaction_type] || 'default'} 
                            />
                          </TableCell>
                          <TableCell>
                            <Chip 
                              size="small" 
                              label={trade.chamber} 
                              icon={trade.chamber === 'Senate' ? <AccountBalanceIcon fontSize="small" /> : <HowToVoteIcon fontSize="small" />}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <StatusChip 
                              label={trade.party} 
                              color={PARTY_COLORS[trade.party] || 'default'} 
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {trade.owner_type || '—'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>

              {/* Pagination */}
              {totalTrades > pageSize && (
                <Pagination
                  count={Math.ceil(totalTrades / pageSize)}
                  page={page + 1}
                  onChange={(_, v) => setPage(v - 1)}
                  color="primary"
                  showFirstButton
                  showLastButton
                  boundaryCount={1}
                  siblingCount={1}
                />
              )}
            </Card>
          )}
        </>
      )}

      {tab === 'politicians' && (
        <Card>
          <CardHeader 
            title="Most Active Congressional Traders" 
            subheader={timeRange === '7d' ? 'Last 7 days' : timeRange === '30d' ? 'Last 30 days' : timeRange === '90d' ? 'Last 90 days' : 'Last year'}
          />
          <TableContainer sx={{ maxHeight: 600 }}>
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Rank</TableCell>
                  <TableCell>Politician</TableCell>
                  <TableCell>Chamber</TableCell>
                  <TableCell>Party</TableCell>
                  <TableCell>State</TableCell>
                  <TableCell align="right">Total Trades</TableCell>
                  <TableCell align="right">Unique Tickers</TableCell>
                  <TableCell align="right">Purchases</TableCell>
                  <TableCell align="right">Sales</TableCell>
                  <TableCell>Latest Trade</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {politicians.map((pol, idx) => (
                  <TableRow key={pol.politician_bioguide_id || pol.politician_name} hover>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>{pol.politician_name}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={pol.chamber} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <StatusChip label={pol.party} color={PARTY_COLORS[pol.party] || 'default'} />
                    </TableCell>
                    <TableCell>{pol.state}</TableCell>
                    <TableCell align="right" fontWeight={600}>{pol.total_trades}</TableCell>
                    <TableCell align="right">{pol.unique_tickers}</TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" color="success">{pol.purchases}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" color="error">{pol.sales}</Typography>
                    </TableCell>
                    <TableCell>{formatDate(pol.latest_trade_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}

      {tab === 'tickers' && (
        <Card>
          <CardHeader 
            title="Most Traded Stocks by Congress" 
            subheader={timeRange === '7d' ? 'Last 7 days' : timeRange === '30d' ? 'Last 30 days' : timeRange === '90d' ? 'Last 90 days' : 'Last year'}
          />
          <TableContainer sx={{ maxHeight: 600 }}>
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Rank</TableCell>
                  <TableCell>Ticker</TableCell>
                  <TableCell>Company</TableCell>
                  <TableCell align="right">Total Trades</TableCell>
                  <TableCell align="right">Unique Politicians</TableCell>
                  <TableCell align="right">Purchases</TableCell>
                  <TableCell align="right">Sales</TableCell>
                  <TableCell>Latest Trade</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tickers.map((ticker, idx) => (
                  <TableRow key={ticker.ticker} hover>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight={700}>{ticker.ticker}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{ticker.company_name}</Typography>
                    </TableCell>
                    <TableCell align="right" fontWeight={600}>{ticker.total_trades}</TableCell>
                    <TableCell align="right">{ticker.unique_politicians}</TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" color="success">{ticker.purchases}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" color="error">{ticker.sales}</Typography>
                    </TableCell>
                    <TableCell>{formatDate(ticker.latest_trade_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}
    </Box>
  );
}