/**
 * Corporate Announcements Page
 * Finance domain - Earnings reports, product launches, M&A, executive changes
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Business,
  TrendingUp,
  TrendingDown,
  Refresh,
  CalendarToday,
  Article,
  OpenInNew,
} from '@mui/icons-material';
import apiService from '../../../services/apiService';
import { useDomainRoute } from '../../../hooks/useDomainRoute';

const CorporateAnnouncements: React.FC = () => {
  const { domain } = useDomainRoute();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [announcements, setAnnouncements] = useState<any[]>([]);
  const [filters, setFilters] = useState({
    company: '',
    ticker: '',
    type: 'all',
    startDate: '',
    endDate: '',
  });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 20;

  const loadAnnouncements = useCallback(async() => {
    if (domain !== 'finance') {
      setError('This page is only available for the Finance domain');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await apiService.getCorporateAnnouncements({
        ...filters,
        limit,
        offset: (page - 1) * limit,
      }, domain);

      if (response.success) {
        setAnnouncements(response.data?.announcements || []);
        setTotal(response.data?.total || 0);
      } else {
        setError(response.error || 'Failed to load corporate announcements');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading corporate announcements');
    } finally {
      setLoading(false);
    }
  }, [domain, filters, page]);

  useEffect(() => {
    loadAnnouncements();
  }, [loadAnnouncements]);

  const handleFilterChange = (field: string, value: any) => {
    setFilters(prev => ({ ...prev, [field]: value }));
    setPage(1); // Reset to first page on filter change
  };

  if (domain !== 'finance') {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">
          Corporate Announcements is only available in the Finance domain.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Business /> Corporate Announcements
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadAnnouncements}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              label="Company Name"
              value={filters.company}
              onChange={(e) => handleFilterChange('company', e.target.value)}
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              label="Ticker Symbol"
              value={filters.ticker}
              onChange={(e) => handleFilterChange('ticker', e.target.value.toUpperCase())}
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
                label="Type"
              >
                <MenuItem value="all">All Types</MenuItem>
                <MenuItem value="earnings">Earnings</MenuItem>
                <MenuItem value="merger">Merger & Acquisition</MenuItem>
                <MenuItem value="product">Product Launch</MenuItem>
                <MenuItem value="executive">Executive Change</MenuItem>
                <MenuItem value="regulatory">Regulatory Filing</MenuItem>
                <MenuItem value="guidance">Guidance</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              label="Start Date"
              type="date"
              value={filters.startDate}
              onChange={(e) => handleFilterChange('startDate', e.target.value)}
              size="small"
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              label="End Date"
              type="date"
              value={filters.endDate}
              onChange={(e) => handleFilterChange('endDate', e.target.value)}
              size="small"
              InputLabelProps={{ shrink: true }}
            />
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
        <>
          <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              {total} announcement{total !== 1 ? 's' : ''} found
            </Typography>
            <Chip
              label="API Endpoint: /api/v4/finance/finance/corporate-announcements"
              color="info"
              size="small"
            />
          </Box>

          {announcements.length === 0 ? (
            <Alert severity="info">
              No corporate announcements found. The backend API endpoint needs to be implemented.
            </Alert>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Date</TableCell>
                    <TableCell>Company</TableCell>
                    <TableCell>Ticker</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Title</TableCell>
                    <TableCell>Sentiment</TableCell>
                    <TableCell>Market Impact</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {announcements.map((announcement: any) => (
                    <TableRow key={announcement.id}>
                      <TableCell>
                        {announcement.announcement_date
                          ? new Date(announcement.announcement_date).toLocaleDateString()
                          : 'N/A'}
                      </TableCell>
                      <TableCell>{announcement.company_name || 'N/A'}</TableCell>
                      <TableCell>
                        <Chip label={announcement.ticker_symbol || 'N/A'} size="small" />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={announcement.announcement_type || 'N/A'}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>{announcement.title || 'N/A'}</TableCell>
                      <TableCell>
                        {announcement.sentiment_label && (
                          <Chip
                            label={announcement.sentiment_label}
                            size="small"
                            color={
                              announcement.sentiment_label === 'positive' ? 'success' :
                                announcement.sentiment_label === 'negative' ? 'error' : 'default'
                            }
                          />
                        )}
                      </TableCell>
                      <TableCell>
                        {announcement.market_impact !== null && announcement.market_impact !== undefined ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            {announcement.market_impact >= 0 ? (
                              <TrendingUp color="success" fontSize="small" />
                            ) : (
                              <TrendingDown color="error" fontSize="small" />
                            )}
                            <Typography variant="body2">
                              {announcement.market_impact > 0 ? '+' : ''}
                              {announcement.market_impact.toFixed(2)}%
                            </Typography>
                          </Box>
                        ) : 'N/A'}
                      </TableCell>
                      <TableCell>
                        {announcement.source_url && (
                          <Tooltip title="View Source">
                            <IconButton
                              size="small"
                              href={announcement.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <OpenInNew fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}
    </Box>
  );
};

export default CorporateAnnouncements;

