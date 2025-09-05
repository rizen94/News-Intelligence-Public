/**
 * Trends Analysis Page v3.0
 * Advanced trend detection and pattern analysis
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  LinearProgress,
  Alert,
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
  ShowChart as ShowChartIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Timeline as TimelineIcon,
  Psychology as PsychologyIcon,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

interface TrendData {
  timestamp: string;
  value: number;
  confidence: number;
}

interface TrendPattern {
  pattern_type: string;
  strength: number;
  duration_hours: number;
  start_time: string;
  end_time: string;
  peak_value: number;
  valley_value: number;
  volatility: number;
  description: string;
}

interface TrendAnalysis {
  trends: TrendPattern[];
  overall_trend: string;
  trend_strength: number;
  volatility_score: number;
  key_events: any[];
  predictions: any[];
  analysis_period: {
    start: string;
    end: string;
  };
  processing_time: number;
  model_used: string;
  local_processing: boolean;
}

const TrendsAnalysis: React.FC = () => {
  const [selectedMetric, setSelectedMetric] = useState('sentiment');
  const [timeWindow, setTimeWindow] = useState(24);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [trendAnalysis, setTrendAnalysis] = useState<TrendAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sample trend data for demonstration
  const [sampleTrendData] = useState<TrendData[]>([
    { timestamp: '2024-01-01T00:00:00Z', value: 0.2, confidence: 0.8 },
    { timestamp: '2024-01-01T06:00:00Z', value: 0.4, confidence: 0.85 },
    { timestamp: '2024-01-01T12:00:00Z', value: 0.6, confidence: 0.9 },
    { timestamp: '2024-01-01T18:00:00Z', value: 0.8, confidence: 0.88 },
    { timestamp: '2024-01-02T00:00:00Z', value: 0.7, confidence: 0.92 },
    { timestamp: '2024-01-02T06:00:00Z', value: 0.5, confidence: 0.87 },
    { timestamp: '2024-01-02T12:00:00Z', value: 0.3, confidence: 0.89 },
    { timestamp: '2024-01-02T18:00:00Z', value: 0.1, confidence: 0.91 },
  ]);

  const [sampleAnalysis] = useState<TrendAnalysis>({
    trends: [
      {
        pattern_type: 'rising',
        strength: 0.8,
        duration_hours: 18,
        start_time: '2024-01-01T00:00:00Z',
        end_time: '2024-01-01T18:00:00Z',
        peak_value: 0.8,
        valley_value: 0.2,
        volatility: 0.3,
        description: 'Strong upward trend in sentiment over 18 hours'
      },
      {
        pattern_type: 'falling',
        strength: 0.6,
        duration_hours: 18,
        start_time: '2024-01-01T18:00:00Z',
        end_time: '2024-01-02T12:00:00Z',
        peak_value: 0.8,
        valley_value: 0.1,
        volatility: 0.4,
        description: 'Moderate downward trend in sentiment'
      }
    ],
    overall_trend: 'volatile',
    trend_strength: 0.7,
    volatility_score: 0.6,
    key_events: [
      {
        type: 'high_engagement',
        timestamp: '2024-01-01T12:00:00Z',
        title: 'Breaking: Major Tech Announcement',
        description: 'High engagement: 0.95'
      },
      {
        type: 'extreme_sentiment',
        timestamp: '2024-01-01T18:00:00Z',
        title: 'Controversial Policy Update',
        description: 'Extreme sentiment: -0.8'
      }
    ],
    predictions: [
      {
        time_hours_ahead: 1,
        predicted_value: 0.15,
        confidence: 0.8,
        reasoning: 'Based on recent downward trend'
      },
      {
        time_hours_ahead: 3,
        predicted_value: 0.25,
        confidence: 0.6,
        reasoning: 'Trend continuation with some uncertainty'
      },
      {
        time_hours_ahead: 6,
        predicted_value: 0.35,
        confidence: 0.4,
        reasoning: 'Long-term projection with high uncertainty'
      }
    ],
    analysis_period: {
      start: '2024-01-01T00:00:00Z',
      end: '2024-01-02T18:00:00Z'
    },
    processing_time: 2.3,
    model_used: 'llama3.1:8b',
    local_processing: true
  });

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setError(null);

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      setTrendAnalysis(sampleAnalysis);
    } catch (err) {
      setError('Trend analysis failed. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getTrendIcon = (trendType: string) => {
    switch (trendType) {
      case 'rising': return <TrendingUpIcon color="success" />;
      case 'falling': return <TrendingDownIcon color="error" />;
      case 'stable': return <TrendingFlatIcon color="info" />;
      case 'volatile': return <ShowChartIcon color="warning" />;
      case 'cyclical': return <TimelineIcon color="primary" />;
      default: return <InfoIcon />;
    }
  };

  const getTrendColor = (trendType: string) => {
    switch (trendType) {
      case 'rising': return 'success';
      case 'falling': return 'error';
      case 'stable': return 'info';
      case 'volatile': return 'warning';
      case 'cyclical': return 'primary';
      default: return 'default';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Trend Analysis
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Advanced pattern detection and trend analysis using local AI models.
        </Typography>

        {/* Controls */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Metric to Analyze</InputLabel>
                <Select
                  value={selectedMetric}
                  onChange={(e) => setSelectedMetric(e.target.value)}
                  label="Metric to Analyze"
                >
                  <MenuItem value="sentiment">Sentiment Score</MenuItem>
                  <MenuItem value="engagement">Engagement Score</MenuItem>
                  <MenuItem value="volume">Article Volume</MenuItem>
                  <MenuItem value="quality">Quality Score</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Time Window</InputLabel>
                <Select
                  value={timeWindow}
                  onChange={(e) => setTimeWindow(e.target.value as number)}
                  label="Time Window"
                >
                  <MenuItem value={6}>6 Hours</MenuItem>
                  <MenuItem value={12}>12 Hours</MenuItem>
                  <MenuItem value={24}>24 Hours</MenuItem>
                  <MenuItem value={48}>48 Hours</MenuItem>
                  <MenuItem value={168}>1 Week</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Button
                variant="contained"
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                startIcon={<PsychologyIcon />}
                fullWidth
              >
                {isAnalyzing ? 'Analyzing...' : 'Analyze Trends'}
              </Button>
            </Grid>
          </Grid>
        </Paper>

        {/* Error Display */}
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Loading Indicator */}
        {isAnalyzing && (
          <Box sx={{ mb: 3 }}>
            <LinearProgress />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
              AI is analyzing trends using local models...
            </Typography>
          </Box>
        )}
      </Box>

      {/* Analysis Results */}
      {trendAnalysis && (
        <Grid container spacing={3}>
          {/* Overall Trend Summary */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Overall Trend Summary
                </Typography>
                <Grid container spacing={3} alignItems="center">
                  <Grid item xs={12} md={3}>
                    <Box textAlign="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 1 }}>
                        {getTrendIcon(trendAnalysis.overall_trend)}
                        <Typography variant="h5" sx={{ ml: 1, textTransform: 'capitalize' }}>
                          {trendAnalysis.overall_trend}
                        </Typography>
                      </Box>
                      <Chip
                        label={`${(trendAnalysis.trend_strength * 100).toFixed(1)}% Strength`}
                        color={getTrendColor(trendAnalysis.overall_trend)}
                        size="small"
                      />
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {trendAnalysis.volatility_score.toFixed(2)}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Volatility Score
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {trendAnalysis.trends.length}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Patterns Detected
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {trendAnalysis.processing_time.toFixed(1)}s
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Processing Time
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Trend Chart */}
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Trend Visualization
                </Typography>
                <Box sx={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sampleTrendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="timestamp" 
                        tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                      />
                      <YAxis />
                      <RechartsTooltip 
                        labelFormatter={(value) => new Date(value).toLocaleString()}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="value" 
                        stroke="#1976d2" 
                        strokeWidth={2}
                        dot={{ fill: '#1976d2', strokeWidth: 2, r: 4 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Predictions */}
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Predictions
                </Typography>
                {trendAnalysis.predictions.map((prediction, index) => (
                  <Box key={index} sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">
                        +{prediction.time_hours_ahead}h
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {(prediction.confidence * 100).toFixed(0)}% confidence
                      </Typography>
                    </Box>
                    <Typography variant="h6" color="primary">
                      {prediction.predicted_value.toFixed(2)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {prediction.reasoning}
                    </Typography>
                  </Box>
                ))}
              </CardContent>
            </Card>
          </Grid>

          {/* Detected Patterns */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Detected Patterns
                </Typography>
                <List>
                  {trendAnalysis.trends.map((trend, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        {getTrendIcon(trend.pattern_type)}
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                              {trend.pattern_type} Trend
                            </Typography>
                            <Chip
                              label={`${(trend.strength * 100).toFixed(0)}%`}
                              color={getTrendColor(trend.pattern_type)}
                              size="small"
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {trend.description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Duration: {trend.duration_hours.toFixed(1)}h | 
                              Range: {trend.valley_value.toFixed(2)} - {trend.peak_value.toFixed(2)}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>

          {/* Key Events */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Key Events
                </Typography>
                <List>
                  {trendAnalysis.key_events.map((event, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        <WarningIcon color="warning" />
                      </ListItemIcon>
                      <ListItemText
                        primary={event.title}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {event.description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatTimestamp(event.timestamp)}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>

          {/* Analysis Details */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Analysis Details
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Model Used
                    </Typography>
                    <Typography variant="body1">
                      {trendAnalysis.model_used}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Processing Time
                    </Typography>
                    <Typography variant="body1">
                      {trendAnalysis.processing_time.toFixed(2)}s
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Local Processing
                    </Typography>
                    <Typography variant="body1">
                      {trendAnalysis.local_processing ? 'Yes' : 'No'}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Analysis Period
                    </Typography>
                    <Typography variant="body1">
                      {formatTimestamp(trendAnalysis.analysis_period.start)} - {formatTimestamp(trendAnalysis.analysis_period.end)}
                    </Typography>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default TrendsAnalysis;


