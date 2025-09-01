import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Divider,
  Badge,
  Tooltip,
  InputAdornment
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Article as ArticleIcon,
  GroupWork as ClusterIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
  TrendingUp as TrendingUpIcon,
  AutoAwesome as AutoAwesomeIcon,
  Build as BuildIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import ArticleViewer from '../../components/ArticleViewer/ArticleViewer';
import { newsSystemService } from '../../services/newsSystemService';

const UnifiedArticlesAnalysis = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [articles, setArticles] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [showArticleDialog, setShowArticleDialog] = useState(false);
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [sortBy, setSortBy] = useState('date');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [articlesRes, clustersRes, entitiesRes] = await Promise.all([
        newsSystemService.getArticles({ limit: 100 }),
        newsSystemService.getClusters(),
        newsSystemService.getEntities()
      ]);

      if (articlesRes.success) {
        setArticles(articlesRes.articles || []);
      }
      if (clustersRes.success) {
        setClusters(clustersRes.data || []);
      }
      if (entitiesRes.success) {
        setEntities(entitiesRes.data || []);
      }
    } catch (error) {
      setError('Error loading data: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleArticleClick = (article) => {
    setSelectedArticle(article);
    setShowArticleDialog(true);
  };

  const handleCloseDialog = () => {
    setShowArticleDialog(false);
    setSelectedArticle(null);
  };

  const getFilteredArticles = () => {
    let filtered = articles;

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(article =>
        article.title?.toLowerCase().includes(query) ||
        article.content?.toLowerCase().includes(query) ||
        article.summary?.toLowerCase().includes(query)
      );
    }

    if (filterCategory) {
      filtered = filtered.filter(article => article.category === filterCategory);
    }

    if (filterSource) {
      filtered = filtered.filter(article => article.source === filterSource);
    }

    // Sort articles
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'date':
          return new Date(b.published_date) - new Date(a.published_date);
        case 'title':
          return a.title?.localeCompare(b.title);
        case 'source':
          return a.source?.localeCompare(b.source);
        default:
          return 0;
      }
    });

    return filtered;
  };

  const getUniqueCategories = () => {
    const categories = new Set();
    articles.forEach(article => {
      if (article.category) categories.add(article.category);
    });
    return Array.from(categories).sort();
  };

  const getUniqueSources = () => {
    const sources = new Set();
    articles.forEach(article => {
      if (article.source) sources.add(article.source);
    });
    return Array.from(sources).sort();
  };

  const getEntityCounts = () => {
    const counts = {};
    entities.forEach(entity => {
      counts[entity.type] = (counts[entity.type] || 0) + 1;
    });
    return counts;
  };

  const renderArticlesTab = () => {
    const filteredArticles = getFilteredArticles();

    return (
      <div className="unified-section">
        {/* Filters */}
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <FilterIcon sx={{ mr: 1 }} />
            <div className="unified-content-title">Article Filters</div>
          </div>
          <div className="unified-content-body">
            <div className="unified-grid unified-grid-4">
              <TextField
                fullWidth
                size="small"
                label="Search Articles"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
                className="unified-input"
              />

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

              <FormControl fullWidth size="small">
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={sortBy}
                  label="Sort By"
                  onChange={(e) => setSortBy(e.target.value)}
                >
                  <MenuItem value="date">Date</MenuItem>
                  <MenuItem value="title">Title</MenuItem>
                  <MenuItem value="source">Source</MenuItem>
                </Select>
              </FormControl>
            </div>
          </div>
        </div>

        {/* Articles List */}
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <ArticleIcon sx={{ mr: 1 }} />
            <div className="unified-content-title">
              {filteredArticles.length} Articles Found
            </div>
            <Tooltip title="Refresh Articles">
              <IconButton onClick={loadData} color="primary">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </div>
          <div className="unified-content-body">
            <List>
              {filteredArticles.map((article, index) => (
                <React.Fragment key={article.id || index}>
                  <ListItem>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="subtitle1" fontWeight="medium">
                            {article.title || 'Untitled Article'}
                          </Typography>
                          {article.category && (
                            <Chip label={article.category} size="small" color="primary" variant="outlined" />
                          )}
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            {article.summary || article.content?.substring(0, 200) + '...'}
                          </Typography>
                          <Box display="flex" gap={1} mt={1}>
                            {article.source && (
                              <Chip label={article.source} size="small" variant="outlined" />
                            )}
                            <Typography variant="caption" color="text.secondary">
                              {article.published_date ? new Date(article.published_date).toLocaleDateString() : 'No date'}
                            </Typography>
                          </Box>
                        </Box>
                      }
                    />
                    <ListItemSecondaryAction>
                      <Tooltip title="View Article">
                        <IconButton onClick={() => handleArticleClick(article)}>
                          <ViewIcon />
                        </IconButton>
                      </Tooltip>
                    </ListItemSecondaryAction>
                  </ListItem>
                  {index < filteredArticles.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </div>
        </div>
      </div>
    );
  };

  const renderClustersTab = () => {
    return (
      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <ClusterIcon sx={{ mr: 1 }} />
            <div className="unified-content-title">Article Clusters</div>
          </div>
          <div className="unified-content-body">
            {clusters.length > 0 ? (
              <div className="unified-grid unified-grid-2">
                {clusters.map((cluster, index) => (
                  <div key={cluster.id || index} className="unified-content-card unified-scale-in">
                    <div className="unified-content-header">
                      <div className="unified-content-title">{cluster.topic || 'Untitled Cluster'}</div>
                    </div>
                    <div className="unified-content-body">
                      <div className="unified-content-text">
                        {cluster.description || 'No description available'}
                      </div>
                      <div style={{ marginTop: 'var(--spacing-md)' }}>
                        <Chip 
                          label={`${cluster.article_count || 0} articles`} 
                          size="small" 
                          color="primary" 
                          variant="outlined" 
                        />
                        {cluster.keywords && cluster.keywords.slice(0, 3).map((keyword, idx) => (
                          <Chip 
                            key={idx}
                            label={keyword} 
                            size="small" 
                            variant="outlined" 
                            sx={{ ml: 1 }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="unified-content-text">
                No clusters available. Run clustering analysis to group related articles.
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderEntitiesTab = () => {
    const entityCounts = getEntityCounts();

    return (
      <div className="unified-section">
        {/* Entity Statistics */}
        <div className="unified-grid unified-grid-4">
          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <PersonIcon sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#1976d2' }}>
                {entityCounts.PERSON || 0}
              </div>
              <div className="unified-stat-label">People</div>
            </div>
          </div>

          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <BusinessIcon sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#9c27b0' }}>
                {entityCounts.ORG || 0}
              </div>
              <div className="unified-stat-label">Organizations</div>
            </div>
          </div>

          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <LocationIcon sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#2e7d32' }}>
                {entityCounts.GPE || 0}
              </div>
              <div className="unified-stat-label">Locations</div>
            </div>
          </div>

          <div className="unified-stat-card unified-fade-in">
            <div className="unified-stat-card-content">
              <ArticleIcon sx={{ fontSize: 40 }} className="unified-stat-icon" />
              <div className="unified-stat-number" style={{ color: '#f57c00' }}>
                {entities.length}
              </div>
              <div className="unified-stat-label">Total Entities</div>
            </div>
          </div>
        </div>

        {/* Entity List */}
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <AutoAwesome sx={{ mr: 1 }} />
            <div className="unified-content-title">Extracted Entities</div>
          </div>
          <div className="unified-content-body">
            {entities.length > 0 ? (
              <List>
                {entities.slice(0, 20).map((entity, index) => (
                  <React.Fragment key={entity.id || index}>
                    <ListItem>
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Typography variant="subtitle1" fontWeight="medium">
                              {entity.name}
                            </Typography>
                            <Chip 
                              label={entity.type} 
                              size="small" 
                              color={
                                entity.type === 'PERSON' ? 'primary' :
                                entity.type === 'ORG' ? 'secondary' :
                                entity.type === 'GPE' ? 'success' : 'default'
                              }
                              variant="outlined"
                            />
                          </Box>
                        }
                        secondary={
                          <Typography variant="body2" color="text.secondary">
                            Mentioned in {entity.article_count || 0} articles
                            {entity.confidence && ` • Confidence: ${(entity.confidence * 100).toFixed(1)}%`}
                          </Typography>
                        }
                      />
                    </ListItem>
                    {index < Math.min(entities.length, 20) - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            ) : (
              <div className="unified-content-text">
                No entities extracted yet. Run entity extraction to identify people, organizations, and locations.
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="unified-container">
      {/* Header */}
      <div className="unified-section">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Articles & Analysis
          </Typography>
          <Tooltip title="Refresh All Data">
            <IconButton onClick={loadData} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {loading && <CircularProgress sx={{ mb: 2 }} />}
      </div>

      {/* Tabs */}
      <div className="unified-section">
        <div className="unified-content-card unified-fade-in">
          <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
            <Tab label="Articles" icon={<ArticleIcon />} />
            <Tab label="Clusters" icon={<ClusterIcon />} />
            <Tab label="Entities" icon={<AutoAwesome />} />
          </Tabs>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 0 && renderArticlesTab()}
      {activeTab === 1 && renderClustersTab()}
      {activeTab === 2 && renderEntitiesTab()}

      {/* Article Dialog */}
      <Dialog 
        open={showArticleDialog} 
        onClose={handleCloseDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {selectedArticle?.title || 'Article Details'}
        </DialogTitle>
        <DialogContent>
          {selectedArticle && (
            <ArticleViewer 
              article={selectedArticle}
              onClose={handleCloseDialog}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Close</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default UnifiedArticlesAnalysis;
