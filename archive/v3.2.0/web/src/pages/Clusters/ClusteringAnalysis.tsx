/**
 * Clustering Analysis Page v3.0
 * Advanced document clustering and topic analysis
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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  Tooltip,
  Badge,
} from '@mui/material';
import {
  Group as GroupIcon,
  ExpandMore as ExpandMoreIcon,
  Psychology as PsychologyIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Share as ShareIcon,
  Info as InfoIcon,
  Article as ArticleIcon,
  TrendingUp as TrendingUpIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip } from 'recharts';

interface Cluster {
  cluster_id: number;
  articles: any[];
  centroid: number[];
  size: number;
  keywords: string[];
  summary: string;
  coherence_score: number;
  local_processing: boolean;
}

interface ClusteringAnalysis {
  clusters: Cluster[];
  total_articles: number;
  num_clusters: number;
  algorithm_used: string;
  silhouette_score: number;
  processing_time: number;
  model_used: string;
  local_processing: boolean;
}

const ClusteringAnalysis: React.FC = () => {
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('kmeans');
  const [numClusters, setNumClusters] = useState<number | ''>('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [clusteringAnalysis, setClusteringAnalysis] = useState<ClusteringAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedCluster, setExpandedCluster] = useState<number | false>(false);

  // Sample clustering data for demonstration
  const [sampleAnalysis] = useState<ClusteringAnalysis>({
    clusters: [
      {
        cluster_id: 0,
        articles: [
          { id: 1, title: "Apple announces new iPhone features", content: "Apple Inc. has unveiled..." },
          { id: 2, title: "iPhone sales exceed expectations", content: "Quarterly iPhone sales..." },
          { id: 3, title: "Apple stock reaches new high", content: "Apple's stock price..." }
        ],
        centroid: [0.1, 0.2, 0.3],
        size: 3,
        keywords: ["Apple", "iPhone", "technology", "smartphone", "innovation"],
        summary: "Technology and Apple-related news focusing on iPhone developments and company performance.",
        coherence_score: 0.85,
        local_processing: true
      },
      {
        cluster_id: 1,
        articles: [
          { id: 4, title: "Climate change summit begins", content: "World leaders gather..." },
          { id: 5, title: "New climate policies announced", content: "Environmental regulations..." },
          { id: 6, title: "Renewable energy investments", content: "Green energy funding..." }
        ],
        centroid: [0.4, 0.5, 0.6],
        size: 3,
        keywords: ["climate", "environment", "renewable", "energy", "policy"],
        summary: "Environmental and climate-related news covering policy changes and renewable energy developments.",
        coherence_score: 0.92,
        local_processing: true
      },
      {
        cluster_id: 2,
        articles: [
          { id: 7, title: "Stock market volatility continues", content: "Market fluctuations..." },
          { id: 8, title: "Federal Reserve interest rates", content: "Central bank decisions..." },
          { id: 9, title: "Economic indicators show growth", content: "GDP and employment data..." }
        ],
        centroid: [0.7, 0.8, 0.9],
        size: 3,
        keywords: ["economy", "finance", "market", "banking", "investment"],
        summary: "Economic and financial news covering market trends, banking policies, and economic indicators.",
        coherence_score: 0.78,
        local_processing: true
      }
    ],
    total_articles: 9,
    num_clusters: 3,
    algorithm_used: 'kmeans',
    silhouette_score: 0.72,
    processing_time: 3.2,
    model_used: 'nomic-embed-text',
    local_processing: true
  });

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setError(null);

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 3000));
      setClusteringAnalysis(sampleAnalysis);
    } catch (err) {
      setError('Clustering analysis failed. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleClusterExpand = (clusterId: number) => {
    setExpandedCluster(expandedCluster === clusterId ? false : clusterId);
  };

  const getCoherenceColor = (score: number) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const getCoherenceLabel = (score: number) => {
    if (score >= 0.8) return 'High';
    if (score >= 0.6) return 'Medium';
    return 'Low';
  };

  // Prepare data for charts
  const clusterSizeData = clusteringAnalysis?.clusters.map(cluster => ({
    name: `Cluster ${cluster.cluster_id}`,
    value: cluster.size,
    coherence: cluster.coherence_score
  })) || [];

  const keywordData = clusteringAnalysis?.clusters.flatMap(cluster => 
    cluster.keywords.map(keyword => ({
      keyword,
      cluster: cluster.cluster_id,
      count: 1
    }))
  ).reduce((acc: any[], curr) => {
    const existing = acc.find(item => item.keyword === curr.keyword);
    if (existing) {
      existing.count += 1;
    } else {
      acc.push(curr);
    }
    return acc;
  }, []).sort((a, b) => b.count - a.count).slice(0, 10) || [];

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Clustering Analysis
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Advanced document clustering and topic analysis using local AI models.
        </Typography>

        {/* Controls */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Clustering Algorithm</InputLabel>
                <Select
                  value={selectedAlgorithm}
                  onChange={(e) => setSelectedAlgorithm(e.target.value)}
                  label="Clustering Algorithm"
                >
                  <MenuItem value="kmeans">K-Means</MenuItem>
                  <MenuItem value="dbscan">DBSCAN</MenuItem>
                  <MenuItem value="agglomerative">Agglomerative</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Number of Clusters</InputLabel>
                <Select
                  value={numClusters}
                  onChange={(e) => setNumClusters(e.target.value as number | '')}
                  label="Number of Clusters"
                >
                  <MenuItem value="">Auto-detect</MenuItem>
                  <MenuItem value={2}>2 Clusters</MenuItem>
                  <MenuItem value={3}>3 Clusters</MenuItem>
                  <MenuItem value={4}>4 Clusters</MenuItem>
                  <MenuItem value={5}>5 Clusters</MenuItem>
                  <MenuItem value={6}>6 Clusters</MenuItem>
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
                {isAnalyzing ? 'Clustering...' : 'Analyze Clusters'}
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
              AI is clustering articles using local models...
            </Typography>
          </Box>
        )}
      </Box>

      {/* Analysis Results */}
      {clusteringAnalysis && (
        <Grid container spacing={3}>
          {/* Summary Statistics */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Clustering Summary
                </Typography>
                <Grid container spacing={3} alignItems="center">
                  <Grid item xs={6} sm={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {clusteringAnalysis.num_clusters}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Clusters Found
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {clusteringAnalysis.total_articles}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Articles Analyzed
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {clusteringAnalysis.silhouette_score.toFixed(2)}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Silhouette Score
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {clusteringAnalysis.processing_time.toFixed(1)}s
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

          {/* Cluster Size Distribution */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Cluster Size Distribution
                </Typography>
                <Box sx={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={clusterSizeData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, value }) => `${name}: ${value}`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {clusterSizeData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Top Keywords */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Keywords Across Clusters
                </Typography>
                <Box sx={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={keywordData.slice(0, 8)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="keyword" />
                      <YAxis />
                      <RechartsTooltip />
                      <Bar dataKey="count" fill="#8884d8" />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Cluster Details */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Cluster Details
                </Typography>
                {clusteringAnalysis.clusters.map((cluster) => (
                  <Accordion
                    key={cluster.cluster_id}
                    expanded={expandedCluster === cluster.cluster_id}
                    onChange={() => handleClusterExpand(cluster.cluster_id)}
                    sx={{ mb: 2 }}
                  >
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                        <GroupIcon sx={{ mr: 2, color: COLORS[cluster.cluster_id % COLORS.length] }} />
                        <Box sx={{ flexGrow: 1 }}>
                          <Typography variant="h6">
                            Cluster {cluster.cluster_id}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {cluster.summary}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1, mr: 2 }}>
                          <Chip
                            label={`${cluster.size} articles`}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                          <Chip
                            label={`${getCoherenceLabel(cluster.coherence_score)} coherence`}
                            size="small"
                            color={getCoherenceColor(cluster.coherence_score)}
                            variant="outlined"
                          />
                        </Box>
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Grid container spacing={3}>
                        {/* Keywords */}
                        <Grid item xs={12} md={6}>
                          <Typography variant="subtitle1" gutterBottom>
                            Keywords
                          </Typography>
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                            {cluster.keywords.map((keyword, index) => (
                              <Chip
                                key={index}
                                label={keyword}
                                size="small"
                                color="primary"
                                variant="outlined"
                              />
                            ))}
                          </Box>
                        </Grid>

                        {/* Coherence Score */}
                        <Grid item xs={12} md={6}>
                          <Typography variant="subtitle1" gutterBottom>
                            Coherence Analysis
                          </Typography>
                          <Box sx={{ mb: 2 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                              <Typography variant="body2">Coherence Score</Typography>
                              <Typography variant="body2" color="text.secondary">
                                {(cluster.coherence_score * 100).toFixed(1)}%
                              </Typography>
                            </Box>
                            <LinearProgress
                              variant="determinate"
                              value={cluster.coherence_score * 100}
                              color={getCoherenceColor(cluster.coherence_score)}
                              sx={{ height: 8, borderRadius: 4 }}
                            />
                          </Box>
                        </Grid>

                        {/* Articles */}
                        <Grid item xs={12}>
                          <Typography variant="subtitle1" gutterBottom>
                            Articles in this Cluster
                          </Typography>
                          <List dense>
                            {cluster.articles.map((article, index) => (
                              <ListItem key={index} sx={{ px: 0 }}>
                                <ListItemIcon>
                                  <ArticleIcon color="action" />
                                </ListItemIcon>
                                <ListItemText
                                  primary={article.title}
                                  secondary={article.content.substring(0, 100) + '...'}
                                />
                                <IconButton size="small">
                                  <InfoIcon />
                                </IconButton>
                              </ListItem>
                            ))}
                          </List>
                        </Grid>
                      </Grid>
                    </AccordionDetails>
                  </Accordion>
                ))}
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
                      Algorithm Used
                    </Typography>
                    <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                      {clusteringAnalysis.algorithm_used}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Model Used
                    </Typography>
                    <Typography variant="body1">
                      {clusteringAnalysis.model_used}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Processing Time
                    </Typography>
                    <Typography variant="body1">
                      {clusteringAnalysis.processing_time.toFixed(2)}s
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Local Processing
                    </Typography>
                    <Typography variant="body1">
                      {clusteringAnalysis.local_processing ? 'Yes' : 'No'}
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

export default ClusteringAnalysis;


