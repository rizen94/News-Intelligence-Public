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
} from '@mui/material';
import { getApi, getCurrentDomain } from '../../services/api/client';

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

const UsdPurchasingPowerTracker: React.FC = () => {
  const [data, setData] = useState<TrackerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const domain = getCurrentDomain() || 'finance';
      const url = `/api/${domain}/finance/usd-purchasing-power-tracker`;
      try {
        setLoading(true);
        setError(null);
        const response = await getApi().get(url);
        if (!cancelled) {
          setData(response.data?.data ?? null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
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
      <Box sx={{ color: 'error.main', textAlign: 'center', py: 4 }}>
        <Typography variant="h6">Error loading data</Typography>
        <Typography>{error.message}</Typography>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="h6">No data available</Typography>
      </Box>
    );
  }

  const fmtPct = (v?: number) =>
    v === undefined || v === null
      ? 'N/A'
      : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;

  return (
    <Paper sx={{ p: 3, mt: 2 }}>
      <Typography variant="h5" gutterBottom>
        USD Purchasing Power Tracker
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Last updated:{' '}
        {data.last_updated
          ? new Date(data.last_updated).toLocaleString()
          : 'N/A'}
      </Typography>
      <Box sx={{ mt: 2, overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Metric</TableCell>
              <TableCell align="right">Current Value</TableCell>
              <TableCell align="right">1D Change</TableCell>
              <TableCell align="right">7D Change</TableCell>
              <TableCell align="right">30D Change</TableCell>
              <TableCell align="center">Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {Object.entries(data.series || {}).map(([key, value]) => (
              <TableRow key={key}>
                <TableCell>
                  <Typography variant="body1" fontWeight="medium">
                    {value.label || key}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  {value.value !== undefined ? value.value.toFixed(2) : 'N/A'}
                </TableCell>
                <TableCell align="right">{fmtPct(value.change_1d)}</TableCell>
                <TableCell align="right">{fmtPct(value.change_7d)}</TableCell>
                <TableCell align="right">{fmtPct(value.change_30d)}</TableCell>
                <TableCell align="center">
                  <Typography
                    variant="body2"
                    color={
                      value.status === '🟢'
                        ? 'success.main'
                        : value.status === '🔴'
                          ? 'error.main'
                          : 'warning.main'
                    }
                  >
                    {value.status}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
      <Box sx={{ mt: 2, padding: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Data source: Federal Reserve Economic Data (FRED) API | Updated daily
          at 6:00 AM ET
        </Typography>
      </Box>
    </Paper>
  );
};

export default UsdPurchasingPowerTracker;
