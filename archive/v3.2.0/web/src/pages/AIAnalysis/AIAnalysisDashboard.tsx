/**
 * AI Analysis Dashboard v3.0
 * Comprehensive AI-powered analysis interface
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Tabs,
  Tab,
  Chip,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
  Paper,
  Divider,
} from '@mui/material';
import {
  Psychology as PsychologyIcon,
  TrendingUp as TrendingUpIcon,
  Group as GroupIcon,
  Assessment as AssessmentIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Share as ShareIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { sentimentService, entityService } from '../../services';
import SentimentDisplay from '../../components/SentimentAnalysis/SentimentDisplay';
import EntityDisplay from '../../components/EntityAnalysis/EntityDisplay';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`ai-tabpanel-${index}`}
      aria-labelledby={`ai-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const AIAnalysisDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [inputText, setInputText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Sample analysis data for demonstration
  const [sampleData] = useState({
    sentiment: {
      sentiment_score: 0.65,
      confidence: 0.87,
      emotions: {
        joy: 0.3,
        anger: 0.1,
        fear: 0.05,
        sadness: 0.1,
        surprise: 0.15,
        disgust: 0.05,
        neutral: 0.25
      },
      context: "The text expresses optimism and positive outlook with some excitement about future possibilities.",
      model_used: "llama3.1:8b",
      processing_time: 1.2,
      local_processing: true
    },
    entities: [
      {
        text: "Apple Inc.",
        label: "ORGANIZATION",
        confidence: 0.95,
        start_pos: 0,
        end_pos: 9,
        context: "Apple Inc. has announced new products",
        model_used: "llama3.1:8b",
        local_processing: true
      },
      {
        text: "iPhone",
        label: "PRODUCT",
        confidence: 0.90,
        start_pos: 25,
        end_pos: 31,
        context: "new iPhone with advanced features",
        model_used: "llama3.1:8b",
        local_processing: true
      },
      {
        text: "California",
        label: "LOCATION",
        confidence: 0.88,
        start_pos: 45,
        end_pos: 55,
        context: "headquarters in California",
        model_used: "llama3.1:8b",
        local_processing: true
      }
    ],
    readability: {
      flesch_reading_ease: 75.2,
      flesch_kincaid_grade: 8.5,
      gunning_fog: 12.1,
      smog_index: 10.8,
      automated_readability_index: 9.2,
      coleman_liau_index: 11.3,
      average_grade_level: 10.4,
      reading_time_minutes: 2.3,
      word_count: 45,
      sentence_count: 3,
      syllable_count: 67,
      character_count: 280
    },
    quality: {
      overall_quality_score: 0.85,
      clarity_score: 0.90,
      coherence_score: 0.88,
      completeness_score: 0.82,
      accuracy_score: 0.87,
      engagement_score: 0.79,
      bias_score: 0.15,
      factual_consistency: 0.92,
      source_reliability: 0.88,
      writing_style: "professional",
      content_type: "news_article",
      target_audience: "general_public",
      recommendations: [
        "Consider adding more specific examples",
        "Improve paragraph structure for better flow",
        "Add more engaging opening sentence"
      ],
      model_used: "llama3.1:8b",
      processing_time: 2.1,
      local_processing: true
    }
  });

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleAnalyze = async () => {
    if (!inputText.trim()) {
      setError('Please enter text to analyze');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      // Simulate API calls (replace with actual API calls)
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // For now, use sample data
      setAnalysisResults(sampleData);
    } catch (err) {
      setError('Analysis failed. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleClear = () => {
    setInputText('');
    setAnalysisResults(null);
    setError(null);
  };

  const getReadabilityLabel = (score: number) => {
    if (score >= 90) return 'Very Easy';
    if (score >= 80) return 'Easy';
    if (score >= 70) return 'Fairly Easy';
    if (score >= 60) return 'Standard';
    if (score >= 50) return 'Fairly Difficult';
    if (score >= 30) return 'Difficult';
    return 'Very Difficult';
  };

  const getReadabilityColor = (score: number) => {
    if (score >= 70) return 'success';
    if (score >= 50) return 'warning';
    return 'error';
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          AI Analysis Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Comprehensive AI-powered analysis of your content using local machine learning models.
        </Typography>

        {/* Input Section */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Analyze Text
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Enter text to analyze for sentiment, entities, readability, and quality..."
            variant="outlined"
            sx={{ mb: 2 }}
          />
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              onClick={handleAnalyze}
              disabled={isAnalyzing || !inputText.trim()}
              startIcon={<PsychologyIcon />}
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze Text'}
            </Button>
            <Button
              variant="outlined"
              onClick={handleClear}
              disabled={isAnalyzing}
            >
              Clear
            </Button>
            {analysisResults && (
              <>
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                >
                  Export Results
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<ShareIcon />}
                >
                  Share Analysis
                </Button>
              </>
            )}
          </Box>
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
              AI is analyzing your text using local models...
            </Typography>
          </Box>
        )}
      </Box>

      {/* Analysis Results */}
      {analysisResults && (
        <Box>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            aria-label="AI analysis tabs"
            sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}
          >
            <Tab
              icon={<PsychologyIcon />}
              label="Sentiment Analysis"
              iconPosition="start"
            />
            <Tab
              icon={<GroupIcon />}
              label="Entity Extraction"
              iconPosition="start"
            />
            <Tab
              icon={<AssessmentIcon />}
              label="Readability & Quality"
              iconPosition="start"
            />
            <Tab
              icon={<TrendingUpIcon />}
              label="Summary"
              iconPosition="start"
            />
          </Tabs>

          {/* Sentiment Analysis Tab */}
          <TabPanel value={activeTab} index={0}>
            <SentimentDisplay
              analysis={analysisResults.sentiment}
              showDetails={true}
            />
          </TabPanel>

          {/* Entity Extraction Tab */}
          <TabPanel value={activeTab} index={1}>
            <EntityDisplay
              entities={analysisResults.entities}
              text={inputText}
              showDetails={true}
            />
          </TabPanel>

          {/* Readability & Quality Tab */}
          <TabPanel value={activeTab} index={2}>
            <Grid container spacing={3}>
              {/* Readability Metrics */}
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Readability Metrics
                    </Typography>
                    
                    <Box sx={{ mb: 3 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2">Flesch Reading Ease</Typography>
                        <Chip
                          label={getReadabilityLabel(analysisResults.readability.flesch_reading_ease)}
                          color={getReadabilityColor(analysisResults.readability.flesch_reading_ease)}
                          size="small"
                        />
                      </Box>
                      <Typography variant="h4" color="primary">
                        {analysisResults.readability.flesch_reading_ease.toFixed(1)}
                      </Typography>
                    </Box>

                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="primary">
                            {analysisResults.readability.average_grade_level.toFixed(1)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Grade Level
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={6}>
                        <Box textAlign="center">
                          <Typography variant="h6" color="primary">
                            {analysisResults.readability.reading_time_minutes.toFixed(1)}m
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Reading Time
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>

                    <Divider sx={{ my: 2 }} />

                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Text Statistics
                      </Typography>
                      <Grid container spacing={1}>
                        <Grid item xs={6}>
                          <Typography variant="caption">
                            Words: {analysisResults.readability.word_count}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption">
                            Sentences: {analysisResults.readability.sentence_count}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption">
                            Syllables: {analysisResults.readability.syllable_count}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption">
                            Characters: {analysisResults.readability.character_count}
                          </Typography>
                        </Grid>
                      </Grid>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* Quality Metrics */}
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Quality Analysis
                    </Typography>
                    
                    <Box sx={{ mb: 3 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2">Overall Quality</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {(analysisResults.quality.overall_quality_score * 100).toFixed(1)}%
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={analysisResults.quality.overall_quality_score * 100}
                        sx={{ height: 8, borderRadius: 4 }}
                      />
                    </Box>

                    <Grid container spacing={2}>
                      {[
                        { label: 'Clarity', value: analysisResults.quality.clarity_score },
                        { label: 'Coherence', value: analysisResults.quality.coherence_score },
                        { label: 'Completeness', value: analysisResults.quality.completeness_score },
                        { label: 'Accuracy', value: analysisResults.quality.accuracy_score },
                        { label: 'Engagement', value: analysisResults.quality.engagement_score },
                      ].map((metric) => (
                        <Grid item xs={6} key={metric.label}>
                          <Box>
                            <Typography variant="caption" color="text.secondary">
                              {metric.label}
                            </Typography>
                            <LinearProgress
                              variant="determinate"
                              value={metric.value * 100}
                              sx={{ height: 4, borderRadius: 2, mt: 0.5 }}
                            />
                            <Typography variant="caption" color="text.secondary">
                              {(metric.value * 100).toFixed(0)}%
                            </Typography>
                          </Box>
                        </Grid>
                      ))}
                    </Grid>

                    <Divider sx={{ my: 2 }} />

                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Content Classification
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                        <Chip label={analysisResults.quality.writing_style} size="small" />
                        <Chip label={analysisResults.quality.content_type} size="small" />
                        <Chip label={analysisResults.quality.target_audience} size="small" />
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* Recommendations */}
              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      AI Recommendations
                    </Typography>
                    {analysisResults.quality.recommendations.map((rec: string, index: number) => (
                      <Box key={index} sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="body2" sx={{ mr: 1 }}>
                          • {rec}
                        </Typography>
                      </Box>
                    ))}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </TabPanel>

          {/* Summary Tab */}
          <TabPanel value={activeTab} index={3}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Analysis Summary
                    </Typography>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Sentiment
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                          label={analysisResults.sentiment.sentiment_score > 0 ? 'Positive' : 'Negative'}
                          color={analysisResults.sentiment.sentiment_score > 0 ? 'success' : 'error'}
                          size="small"
                        />
                        <Typography variant="body2">
                          {(analysisResults.sentiment.sentiment_score * 100).toFixed(1)}% confidence
                        </Typography>
                      </Box>
                    </Box>
                    
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Entities Found
                      </Typography>
                      <Typography variant="body2">
                        {analysisResults.entities.length} entities detected
                      </Typography>
                    </Box>

                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Readability
                      </Typography>
                      <Typography variant="body2">
                        Grade {analysisResults.readability.average_grade_level.toFixed(1)} level
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Quality Score
                      </Typography>
                      <Typography variant="body2">
                        {(analysisResults.quality.overall_quality_score * 100).toFixed(1)}% overall quality
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Processing Details
                    </Typography>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Model Used: {analysisResults.sentiment.model_used}
                      </Typography>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Processing Time: {analysisResults.sentiment.processing_time}s
                      </Typography>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        Local Processing: {analysisResults.sentiment.local_processing ? 'Yes' : 'No'}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Analysis Date: {new Date().toLocaleString()}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </TabPanel>
        </Box>
      )}
    </Box>
  );
};

export default AIAnalysisDashboard;

