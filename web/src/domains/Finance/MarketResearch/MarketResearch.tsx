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
import { apiService } from '../../../services/apiService';
import { useDomainRoute } from '../../../hooks/useDomainRoute';

const MarketResearch: React.FC = () => {
  const { domain } = useDomainRoute();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marketTrends, setMarketTrends] = useState<any>(null);
  const [timeframe, setTimeframe] = useState('7d');
  const [sector, setSector] = useState('all');

  const loadMarketTrends = useCallback(async () => {
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

  useEffect(() => {
    loadMarketTrends();
  }, [loadMarketTrends]);

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
