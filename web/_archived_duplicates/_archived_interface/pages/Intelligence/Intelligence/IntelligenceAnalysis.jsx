import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  CircularProgress,
  Alert,
  Chip,
  Paper,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Tabs,
  Tab,
  TextField,
  IconButton,
  Tooltip,
  Badge,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Psychology as AIIcon,
  Assessment as QualityIcon,
  Warning as AnomalyIcon,
  TrendingUp as ImpactIcon,
  Search as SearchIcon,
  Refresh,
  ExpandMore,
  CheckCircle,
  Error as ErrorIcon,
  Info as InfoIcon,
  LocalFireDepartment,
  Article,
  Timeline,
  Visibility,
} from '@mui/icons-material';
import apiService from '../../services/apiService';

const IntelligenceAnalysis = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Dashboard state
  const [dashboard, setDashboard] = useState(null);

  // RAG state
  const [ragQuery, setRagQuery] = useState('');
  const [ragResult, setRagResult] = useState(null);
  const [ragLoading, setRagLoading] = useState(false);

  // Quality state
  const [qualityResults, setQualityResults] = useState(null);
  const [qualityLoading, setQualityLoading] = useState(false);

  // Anomaly state
  const [anomalies, setAnomalies] = useState(null);
  const [anomalyLoading, setAnomalyLoading] = useState(false);

  // Impact state
  const [highImpact, setHighImpact] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);

  const loadDashboard = useCallback(async() => {
    try {
      setLoading(true);
      const response = await apiService.getIntelligenceDashboard();
      if (response.success) {
        setDashboard(response);
      }
    } catch (err) {
      setError('Failed to load intelligence dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const handleRAGQuery = async() => {
    if (!ragQuery.trim()) return;
    try {
      setRagLoading(true);
      const response = await apiService.queryRAG(ragQuery);
      if (response.success) {
        setRagResult(response);
      }
    } catch (err) {
      setError('RAG query failed');
    } finally {
      setRagLoading(false);
    }
  };

  const loadQualityAssessment = async() => {
    try {
      setQualityLoading(true);
      const response = await apiService.getBatchQuality([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
      if (response.success) {
        setQualityResults(response);
      }
    } catch (err) {
      setError('Quality assessment failed');
    } finally {
      setQualityLoading(false);
    }
  };

  const loadAnomalies = async() => {
    try {
      setAnomalyLoading(true);
      const response = await apiService.getAnomalies(undefined, 20);
      if (response.success) {
        setAnomalies(response);
      }
    } catch (err) {
      setError('Anomaly detection failed');
    } finally {
      setAnomalyLoading(false);
    }
  };

  const loadHighImpact = async() => {
    try {
      setImpactLoading(true);
      const response = await apiService.getTrendingImpact(undefined, 15);
      if (response.success) {
        setHighImpact(response);
      }
    } catch (err) {
      setError('Impact assessment failed');
    } finally {
      setImpactLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 1 && !qualityResults) loadQualityAssessment();
    if (activeTab === 2 && !anomalies) loadAnomalies();
    if (activeTab === 3 && !highImpact) loadHighImpact();
  }, [activeTab, qualityResults, anomalies, highImpact]);

  const getGradeColor = (grade) => {
    switch (grade) {
    case 'A': return 'success';
    case 'B': return 'info';
    case 'C': return 'warning';
    case 'D': return 'warning';
    default: return 'error';
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
    case 'critical': return 'error';
    case 'high': return 'error';
    case 'medium': return 'warning';
    default: return 'info';
    }
  };

  const getImpactColor = (level) => {
    switch (level) {
    case 'critical': return 'error';
    case 'high': return 'warning';
    case 'medium': return 'info';
    default: return 'default';
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            <AIIcon color="primary" fontSize="large" />
            Intelligence Analysis
          </Typography>
          <Typography variant="body1" color="text.secondary">
            RAG-enhanced analysis, quality assessment, anomaly detection, and impact analysis
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadDashboard}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Dashboard Overview */}
      {dashboard && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="primary">
                  {dashboard.overview?.active_storylines || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Active Storylines
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="info.main">
                  {dashboard.overview?.articles_24h || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Articles (24h)
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="success.main">
                  {dashboard.overview?.active_sources || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Active Sources
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Chip
                  label={dashboard.health?.status || 'unknown'}
                  color={dashboard.health?.status === 'healthy' ? 'success' : 'warning'}
                  sx={{ fontSize: '1rem', height: 32 }}
                />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {dashboard.health?.anomaly_count || 0} anomalies
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, v) => setActiveTab(v)}
          variant="fullWidth"
        >
          <Tab icon={<SearchIcon />} label="RAG Context" />
          <Tab icon={<QualityIcon />} label="Quality Assessment" />
          <Tab icon={<AnomalyIcon />} label="Anomaly Detection" />
          <Tab icon={<ImpactIcon />} label="Impact Analysis" />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {activeTab === 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              <SearchIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              RAG-Enhanced Context Retrieval
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Query the knowledge base using semantic search to find relevant context
            </Typography>

            <Box display="flex" gap={2} sx={{ mb: 3 }}>
              <TextField
                fullWidth
                placeholder="Enter your query (e.g., 'climate change policy impacts')"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleRAGQuery()}
              />
              <Button
                variant="contained"
                onClick={handleRAGQuery}
                disabled={ragLoading || !ragQuery.trim()}
                startIcon={ragLoading ? <CircularProgress size={20} /> : <SearchIcon />}
              >
                Search
              </Button>
            </Box>

            {ragResult && (
              <Box>
                <Paper sx={{ p: 2, mb: 2, bgcolor: 'primary.50' }}>
                  <Typography variant="subtitle1" gutterBottom>Context Summary</Typography>
                  <Typography variant="body2">{ragResult.context?.summary}</Typography>
                </Paper>

                <Typography variant="subtitle1" gutterBottom>
                  Retrieved Articles ({ragResult.context?.retrieved_articles?.length || 0})
                </Typography>
                <List>
                  {(ragResult.context?.retrieved_articles || []).slice(0, 10).map((article, idx) => (
                    <ListItem key={idx} divider>
                      <ListItemIcon>
                        <Chip
                          label={`${(article.relevance * 100).toFixed(0)}%`}
                          size="small"
                          color="primary"
                        />
                      </ListItemIcon>
                      <ListItemText
                        primary={article.title}
                        secondary={`${article.source || article.source_domain || 'Unknown'} • ${article.published_at || article.published_date || ''}`}
                      />
                    </ListItem>
                  ))}
                </List>

                {ragResult.context?.related_entities?.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>Related Entities</Typography>
                    <Box display="flex" flexWrap="wrap" gap={1}>
                      {ragResult.context.related_entities.slice(0, 15).map((entity, idx) => (
                        <Chip key={idx} label={entity} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 1 && (
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">
                <QualityIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Storyline Quality Assessment
              </Typography>
              <Button
                variant="outlined"
                onClick={loadQualityAssessment}
                disabled={qualityLoading}
                startIcon={qualityLoading ? <CircularProgress size={20} /> : <Refresh />}
              >
                Refresh
              </Button>
            </Box>

            {qualityLoading && <LinearProgress sx={{ mb: 2 }} />}

            {qualityResults && (
              <>
                <Grid container spacing={2} sx={{ mb: 3 }}>
                  <Grid item xs={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4">{qualityResults.summary?.total_assessed || 0}</Typography>
                      <Typography variant="body2">Assessed</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4">{(qualityResults.summary?.avg_score * 100)?.toFixed(0) || 0}%</Typography>
                      <Typography variant="body2">Avg Score</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={4}>
                    <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'warning.50' }}>
                      <Typography variant="h4" color="warning.main">
                        {qualityResults.summary?.needs_attention || 0}
                      </Typography>
                      <Typography variant="body2">Need Attention</Typography>
                    </Paper>
                  </Grid>
                </Grid>

                <List>
                  {(qualityResults.assessments || []).map((a, idx) => (
                    <ListItem key={idx} divider>
                      <ListItemIcon>
                        <Chip
                          label={a.grade}
                          color={getGradeColor(a.grade)}
                          size="small"
                        />
                      </ListItemIcon>
                      <ListItemText
                        primary={`Storyline #${a.storyline_id}`}
                        secondary={`Score: ${(a.overall_score * 100).toFixed(0)}% • ${a.issues_count} issues`}
                      />
                      <Box>
                        <LinearProgress
                          variant="determinate"
                          value={a.overall_score * 100}
                          sx={{ width: 100 }}
                          color={a.overall_score >= 0.7 ? 'success' : a.overall_score >= 0.5 ? 'warning' : 'error'}
                        />
                      </Box>
                    </ListItem>
                  ))}
                </List>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 2 && (
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">
                <AnomalyIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Anomaly Detection
              </Typography>
              <Button
                variant="outlined"
                onClick={loadAnomalies}
                disabled={anomalyLoading}
                startIcon={anomalyLoading ? <CircularProgress size={20} /> : <Refresh />}
              >
                Refresh
              </Button>
            </Box>

            {anomalyLoading && <LinearProgress sx={{ mb: 2 }} />}

            {anomalies && (
              <>
                <Alert
                  severity={anomalies.requires_attention ? 'warning' : 'success'}
                  sx={{ mb: 2 }}
                >
                  {anomalies.requires_attention
                    ? `${anomalies.severity_breakdown?.critical + anomalies.severity_breakdown?.high} critical/high severity anomalies detected`
                    : 'No critical anomalies detected'}
                </Alert>

                <Grid container spacing={2} sx={{ mb: 3 }}>
                  {Object.entries(anomalies.severity_breakdown || {}).map(([severity, count]) => (
                    <Grid item xs={3} key={severity}>
                      <Paper sx={{ p: 2, textAlign: 'center' }}>
                        <Badge badgeContent={count} color={getSeverityColor(severity)}>
                          <Typography variant="subtitle1" sx={{ textTransform: 'capitalize' }}>
                            {severity}
                          </Typography>
                        </Badge>
                      </Paper>
                    </Grid>
                  ))}
                </Grid>

                {Object.entries(anomalies.anomalies_by_type || {}).map(([type, items]) => (
                  <Accordion key={type}>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <Typography sx={{ textTransform: 'capitalize' }}>
                        {type.replace(/_/g, ' ')} ({items.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense>
                        {items.map((item, idx) => (
                          <ListItem key={idx}>
                            <ListItemIcon>
                              <Chip
                                label={item.severity}
                                color={getSeverityColor(item.severity)}
                                size="small"
                              />
                            </ListItemIcon>
                            <ListItemText
                              primary={item.description}
                              secondary={`Detected: ${item.detected_value} (expected: ${item.expected_range[0].toFixed(1)} - ${item.expected_range[1].toFixed(1)})`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                ))}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 3 && (
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">
                <ImpactIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                High-Impact Storylines
              </Typography>
              <Button
                variant="outlined"
                onClick={loadHighImpact}
                disabled={impactLoading}
                startIcon={impactLoading ? <CircularProgress size={20} /> : <Refresh />}
              >
                Refresh
              </Button>
            </Box>

            {impactLoading && <LinearProgress sx={{ mb: 2 }} />}

            {highImpact && (
              <>
                <Grid container spacing={2} sx={{ mb: 3 }}>
                  <Grid item xs={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4">{highImpact.summary?.total_found || 0}</Typography>
                      <Typography variant="body2">High Impact</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={4}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4">
                        {((highImpact.summary?.avg_impact || 0) * 100).toFixed(0)}%
                      </Typography>
                      <Typography variant="body2">Avg Impact</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={4}>
                    <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'error.50' }}>
                      <Typography variant="h4" color="error.main">
                        {highImpact.summary?.critical_count || 0}
                      </Typography>
                      <Typography variant="body2">Critical</Typography>
                    </Paper>
                  </Grid>
                </Grid>

                <List>
                  {(highImpact.high_impact_storylines || []).map((s, idx) => (
                    <Paper key={idx} sx={{ mb: 2, p: 2 }}>
                      <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                        <Box flex={1}>
                          <Box display="flex" alignItems="center" gap={1} mb={1}>
                            <Typography variant="h6">{s.title}</Typography>
                            <Chip
                              label={s.impact_level}
                              color={getImpactColor(s.impact_level)}
                              size="small"
                            />
                            <Chip
                              label={`${s.article_count} articles`}
                              size="small"
                              variant="outlined"
                            />
                          </Box>

                          <Box display="flex" gap={2} mb={1}>
                            <Typography variant="body2">
                              Impact: <strong>{(s.impact_score * 100).toFixed(0)}%</strong>
                            </Typography>
                            <Typography variant="body2">
                              Velocity: <strong>{(s.velocity * 100).toFixed(0)}%</strong>
                            </Typography>
                            <Typography variant="body2">
                              Longevity: <strong>{s.longevity}</strong>
                            </Typography>
                          </Box>

                          {s.affected_domains?.length > 0 && (
                            <Box display="flex" gap={0.5}>
                              {s.affected_domains.map((d, i) => (
                                <Chip key={i} label={d} size="small" variant="outlined" />
                              ))}
                            </Box>
                          )}
                        </Box>

                        <Box>
                          <CircularProgress
                            variant="determinate"
                            value={s.impact_score * 100}
                            size={60}
                            color={getImpactColor(s.impact_level)}
                          />
                        </Box>
                      </Box>
                    </Paper>
                  ))}
                </List>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default IntelligenceAnalysis;

