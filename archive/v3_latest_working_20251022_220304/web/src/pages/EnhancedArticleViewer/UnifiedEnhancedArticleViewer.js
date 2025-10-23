import {
  Search,
  FilterList,
  ViewList,
  Article,
  Source,
  Timeline,
  Close,
  Refresh,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  LinearProgress,
  Alert,
  Card,
  CardContent,
  Grid,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  Divider,
  Paper,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import newsSystemService from '../../services/newsSystemService';

const UnifiedEnhancedArticleViewer = () => {
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

  const loadData = async() => {
    setLoading(true);
    try {
      const [articlesRes, masterArticlesRes, storyThreadsRes, preprocessingRes] = await Promise.all([
        newsSystemService.getArticles({ limit: 100 }),
        newsSystemService.getMasterArticles(),
        newsSystemService.getStoryThreads(),
        newsSystemService.getPreprocessingStatus(),
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
      filtered = articles.filter(article => !article.master_article_id);
      break;
    case 'master':
      filtered = masterArticles;
      break;
    case 'processed':
      filtered = articles.filter(article => article.master_article_id);
      break;
    default:
      filtered = [...articles, ...masterArticles];
    }

    if (filterCategory) {
      filtered = filtered.filter(article =>
        article.category === filterCategory ||
        article.tags?.includes(filterCategory),
      );
    }

    if (filterSource) {
      filtered = filtered.filter(article =>
        article.source === filterSource ||
        article.sources?.includes(filterSource),
      );
    }

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(article =>
        article.title?.toLowerCase().includes(term) ||
        article.content?.toLowerCase().includes(term) ||
        article.summary?.toLowerCase().includes(term),
      );
    }

    return filtered;
  };

  const handleArticleClick = (article) => {
    setSelectedArticle(article);
    setShowArticleDialog(true);
  };

  const handleCloseDialog = () => {
    setShowArticleDialog(false);
    setSelectedArticle(null);
  };

  const getUniqueCategories = () => {
    const categories = new Set();
    [...articles, ...masterArticles].forEach(article => {
      if (article.category) categories.add(article.category);
      if (article.tags) {
        article.tags.forEach(tag => categories.add(tag));
      }
    });
    return Array.from(categories).sort();
  };

  const getUniqueSources = () => {
    const sources = new Set();
    [...articles, ...masterArticles].forEach(article => {
      if (article.source) sources.add(article.source);
      if (article.sources) {
        article.sources.forEach(source => sources.add(source));
      }
    });
    return Array.from(sources).sort();
  };

  const renderArticleCard = (article, index) => (
    <div key={article.id || index} className="unified-content-card unified-fade-in">
      <div className="unified-content-header">
        <Article sx={{ mr: 1 }} />
        <div className="unified-content-title">
          {article.title || 'Untitled Article'}
        </div>
      </div>
      <div className="unified-content-body">
        <div className="unified-content-text">
          {article.summary || article.content?.substring(0, 300) + '...'}
        </div>

        {/* Article Metadata */}
        <div style={{ marginBottom: 'var(--spacing-md)' }}>
          {article.source && (
            <Chip
              label={article.source}
              size="small"
              sx={{ mr: 1, mb: 1 }}
              color="primary"
              variant="outlined"
            />
          )}
          {article.category && (
            <Chip
              label={article.category}
              size="small"
              sx={{ mr: 1, mb: 1 }}
              color="secondary"
              variant="outlined"
            />
          )}
          {article.tags && article.tags.slice(0, 3).map((tag, idx) => (
            <Chip
              key={idx}
              label={tag}
              size="small"
              sx={{ mr: 1, mb: 1 }}
              variant="outlined"
            />
          ))}
        </div>

        <div className="unified-content-actions">
          <Button
            variant="contained"
            size="small"
            onClick={() => handleArticleClick(article)}
            className="unified-button-sm"
          >
            View Details
          </Button>

          {article.url && (
            <Button
              variant="outlined"
              size="small"
              onClick={() => window.open(article.url, '_blank')}
              className="unified-button-sm"
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
                alert(`Sources: ${article.sources.join(', ')}`);
              }}
              className="unified-button-sm"
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
                alert(`Consolidation Details: ${JSON.stringify(article.consolidation_metadata, null, 2)}`);
              }}
              className="unified-button-sm"
            >
              Consolidation Details
            </Button>
          )}
        </div>

        {/* Processing Status */}
        {(article.processing_status || article.preprocessing_status || article.ml_processing_status) && (
          <div style={{ marginTop: 'var(--spacing-sm)' }}>
            {article.processing_status && (
              <Chip
                label={`Processing: ${article.processing_status}`}
                size="small"
                color="info"
                variant="outlined"
                sx={{ mr: 1 }}
              />
            )}
            {article.preprocessing_status && (
              <Chip
                label={`Preprocessing: ${article.preprocessing_status}`}
                size="small"
                color="warning"
                variant="outlined"
                sx={{ mr: 1 }}
              />
            )}
            {article.ml_processing_status && (
              <Chip
                label={`ML: ${article.ml_processing_status}`}
                size="small"
                color="success"
                variant="outlined"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );

  const renderFilters = () => (
    <div className="unified-content-card unified-fade-in">
      <div className="unified-content-header">
        <FilterList sx={{ mr: 1 }} />
        <div className="unified-content-title">Filters & Search</div>
      </div>
      <div className="unified-content-body">
        <div className="unified-grid unified-grid-4">
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

          <FormControl fullWidth size="small">
            <InputLabel>Category</InputLabel>
            <Select
              value={filterCategory}
              label="Category"
              onChange={(e) => setFilterCategory(e.target.value)}
            >
              <MenuItem value="">All Categories</MenuItem>
              {getUniqueCategories().map(category => (
                <MenuItem key={category} value={category}>{category}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth size="small">
            <InputLabel>Source</InputLabel>
            <Select
              value={filterSource}
              label="Source"
              onChange={(e) => setFilterSource(e.target.value)}
            >
              <MenuItem value="">All Sources</MenuItem>
              {getUniqueSources().map(source => (
                <MenuItem key={source} value={source}>{source}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            fullWidth
            size="small"
            label="Search"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
          />
        </div>
      </div>
    </div>
  );

  const renderArticleDialog = () => (
    <Dialog
      open={showArticleDialog}
      onClose={handleCloseDialog}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            {selectedArticle?.title || 'Article Details'}
          </Typography>
          <IconButton onClick={handleCloseDialog}>
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {selectedArticle && (
          <Box>
            <Typography variant="body1" paragraph>
              {selectedArticle.content || selectedArticle.summary}
            </Typography>

            <Divider sx={{ my: 2 }} />

            <Typography variant="h6" gutterBottom>Metadata</Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Source:</strong> {selectedArticle.source || 'Unknown'}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Category:</strong> {selectedArticle.category || 'Uncategorized'}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Published:</strong> {selectedArticle.published_date ? new Date(selectedArticle.published_date).toLocaleDateString() : 'Unknown'}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>ID:</strong> {selectedArticle.id}
                </Typography>
              </Grid>
            </Grid>

            {selectedArticle.tags && selectedArticle.tags.length > 0 && (
              <Box mt={2}>
                <Typography variant="h6" gutterBottom>Tags</Typography>
                <Box>
                  {selectedArticle.tags.map((tag, index) => (
                    <Chip key={index} label={tag} size="small" sx={{ mr: 1, mb: 1 }} />
                  ))}
                </Box>
              </Box>
            )}

            {selectedArticle.sources && selectedArticle.sources.length > 0 && (
              <Box mt={2}>
                <Typography variant="h6" gutterBottom>Sources</Typography>
                <List dense>
                  {selectedArticle.sources.map((source, index) => (
                    <ListItem key={index}>
                      <ListItemText primary={source} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCloseDialog}>Close</Button>
        {selectedArticle?.url && (
          <Button
            variant="contained"
            onClick={() => window.open(selectedArticle.url, '_blank')}
          >
            View Original
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );

  const filteredArticles = getFilteredArticles();

  return (
    <div className="unified-container-fluid">
      {/* Header */}
      <div className="unified-section">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Enhanced Article Viewer
          </Typography>
          <Tooltip title="Refresh Data">
            <IconButton onClick={loadData} color="primary">
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {loading && <LinearProgress sx={{ mb: 2 }} />}
      </div>

      {/* Preprocessing Status */}
      {preprocessingStatus && (
        <div className="unified-section">
          <div className="unified-grid unified-grid-4">
            <div className="unified-stat-card unified-fade-in">
              <div className="unified-stat-card-content">
                <Article sx={{ fontSize: 40 }} className="unified-stat-icon" />
                <div className="unified-stat-number" style={{ color: '#0288d1' }}>
                  {preprocessingStatus.total_master_articles || 0}
                </div>
                <div className="unified-stat-label">Master Articles</div>
              </div>
            </div>
            <div className="unified-stat-card unified-fade-in">
              <div className="unified-stat-card-content">
                <Timeline sx={{ fontSize: 40 }} className="unified-stat-icon" />
                <div className="unified-stat-number" style={{ color: '#1976d2' }}>
                  {preprocessingStatus.consolidated_articles || 0}
                </div>
                <div className="unified-stat-label">Consolidated</div>
              </div>
            </div>
            <div className="unified-stat-card unified-fade-in">
              <div className="unified-stat-card-content">
                <Article sx={{ fontSize: 40 }} className="unified-stat-icon" />
                <div className="unified-stat-number" style={{ color: '#9c27b0' }}>
                  {preprocessingStatus.single_source_articles || 0}
                </div>
                <div className="unified-stat-label">Single Source</div>
              </div>
            </div>
            <div className="unified-stat-card unified-fade-in">
              <div className="unified-stat-card-content">
                <Timeline sx={{ fontSize: 40 }} className="unified-stat-icon" />
                <div className="unified-stat-number" style={{ color: '#2e7d32' }}>
                  {preprocessingStatus.processing_statistics?.tags_extracted || 0}
                </div>
                <div className="unified-stat-label">Tags Extracted</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {renderFilters()}

      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <ViewList sx={{ mr: 1 }} />
            <div className="unified-content-title">
              {filteredArticles.length} articles found
            </div>
          </div>
          <div className="unified-content-body">
            <div className="unified-grid unified-grid-2">
              {filteredArticles.map((article, index) => renderArticleCard(article, index))}
            </div>
          </div>
        </div>
      </div>

      {renderArticleDialog()}
    </div>
  );
};

export default UnifiedEnhancedArticleViewer;
