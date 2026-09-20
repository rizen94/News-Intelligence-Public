/**
 * USD Purchasing Power tracker — product-home under /finance/trackers.
 * Adapted from classic Finance page; reuses GET .../usd-purchasing-power-tracker.
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Paper,
  Button,
} from '@mui/material';
import { getApi } from '../../../services/api/client';

type TrackerSeries = {
  value?: number;
  label?: string;
  change_1d?: number;
  change_7d?: number;
  change_30d?: number;
  status?: string;
};

type TrackerData = {
  last_updated?: string;
  series?: Record<string, TrackerSeries>;
};

export default function UsdPurchasingPowerPage() {
  const [data, setData] = useState<TrackerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const load = async (refresh = false) => {
    const url = `/api/finance/finance/usd-purchasing-power-tracker`;
    try {
      setLoading(true);
      setError(null);
      const response = await getApi().get(url, {
        params: refresh ? { refresh: true } : undefined,
      });
      setData(response.data?.data ?? null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(true);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={36} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ color: 'error.main', py: 2 }}>
        <Typography variant='h6'>Error loading data</Typography>
        <Typography>{error.message}</Typography>
        <Button sx={{ mt: 1 }} onClick={() => void load(true)}>
          Retry
        </Button>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ py: 2 }}>
        <Typography variant='h6'>No data available</Typography>
        <Typography color='text.secondary' sx={{ mb: 1 }}>
          Set FRED_API_KEY on the API host, then refresh.
        </Typography>
        <Button onClick={() => void load(true)}>Refresh from FRED</Button>
      </Box>
    );
  }

  const fmtPct = (v?: number) =>
    v === undefined || v === null ? 'N/A' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;

  return (
    <div>
      <h1 className='finance-page-title'>USD purchasing power</h1>
      <p className='finance-page-lede'>
        CPI-based purchasing power (PDOLLAR), dollar strength, and gold — FRED-backed market
        health tracker.
      </p>
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, mb: 1 }}>
          <Typography variant='body2' color='text.secondary'>
            Last updated:{' '}
            {data.last_updated
              ? new Date(data.last_updated).toLocaleString()
              : 'N/A'}
          </Typography>
          <Button size='small' onClick={() => void load(true)}>
            Refresh
          </Button>
        </Box>
        <Box sx={{ overflowX: 'auto' }}>
          <Table size='small'>
            <TableHead>
              <TableRow>
                <TableCell>Metric</TableCell>
                <TableCell align='right'>Current Value</TableCell>
                <TableCell align='right'>1D Change</TableCell>
                <TableCell align='right'>7D Change</TableCell>
                <TableCell align='right'>30D Change</TableCell>
                <TableCell align='center'>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(data.series || {}).map(([key, value]) => (
                <TableRow key={key}>
                  <TableCell>
                    <Typography variant='body1' fontWeight='medium'>
                      {value.label || key}
                    </Typography>
                  </TableCell>
                  <TableCell align='right'>
                    {value.value !== undefined ? value.value.toFixed(2) : 'N/A'}
                  </TableCell>
                  <TableCell align='right'>{fmtPct(value.change_1d)}</TableCell>
                  <TableCell align='right'>{fmtPct(value.change_7d)}</TableCell>
                  <TableCell align='right'>{fmtPct(value.change_30d)}</TableCell>
                  <TableCell align='center'>{value.status}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
        <Typography variant='caption' color='text.secondary' display='block' sx={{ mt: 1.5 }}>
          Data source: Federal Reserve Economic Data (FRED) API
        </Typography>
      </Paper>
    </div>
  );
}
