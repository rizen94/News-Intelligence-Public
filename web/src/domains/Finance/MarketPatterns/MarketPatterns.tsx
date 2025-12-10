/**
 * Market Patterns Page
 * Finance domain - Pattern detection, correlation analysis, trend analysis
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
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  ShowChart,
  TrendingUp,
  TrendingDown,
  Refresh,
  ExpandMore,
  Analytics,
  Psychology,
} from '@mui/icons-material';
import { apiService } from '../../../services/apiService';
import { useDomainRoute } from '../../../hooks/useDomainRoute';

const MarketPatterns: React.FC = () => {
  const { domain } = useDomainRoute();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [patterns, setPatterns] = useState<any[]>([]);
  const [filters, setFilters] = useState({
    patternType: 'all',
    company: '',
    minConfidence: 0.7,
    startDate: '',
    endDate: '',
  });

  const loadPatterns = useCallback(async () => {
    if (domain !== 'finance') {
      setError('This page is only available for the Finance domain');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const response = await apiService.getMarketPatterns({
        ...filters,
        patternType: filters.patternType !== 'all' ? filters.patternType : undefined,
        minConfidence: filters.minConfidence,
      }, domain);

      if (response.success) {
        setPatterns(response.data?.patterns || []);
      } else {
        setError(response.error || 'Failed to load market patterns');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading market patterns');
    } finally {
      setLoading(false);
    }
  }, [domain, filters]);

  useEffect(() => {
    loadPatterns();
  }, [loadPatterns]);

  const handleFilterChange = (field: string, value: any) => {
    setFilters(prev => ({ ...prev, [field]: value }));
  };

  if (domain !== 'finance') {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">
          Market Patterns is only available in the Finance domain.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ShowChart /> Market Pattern Analysis
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadPatterns}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth>
              <InputLabel>Pattern Type</InputLabel>
              <Select
                value={filters.patternType}
                onChange={(e) => handleFilterChange('patternType', e.target.value)}
                label="Pattern Type"
              >
                <MenuItem value="all">All Types</MenuItem>
                <MenuItem value="price_trend">Price Trend</MenuItem>
                <MenuItem value="volume_spike">Volume Spike</MenuItem>
                <MenuItem value="correlation">Correlation</MenuItem>
                <MenuItem value="sentiment_shift">Sentiment Shift</MenuItem>
                <MenuItem value="momentum">Momentum</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              label="Company"
              value={filters.company}
              onChange={(e) => handleFilterChange('company', e.target.value)}
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              label="Min Confidence"
              type="number"
              value={filters.minConfidence}
              onChange={(e) => handleFilterChange('minConfidence', parseFloat(e.target.value) || 0)}
              size="small"
              inputProps={{ min: 0, max: 1, step: 0.1 }}
            />
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
          <Box sx={{ mb: 2 }}>
            <Chip 
              label="API Endpoint: /api/v4/finance/finance/market-patterns" 
              color="info" 
              size="small" 
            />
          </Box>

          {patterns.length === 0 ? (
            <Alert severity="info">
              No market patterns found. The backend API endpoint needs to be implemented.
            </Alert>
          ) : (
            <Grid container spacing={3}>
              {patterns.map((pattern: any) => (
                <Grid item xs={12} key={pattern.id}>
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                        <Chip 
                          label={pattern.pattern_type || 'Unknown'} 
                          color="primary" 
                          variant="outlined"
                        />
                        <Typography variant="h6" sx={{ flexGrow: 1 }}>
                          {pattern.pattern_name || 'Unnamed Pattern'}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <Chip
                            label={`${(pattern.confidence_score * 100).toFixed(0)}% confidence`}
                            size="small"
                            color={pattern.confidence_score >= 0.8 ? 'success' : 'default'}
                          />
                          {pattern.market_impact && (
                            <Chip
                              label={`${pattern.market_impact > 0 ? '+' : ''}${pattern.market_impact.toFixed(2)}% impact`}
                              size="small"
                              color={pattern.market_impact >= 0 ? 'success' : 'error'}
                              icon={pattern.market_impact >= 0 ? <TrendingUp /> : <TrendingDown />}
                            />
                          )}
                        </Box>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Grid container spacing={2}>
                        <Grid item xs={12} md={6}>
                          <Typography variant="subtitle2" gutterBottom>
                            Description
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {pattern.description || 'No description available'}
                          </Typography>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <Typography variant="subtitle2" gutterBottom>
                            Details
                          </Typography>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                            <Typography variant="body2">
                              <strong>Detected:</strong>{' '}
                              {pattern.detected_at 
                                ? new Date(pattern.detected_at).toLocaleString()
                                : 'N/A'}
                            </Typography>
                            <Typography variant="body2">
                              <strong>Duration:</strong> {pattern.pattern_duration_days || 0} days
                            </Typography>
                            <Typography variant="body2">
                              <strong>Strength:</strong> {(pattern.pattern_strength * 100).toFixed(0)}%
                            </Typography>
                            {pattern.affected_companies && pattern.affected_companies.length > 0 && (
                              <Box>
                                <Typography variant="body2" gutterBottom>
                                  <strong>Affected Companies:</strong>
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                  {pattern.affected_companies.map((company: string, idx: number) => (
                                    <Chip key={idx} label={company} size="small" />
                                  ))}
                                </Box>
                              </Box>
                            )}
                          </Box>
                        </Grid>
                        {pattern.predicted_outcome && (
                          <Grid item xs={12}>
                            <Card variant="outlined" sx={{ bgcolor: 'action.hover' }}>
                              <CardContent>
                                <Typography variant="subtitle2" gutterBottom>
                                  <Psychology fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                                  AI Prediction
                                </Typography>
                                <Typography variant="body2">
                                  {pattern.predicted_outcome}
                                </Typography>
                              </CardContent>
                            </Card>
                          </Grid>
                        )}
                      </Grid>
                    </AccordionDetails>
                  </Accordion>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}
    </Box>
  );
};

export default MarketPatterns;



