import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  Chip,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  Tooltip,
  Badge,
  Alert,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import {
  ExpandMore,
  Article,
  Timeline,
  AutoAwesome,
  Storage,
  TrendingUp,
  History,
  Notifications,
  CheckCircle,
  Error,
  Warning,
  Info,
  Link,
  Tag,
  Source,
  Schedule,
  Person,
  Language,
  CalendarToday,
  Visibility,
  Edit,
  Share,
  Bookmark,
  BookmarkBorder,
  Close
} from '@mui/icons-material';
import { newsSystemService } from '../../services/newsSystemService';
import './EnhancedArticleViewer.css';

const EnhancedArticleViewer = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [articles, setArticles] = useState([]);
  const [masterArticles, setMasterArticles] = useState([]);
  const [storyThreads, setStoryThreads] = useState([]);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('all'); // 'all', 'raw', 'master', 'processed'
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [showArticleDialog, setShowArticleDialog] = useState(false);
  const [preprocessingStatus, setPreprocessingStatus] = useState(null);

  useEffect(() => {
    loadData();
  }, [viewMode]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [articlesRes, masterArticlesRes, storyThreadsRes, preprocessingRes] = await Promise.all([
        newsSystemService.getArticles({ limit: 100 }),
        newsSystemService.getMasterArticles(),
        newsSystemService.getStoryThreads(),
        newsSystemService.getPreprocessingStatus()
      ]);

      if (articlesRes.success) {
        setArticles(articlesRes.articles || []);
      }
      if (masterArticlesRes.success) {
        setMasterArticles(masterArticlesRes.data || []);
      }
      if (storyThreadsRes.success) {
        setStoryThreads(storyThreadsRes.data || []);
      }
      if (preprocessingRes.success) {
        setPreprocessingStatus(preprocessingRes.data);
      }
    } catch (error) {
      setError('Error loading data: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const getFilteredArticles = () => {
    let filtered = [];
    
    switch (viewMode) {
      case 'raw':
        filtered = articles;
        break;
      case 'master':
        filtered = masterArticles;
        break;
      case 'processed':
        filtered = articles.filter(article => article.processing_status === 'processed');
        break;
      default:
        filtered = [...articles, ...masterArticles];
    }

    if (filterCategory) {
      filtered = filtered.filter(article => 
        article.category?.toLowerCase().includes(filterCategory.toLowerCase())
      );
    }

    if (filterSource) {
      filtered = filtered.filter(article => 
        article.source?.toLowerCase().includes(filterSource.toLowerCase())
      );
    }

    if (searchTerm) {
      filtered = filtered.filter(article => 
        article.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        article.content?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        article.summary?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    return filtered.sort((a, b) => new Date(b.published_at || b.published_date) - new Date(a.published_at || a.published_date));
  };

  const handleViewArticle = (article) => {
    setSelectedArticle(article);
    setShowArticleDialog(true);
  };

  const getArticleType = (article) => {
    if (article.source_count) return 'Master Article';
    if (article.processing_status === 'processed') return 'Processed';
    if (article.preprocessing_status) return 'Preprocessed';
    return 'Raw Article';
  };

  const getArticleTypeColor = (article) => {
    if (article.source_count) return 'primary';
    if (article.processing_status === 'processed') return 'success';
    if (article.preprocessing_status) return 'warning';
    return 'default';
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleString();
  };

  const renderArticleCard = (article, index) => (
    <Card key={article.id || index} sx={{ mb: 2 }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="start" mb={2}>
          <Typography variant="h6" sx={{ flex: 1, mr: 2 }}>
            {article.title}
          </Typography>
          <Box display="flex" gap={1} flexShrink={0}>
            <Chip 
              label={getArticleType(article)} 
              color={getArticleTypeColor(article)} 
              size="small" 
            />
            {article.source_count && (
              <Chip 
                label={`${article.source_count} sources`} 
                color="secondary" 
                size="small" 
              />
            )}
            {article.source_priority && (
              <Chip 
                label={`Priority: ${article.source_priority}`} 
                color="info" 
                size="small" 
              />
            )}
          </Box>
        </Box>

        <Box display="flex" alignItems="center" gap={2} mb={2} sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
          <Box display="flex" alignItems="center" gap={0.5}>
            <Source fontSize="small" />
            <span>{article.source}</span>
          </Box>
          <Box display="flex" alignItems="center" gap={0.5}>
            <CalendarToday fontSize="small" />
            <span>{formatDateTime(article.published_at || article.published_date)}</span>
          </Box>
          {article.category && (
            <Chip label={article.category} size="small" variant="outlined" />
          )}
        </Box>

        {article.tags && article.tags.length > 0 && (
          <Box sx={{ mb: 2 }}>
            {article.tags.slice(0, 8).map((tag, tagIndex) => (
              <Chip
                key={tagIndex}
                label={typeof tag === 'string' ? tag : tag.text}
                size="small"
                sx={{ mr: 1, mb: 1 }}
                color={typeof tag === 'object' && tag.score > 0.7 ? 'primary' : 'default'}
              />
            ))}
            {article.tags.length > 8 && (
              <Chip
                label={`+${article.tags.length - 8} more`}
                size="small"
                variant="outlined"
                sx={{ mr: 1, mb: 1 }}
              />
            )}
          </Box>
        )}

        <Typography variant="body1" sx={{ mb: 2, lineHeight: 1.6 }}>
          {article.summary || article.content?.substring(0, 300) + '...'}
        </Typography>

        <Box display="flex" gap={1} flexWrap="wrap">
          <Button 
            variant="outlined" 
            size="small"
            startIcon={<Visibility />}
            onClick={() => handleViewArticle(article)}
          >
            View Full Article
          </Button>
          
          {article.url && (
            <Button 
              variant="outlined" 
              size="small"
              startIcon={<Link />}
              onClick={() => window.open(article.url, '_blank')}
            >
              Original Source
            </Button>
          )}

          {article.sources && article.sources.length > 0 && (
            <Button 
              variant="outlined" 
              size="small"
              startIcon={<Source />}
              onClick={() => {
                // Show sources in alert for now
                alert(`Sources: ${article.sources.join(', ')}`);
              }}
            >
              View Sources ({article.sources.length})
            </Button>
          )}

          {article.consolidation_metadata && (
            <Button 
              variant="outlined" 
              size="small"
              startIcon={<Timeline />}
              onClick={() => {
                // Show consolidation details in alert for now
                alert(`Consolidation Details: ${JSON.stringify(article.consolidation_metadata, null, 2)}`);
              }}
            >
              Consolidation Details
            </Button>
          )}
        </Box>

        {/* Processing Status */}
        {(article.processing_status || article.preprocessing_status || article.ml_processing_status) && (
          <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Processing Status: {article.processing_status || article.preprocessing_status || article.ml_processing_status}
            </Typography>
            {article.ml_processing_duration_seconds && (
              <Typography variant="caption" color="text.secondary" sx={{ ml: 2 }}>
                ML Processing: {article.ml_processing_duration_seconds}s
              </Typography>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );

  const renderArticleDialog = () => (
    <Dialog 
      open={showArticleDialog} 
      onClose={() => setShowArticleDialog(false)}
      maxWidth="lg"
      fullWidth
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6" sx={{ flex: 1, mr: 2 }}>
            {selectedArticle?.title}
          </Typography>
          <IconButton onClick={() => setShowArticleDialog(false)}>
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        {selectedArticle && (
          <Box>
            {/* Article Metadata */}
            <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Source</Typography>
                  <Typography variant="body1">{selectedArticle.source}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Published</Typography>
                  <Typography variant="body1">
                    {formatDateTime(selectedArticle.published_at || selectedArticle.published_date)}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Category</Typography>
                  <Typography variant="body1">{selectedArticle.category || 'General'}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" color="text.secondary">Type</Typography>
                  <Typography variant="body1">{getArticleType(selectedArticle)}</Typography>
                </Grid>
                {selectedArticle.source_count && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="subtitle2" color="text.secondary">Source Count</Typography>
                    <Typography variant="body1">{selectedArticle.source_count}</Typography>
                  </Grid>
                )}
                {selectedArticle.source_priority && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="subtitle2" color="text.secondary">Priority</Typography>
                    <Typography variant="body1">{selectedArticle.source_priority}</Typography>
                  </Grid>
                )}
              </Grid>
            </Paper>

            {/* Tags */}
            {selectedArticle.tags && selectedArticle.tags.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>Tags</Typography>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {selectedArticle.tags.map((tag, index) => (
                    <Chip
                      key={index}
                      label={typeof tag === 'string' ? tag : tag.text}
                      color={typeof tag === 'object' && tag.score > 0.7 ? 'primary' : 'default'}
                      size="small"
                    />
                  ))}
                </Box>
              </Box>
            )}

            {/* Summary */}
            {selectedArticle.summary && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>Summary</Typography>
                <Typography variant="body1" sx={{ lineHeight: 1.6 }}>
                  {selectedArticle.summary}
                </Typography>
              </Box>
            )}

            {/* Full Content */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>Full Content</Typography>
              <Typography variant="body1" sx={{ lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {selectedArticle.content}
              </Typography>
            </Box>

            {/* Sources */}
            {selectedArticle.sources && selectedArticle.sources.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>Sources</Typography>
                <List>
                  {selectedArticle.sources.map((source, index) => (
                    <ListItem key={index}>
                      <ListItemText primary={source} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}

            {/* Consolidation Metadata */}
            {selectedArticle.consolidation_metadata && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="subtitle1">Consolidation Details</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <pre style={{ fontSize: '0.875rem', overflow: 'auto' }}>
                    {JSON.stringify(selectedArticle.consolidation_metadata, null, 2)}
                  </pre>
                </AccordionDetails>
              </Accordion>
            )}

            {/* Processing Information */}
            {(selectedArticle.processing_status || selectedArticle.ml_processing_status) && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="subtitle1">Processing Information</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    {selectedArticle.processing_status && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">Processing Status</Typography>
                        <Typography variant="body2">{selectedArticle.processing_status}</Typography>
                      </Grid>
                    )}
                    {selectedArticle.ml_processing_status && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">ML Processing Status</Typography>
                        <Typography variant="body2">{selectedArticle.ml_processing_status}</Typography>
                      </Grid>
                    )}
                    {selectedArticle.ml_processing_duration_seconds && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">ML Processing Duration</Typography>
                        <Typography variant="body2">{selectedArticle.ml_processing_duration_seconds}s</Typography>
                      </Grid>
                    )}
                    {selectedArticle.ml_model_used && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">ML Model Used</Typography>
                        <Typography variant="body2">{selectedArticle.ml_model_used}</Typography>
                      </Grid>
                    )}
                  </Grid>
                </AccordionDetails>
              </Accordion>
            )}
          </Box>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={() => setShowArticleDialog(false)}>Close</Button>
        {selectedArticle?.url && (
          <Button 
            variant="contained" 
            startIcon={<Link />}
            onClick={() => window.open(selectedArticle.url, '_blank')}
          >
            View Original
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );

  const renderFilters = () => (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>View Mode</InputLabel>
              <Select
                value={viewMode}
                label="View Mode"
                onChange={(e) => setViewMode(e.target.value)}
              >
                <MenuItem value="all">All Articles</MenuItem>
                <MenuItem value="raw">Raw Articles</MenuItem>
                <MenuItem value="master">Master Articles</MenuItem>
                <MenuItem value="processed">Processed Articles</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search articles..."
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Category"
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              placeholder="Filter by category..."
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Source"
              value={filterSource}
              onChange={(e) => setFilterSource(e.target.value)}
              placeholder="Filter by source..."
            />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );

  const filteredArticles = getFilteredArticles();

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Enhanced Article Viewer
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Comprehensive view of all articles, summaries, and storylines in the system.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {renderFilters()}

      {/* Preprocessing Status */}
      {preprocessingStatus && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Preprocessing Status</Typography>
            <Grid container spacing={2}>
              <Grid item xs={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="h4" color="primary">
                    {preprocessingStatus.total_master_articles || 0}
                  </Typography>
                  <Typography variant="body2">Master Articles</Typography>
                </Box>
              </Grid>
              <Grid item xs={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="h4" color="secondary">
                    {preprocessingStatus.consolidated_articles || 0}
                  </Typography>
                  <Typography variant="body2">Consolidated</Typography>
                </Box>
              </Grid>
              <Grid item xs={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="h4" color="info.main">
                    {preprocessingStatus.single_source_articles || 0}
                  </Typography>
                  <Typography variant="body2">Single Source</Typography>
                </Box>
              </Grid>
              <Grid item xs={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="h4" color="success.main">
                    {preprocessingStatus.processing_statistics?.tags_extracted || 0}
                  </Typography>
                  <Typography variant="body2">Tags Extracted</Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      <Box sx={{ mb: 2 }}>
        <Typography variant="h6">
          {filteredArticles.length} articles found
        </Typography>
      </Box>

      {filteredArticles.map((article, index) => renderArticleCard(article, index))}

      {renderArticleDialog()}
    </Box>
  );
};

export default EnhancedArticleViewer;
