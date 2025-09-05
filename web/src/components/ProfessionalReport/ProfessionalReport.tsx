import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  LinearProgress,
  Alert,
  Paper,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid
} from '@mui/material';
import {
  ExpandMore,
  Article,
  Psychology,
  TrendingUp,
  Source,
  Schedule,
  CheckCircle,
  Warning,
  Error,
  Download,
  Share,
  Refresh
} from '@mui/icons-material';

interface ProfessionalReportProps {
  storyId?: string;
  onReportGenerated?: (report: any) => void;
}

interface ReportData {
  id: number;
  story_id: string;
  title: string;
  executive_summary: string;
  key_findings: string[];
  timeline_summary: string;
  sources: Array<{
    title: string;
    url: string;
    publication_date: string;
    credibility_score: number;
  }>;
  sentiment_analysis: {
    overall_sentiment: string;
    confidence: number;
    breakdown: Record<string, number>;
  };
  impact_assessment: {
    level: string;
    factors: string[];
    potential_outcomes: string[];
  };
  generated_at: string;
  version: string;
}

const ProfessionalReport: React.FC<ProfessionalReportProps> = ({ storyId, onReportGenerated }) => {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const generateReport = async () => {
    setGenerating(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/ai/generate-report/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          story_id: storyId || 'default',
          report_type: 'professional',
          include_analysis: true,
          include_timeline: true,
          include_sources: true
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setReport(data.data);
        onReportGenerated?.(data.data);
      } else {
        setError(data.message || 'Failed to generate report');
      }
    } catch (err) {
      setError('Failed to connect to AI processing service');
      console.error('Error generating report:', err);
    } finally {
      setGenerating(false);
    }
  };

  const loadExistingReport = async () => {
    if (!storyId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`http://localhost:8000/api/stories/reports/${storyId}/`);
      const data = await response.json();
      
      if (data.success) {
        setReport(data.data);
      } else {
        setError(data.message || 'No existing report found');
      }
    } catch (err) {
      setError('Failed to load existing report');
      console.error('Error loading report:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (storyId) {
      loadExistingReport();
    }
  }, [storyId]);

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment.toLowerCase()) {
      case 'positive': return 'success';
      case 'negative': return 'error';
      case 'neutral': return 'default';
      case 'mixed': return 'warning';
      default: return 'default';
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact.toLowerCase()) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleDownload = () => {
    if (!report) return;
    
    const reportText = `
PROFESSIONAL JOURNALISTIC REPORT
${report.title}

Generated: ${formatDate(report.generated_at)}
Version: ${report.version}

EXECUTIVE SUMMARY
${report.executive_summary}

KEY FINDINGS
${report.key_findings.map((finding, index) => `${index + 1}. ${finding}`).join('\n')}

TIMELINE SUMMARY
${report.timeline_summary}

SENTIMENT ANALYSIS
Overall Sentiment: ${report.sentiment_analysis.overall_sentiment}
Confidence: ${Math.round(report.sentiment_analysis.confidence * 100)}%

IMPACT ASSESSMENT
Level: ${report.impact_assessment.level}
Factors: ${report.impact_assessment.factors.join(', ')}

SOURCES
${report.sources.map((source, index) => 
  `${index + 1}. ${source.title} (${formatDate(source.publication_date)}) - Credibility: ${Math.round(source.credibility_score * 100)}%`
).join('\n')}
    `.trim();
    
    const blob = new Blob([reportText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${report.story_id}-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleShare = () => {
    if (!report) return;
    
    if (navigator.share) {
      navigator.share({
        title: report.title,
        text: report.executive_summary,
        url: window.location.href
      });
    } else {
      navigator.clipboard.writeText(window.location.href);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Article sx={{ mr: 1 }} />
            <Typography variant="h6">Professional Report</Typography>
          </Box>
          <LinearProgress />
          <Typography variant="body2" sx={{ mt: 1 }}>
            Loading report...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error && !report) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Article sx={{ mr: 1 }} />
            <Typography variant="h6">Professional Report</Typography>
          </Box>
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
          <Button variant="outlined" onClick={generateReport} disabled={generating}>
            {generating ? 'Generating...' : 'Generate Report'}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box>
      {/* Report Header */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Article sx={{ mr: 1 }} />
              <Typography variant="h6">Professional Report</Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={generateReport}
                disabled={generating}
                size="small"
              >
                {generating ? 'Generating...' : 'Regenerate'}
              </Button>
              {report && (
                <>
                  <Button
                    variant="outlined"
                    startIcon={<Download />}
                    onClick={handleDownload}
                    size="small"
                  >
                    Download
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Share />}
                    onClick={handleShare}
                    size="small"
                  >
                    Share
                  </Button>
                </>
              )}
            </Box>
          </Box>
          
          {generating && (
            <Box sx={{ mb: 2 }}>
              <LinearProgress />
              <Typography variant="body2" sx={{ mt: 1 }}>
                Generating professional report... This may take a few moments.
              </Typography>
            </Box>
          )}
          
          {!report && !generating && (
            <Alert severity="info" sx={{ mb: 2 }}>
              No report available. Click "Generate Report" to create a professional journalistic report.
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Report Content */}
      {report && (
        <Box>
          {/* Executive Summary */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Executive Summary
              </Typography>
              <Typography variant="body1" sx={{ lineHeight: 1.8 }}>
                {report.executive_summary}
              </Typography>
            </CardContent>
          </Card>

          {/* Key Findings */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Key Findings
              </Typography>
              <List>
                {report.key_findings.map((finding, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <CheckCircle color="primary" />
                    </ListItemIcon>
                    <ListItemText primary={finding} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>

          {/* Analysis Grid */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            {/* Sentiment Analysis */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Psychology sx={{ mr: 1 }} />
                    <Typography variant="h6">Sentiment Analysis</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Chip
                      label={report.sentiment_analysis.overall_sentiment}
                      color={getSentimentColor(report.sentiment_analysis.overall_sentiment)}
                      size="small"
                    />
                    <Typography variant="body2" color="text.secondary">
                      {Math.round(report.sentiment_analysis.confidence * 100)}% confidence
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Breakdown: {Object.entries(report.sentiment_analysis.breakdown)
                      .map(([key, value]) => `${key}: ${Math.round(value * 100)}%`)
                      .join(', ')}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* Impact Assessment */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <TrendingUp sx={{ mr: 1 }} />
                    <Typography variant="h6">Impact Assessment</Typography>
                  </Box>
                  <Chip
                    label={report.impact_assessment.level}
                    color={getImpactColor(report.impact_assessment.level)}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    <strong>Factors:</strong> {report.impact_assessment.factors.join(', ')}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    <strong>Potential Outcomes:</strong> {report.impact_assessment.potential_outcomes.join(', ')}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Timeline Summary */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Schedule sx={{ mr: 1 }} />
                <Typography variant="h6">Timeline Summary</Typography>
              </Box>
              <Typography variant="body1" sx={{ lineHeight: 1.8 }}>
                {report.timeline_summary}
              </Typography>
            </CardContent>
          </Card>

          {/* Sources */}
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Source sx={{ mr: 1 }} />
                <Typography variant="h6">Sources</Typography>
              </Box>
              <List>
                {report.sources.map((source, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>
                            {source.title}
                          </Typography>
                          <Chip
                            label={`${Math.round(source.credibility_score * 100)}% credible`}
                            size="small"
                            color={source.credibility_score > 0.8 ? 'success' : source.credibility_score > 0.6 ? 'warning' : 'error'}
                          />
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            Published: {formatDate(source.publication_date)}
                          </Typography>
                          {source.url && (
                            <Typography variant="caption" color="primary">
                              <a href={source.url} target="_blank" rel="noopener noreferrer">
                                View Source
                              </a>
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>

          {/* Report Metadata */}
          <Paper sx={{ p: 2, mt: 3, bgcolor: 'grey.50' }}>
            <Typography variant="caption" color="text.secondary">
              Report generated on {formatDate(report.generated_at)} | Version {report.version}
            </Typography>
          </Paper>
        </Box>
      )}
    </Box>
  );
};

export default ProfessionalReport;