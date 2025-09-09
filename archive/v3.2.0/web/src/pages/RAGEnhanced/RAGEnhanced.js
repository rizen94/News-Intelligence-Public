import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  IconButton,
  Tooltip,
  Badge
} from '@mui/material';
import {
  Search as SearchIcon,
  Psychology as PsychologyIcon,
  Timeline as TimelineIcon,
  History as HistoryIcon,
  Link as LinkIcon,
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Share as ShareIcon,
  Bookmark as BookmarkIcon,
  TrendingUp as TrendingUpIcon,
  Article as ArticleIcon,
  Source as SourceIcon,
  AutoAwesome as AutoAwesomeIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`rag-tabpanel-${index}`}
      aria-labelledby={`rag-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function RAGEnhanced() {
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState('comprehensive');
  const [maxResults, setMaxResults] = useState(20);
  const [includeMLAnalysis, setIncludeMLAnalysis] = useState(true);
  const [searchResults, setSearchResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [ragStats, setRagStats] = useState(null);
  const [storyId, setStoryId] = useState('');
  const [storyTitle, setStoryTitle] = useState('');
  const [dossier, setDossier] = useState(null);
  const [comprehensiveResearch, setComprehensiveResearch] = useState(null);
  const [externalServicesStatus, setExternalServicesStatus] = useState(null);
  const [researchQuery, setResearchQuery] = useState('');
  const [storyKeywords, setStoryKeywords] = useState('');

  // Load RAG statistics and external services status on component mount
  useEffect(() => {
    loadRAGStatistics();
    loadExternalServicesStatus();
  }, []);

  const loadRAGStatistics = async () => {
    try {
      const response = await newsSystemService.getRAGStatistics();
      setRagStats(response.statistics);
    } catch (err) {
      console.error('Failed to load RAG statistics:', err);
    }
  };

  const loadExternalServicesStatus = async () => {
    try {
      const response = await newsSystemService.getExternalServicesStatus();
      setExternalServicesStatus(response.services);
    } catch (err) {
      console.error('Failed to load external services status:', err);
    }
  };

  const handleRAGSearch = async () => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSearchResults(null);

      const response = await newsSystemService.performRAGSearch(
        searchQuery,
        searchType,
        maxResults
      );

      setSearchResults(response.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBuildDossier = async () => {
    if (!storyId.trim()) {
      setError('Please enter a story ID');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setDossier(null);

      const response = await newsSystemService.buildStoryDossierWithRAG(
        storyId,
        storyTitle || null,
        true, // include historical
        true, // include related
        true  // include analysis
      );

      setDossier(response.dossier);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleComprehensiveResearch = async () => {
    if (!researchQuery.trim()) {
      setError('Please enter a research query');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setComprehensiveResearch(null);

      const keywords = storyKeywords.split(',').map(k => k.trim()).filter(k => k);
      
      const response = await newsSystemService.performComprehensiveResearch(
        researchQuery,
        keywords,
        true, // include external
        true  // include internal
      );

      setComprehensiveResearch(response.context);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const renderSearchResults = () => {
    if (!searchResults) return null;

    return (
      <Box>
        <Typography variant="h6" gutterBottom>
          Search Results for: "{searchResults.query}"
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Search Statistics
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">Articles Found:</Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {searchResults.articles_found}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">ML Enhanced:</Typography>
                    <Chip 
                      label={searchResults.ml_enhanced ? 'Yes' : 'No'}
                      color={searchResults.ml_enhanced ? 'success' : 'default'}
                      size="small"
                    />
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">Processing Time:</Typography>
                    <Typography variant="body2">
                      {formatDuration(searchResults.processing_time)}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={9}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Context Summary
                </Typography>
                <Typography variant="body2">
                  {searchResults.base_summary || searchResults.context_summary || 'No summary available'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* ML Analysis */}
        {searchResults.ml_analysis && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                ML-Enhanced Analysis
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {searchResults.ml_analysis.summary}
              </Typography>
              <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip 
                  label={`Model: ${searchResults.ml_analysis.model_used}`}
                  size="small"
                  variant="outlined"
                />
                <Chip 
                  label={`Generated: ${formatDateTime(searchResults.ml_analysis.generated_at)}`}
                  size="small"
                  variant="outlined"
                />
              </Box>
            </CardContent>
          </Card>
        )}

        {/* Argument Analysis */}
        {searchResults.argument_analysis && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Argument Analysis
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {searchResults.argument_analysis.argument_analysis}
              </Typography>
            </CardContent>
          </Card>
        )}

        {/* Key Insights */}
        {searchResults.key_insights && searchResults.key_insights.length > 0 && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Key Insights
              </Typography>
              <List dense>
                {searchResults.key_insights.map((insight, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <TrendingUpIcon color="primary" />
                    </ListItemIcon>
                    <ListItemText primary={insight} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        )}

        {/* Articles */}
        {searchResults.articles && searchResults.articles.length > 0 && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <ArticleIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Relevant Articles ({searchResults.articles.length})
              </Typography>
              <List>
                {searchResults.articles.map((article, index) => (
                  <React.Fragment key={index}>
                    <ListItem>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="subtitle1">
                              {article.title}
                            </Typography>
                            {article.ml_processed && (
                              <Chip 
                                label="ML Processed"
                                color="success"
                                size="small"
                                icon={<PsychologyIcon />}
                              />
                            )}
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {article.summary || article.content?.substring(0, 200) + '...'}
                            </Typography>
                            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                              <Chip 
                                label={article.source}
                                size="small"
                                variant="outlined"
                                icon={<SourceIcon />}
                              />
                              <Chip 
                                label={formatDateTime(article.published_date)}
                                size="small"
                                variant="outlined"
                              />
                              <Chip 
                                label={`Quality: ${(article.quality_score * 100).toFixed(0)}%`}
                                size="small"
                                color={article.quality_score > 0.7 ? 'success' : article.quality_score > 0.4 ? 'warning' : 'error'}
                              />
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < searchResults.articles.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>
        )}
      </Box>
    );
  };

  const renderDossier = () => {
    if (!dossier) return null;

    return (
      <Box>
        <Typography variant="h6" gutterBottom>
          Story Dossier: {dossier.story_title || dossier.story_id}
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Dossier Statistics
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">Processing Time:</Typography>
                    <Typography variant="body2">
                      {formatDuration(dossier.processing_time)}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">Sections:</Typography>
                    <Typography variant="body2">
                      {Object.keys(dossier.sections || {}).length}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2">Generated:</Typography>
                    <Typography variant="body2">
                      {formatDateTime(dossier.generated_at)}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Summary
                </Typography>
                <Typography variant="body2">
                  {dossier.summary}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Key Insights */}
        {dossier.key_insights && dossier.key_insights.length > 0 && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Key Insights
              </Typography>
              <List dense>
                {dossier.key_insights.map((insight, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <TrendingUpIcon color="primary" />
                    </ListItemIcon>
                    <ListItemText primary={insight} />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        )}

        {/* Dossier Sections */}
        {dossier.sections && Object.keys(dossier.sections).length > 0 && (
          <Box>
            {Object.entries(dossier.sections).map(([sectionName, sectionData]) => (
              <Accordion key={sectionName} sx={{ mb: 2 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
                    {sectionName.replace('_', ' ')}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  {sectionName === 'expert_analysis' && sectionData.analysis ? (
                    <Box>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                        {sectionData.analysis}
                      </Typography>
                      <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        <Chip 
                          label={`Model: ${sectionData.model_used}`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip 
                          label={`Articles: ${sectionData.articles_analyzed}`}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    </Box>
                  ) : sectionData.articles_found ? (
                    <Box>
                      <Typography variant="body2" sx={{ mb: 2 }}>
                        {sectionData.base_summary || sectionData.context_summary}
                      </Typography>
                      <Typography variant="subtitle2">
                        Found {sectionData.articles_found} articles
                      </Typography>
                    </Box>
                  ) : (
                    <Typography variant="body2">
                      {JSON.stringify(sectionData, null, 2)}
                    </Typography>
                  )}
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        )}
      </Box>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          RAG Enhanced Intelligence
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh Statistics">
            <IconButton onClick={loadRAGStatistics}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* RAG Statistics */}
      {ragStats && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              RAG Service Statistics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {ragStats.total_requests}
                  </Typography>
                  <Typography variant="body2">Total Requests</Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="success.main">
                    {ragStats.ml_enhanced_requests}
                  </Typography>
                  <Typography variant="body2">ML Enhanced</Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="info.main">
                    {formatDuration(ragStats.avg_processing_time)}
                  </Typography>
                  <Typography variant="body2">Avg Processing Time</Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="warning.main">
                    {(ragStats.success_rate * 100).toFixed(1)}%
                  </Typography>
                  <Typography variant="body2">Success Rate</Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="RAG Search" icon={<SearchIcon />} />
          <Tab label="Story Dossier" icon={<BookmarkIcon />} />
          <Tab label="Comprehensive Research" icon={<AutoAwesomeIcon />} />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Enhanced RAG Search
            </Typography>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Search Query"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Enter your search query..."
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Search Type</InputLabel>
                  <Select
                    value={searchType}
                    onChange={(e) => setSearchType(e.target.value)}
                    label="Search Type"
                  >
                    <MenuItem value="comprehensive">Comprehensive</MenuItem>
                    <MenuItem value="historical">Historical</MenuItem>
                    <MenuItem value="related">Related</MenuItem>
                    <MenuItem value="expert">Expert Analysis</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Max Results"
                  type="number"
                  value={maxResults}
                  onChange={(e) => setMaxResults(parseInt(e.target.value) || 20)}
                  inputProps={{ min: 1, max: 50 }}
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleRAGSearch}
                  disabled={loading}
                  startIcon={loading ? <CircularProgress size={20} /> : <SearchIcon />}
                >
                  {loading ? 'Searching...' : 'Search'}
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {renderSearchResults()}
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Build Story Dossier
            </Typography>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Story ID"
                  value={storyId}
                  onChange={(e) => setStoryId(e.target.value)}
                  placeholder="Enter story identifier..."
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Story Title (Optional)"
                  value={storyTitle}
                  onChange={(e) => setStoryTitle(e.target.value)}
                  placeholder="Enter story title..."
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleBuildDossier}
                  disabled={loading}
                  startIcon={loading ? <CircularProgress size={20} /> : <BookmarkIcon />}
                >
                  {loading ? 'Building...' : 'Build Dossier'}
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {renderDossier()}
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Comprehensive Research with External Sources
            </Typography>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Research Query"
                  value={researchQuery}
                  onChange={(e) => setResearchQuery(e.target.value)}
                  placeholder="Enter your research topic..."
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Story Keywords (comma-separated)"
                  value={storyKeywords}
                  onChange={(e) => setStoryKeywords(e.target.value)}
                  placeholder="tech, AI, innovation..."
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleComprehensiveResearch}
                  disabled={loading}
                  startIcon={loading ? <CircularProgress size={20} /> : <AutoAwesomeIcon />}
                >
                  {loading ? 'Researching...' : 'Start Research'}
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* External Services Status */}
        {externalServicesStatus && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                External Services Status
              </Typography>
              <Grid container spacing={2}>
                {Object.entries(externalServicesStatus).map(([service, status]) => (
                  <Grid item xs={12} sm={6} md={4} key={service}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip 
                        label={service.replace('_', ' ').toUpperCase()}
                        color={status.available ? 'success' : 'default'}
                        size="small"
                      />
                      <Typography variant="body2">
                        {status.available ? 'Available' : 'Not Available'}
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {status.description}
                    </Typography>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        )}

        {/* Comprehensive Research Results */}
        {comprehensiveResearch && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Research Results for: "{comprehensiveResearch.query}"
            </Typography>
            
            {/* Summary */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  Comprehensive Summary
                </Typography>
                <Typography variant="body2">
                  {comprehensiveResearch.comprehensive_summary}
                </Typography>
                <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip 
                    label={`Processing Time: ${formatDuration(comprehensiveResearch.processing_time)}`}
                    size="small"
                    variant="outlined"
                  />
                  <Chip 
                    label={`Sources: ${comprehensiveResearch.total_sources}`}
                    size="small"
                    variant="outlined"
                  />
                  <Chip 
                    label={`Generated: ${formatDateTime(comprehensiveResearch.generated_at)}`}
                    size="small"
                    variant="outlined"
                  />
                </Box>
              </CardContent>
            </Card>

            {/* Sources */}
            {comprehensiveResearch.sources && Object.keys(comprehensiveResearch.sources).length > 0 && (
              <Box>
                {Object.entries(comprehensiveResearch.sources).map(([sourceName, sourceData]) => (
                  <Accordion key={sourceName} sx={{ mb: 2 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
                        {sourceName.replace('_', ' ')} ({sourceData.count || 'N/A'})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      {sourceName === 'internal_database' ? (
                        <Box>
                          <Typography variant="body2" sx={{ mb: 2 }}>
                            {sourceData.summary}
                          </Typography>
                          <Typography variant="subtitle2">
                            Found {sourceData.count} articles in internal database
                          </Typography>
                        </Box>
                      ) : sourceName === 'external_services' ? (
                        <Box>
                          {sourceData.sources && Object.keys(sourceData.sources).length > 0 && (
                            <Box>
                              {Object.entries(sourceData.sources).map(([service, serviceData]) => (
                                <Box key={service} sx={{ mb: 2 }}>
                                  <Typography variant="subtitle2" sx={{ textTransform: 'capitalize' }}>
                                    {service} ({serviceData.count} items)
                                  </Typography>
                                  {service === 'wikipedia' && serviceData.articles && (
                                    <List dense>
                                      {serviceData.articles.slice(0, 3).map((article, index) => (
                                        <ListItem key={index}>
                                          <ListItemText
                                            primary={article.title}
                                            secondary={article.snippet}
                                          />
                                        </ListItem>
                                      ))}
                                    </List>
                                  )}
                                  {service === 'newsapi' && serviceData.articles && (
                                    <List dense>
                                      {serviceData.articles.slice(0, 3).map((article, index) => (
                                        <ListItem key={index}>
                                          <ListItemText
                                            primary={article.title}
                                            secondary={article.description}
                                          />
                                        </ListItem>
                                      ))}
                                    </List>
                                  )}
                                </Box>
                              ))}
                            </Box>
                          )}
                        </Box>
                      ) : (
                        <Typography variant="body2">
                          {JSON.stringify(sourceData, null, 2)}
                        </Typography>
                      )}
                    </AccordionDetails>
                  </Accordion>
                ))}
              </Box>
            )}

            {/* ML Analysis */}
            {comprehensiveResearch.ml_analysis && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                    ML-Enhanced Analysis
                  </Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {comprehensiveResearch.ml_analysis.summary}
                  </Typography>
                </CardContent>
              </Card>
            )}

            {/* Key Insights */}
            {comprehensiveResearch.key_insights && comprehensiveResearch.key_insights.length > 0 && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Key Insights
                  </Typography>
                  <List dense>
                    {comprehensiveResearch.key_insights.map((insight, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <TrendingUpIcon color="primary" />
                        </ListItemIcon>
                        <ListItemText primary={insight} />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            )}
          </Box>
        )}
      </TabPanel>
    </Box>
  );
}

export default RAGEnhanced;
