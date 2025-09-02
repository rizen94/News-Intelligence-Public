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
  AutoAwesome,
  Build as BuildIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import ArticleViewer from '../../components/ArticleViewer/ArticleViewer';
import newsSystemService from '../../services/newsSystemService';

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
          return new Date(b.publishedDate) - new Date(a.publishedDate);
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
        {/* Article Stats */}
        <div className="unified-content-card unified-fade-in">
          <div className="unified-content-header">
            <ArticleIcon sx={{ mr: 1 }} />
            <div className="unified-content-title">Article Overview</div>
          </div>
          <div className="unified-content-body">
            <div className="unified-grid unified-grid-4">
              <div className="unified-stat-card">
                <div className="unified-stat-card-content">
                  <ArticleIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                  <Typography variant="h4" fontWeight="bold">{articles.length}</Typography>
                  <Typography variant="body2" color="textSecondary">Total Articles</Typography>
                </div>
              </div>
              <div className="unified-stat-card">
                <div className="unified-stat-card-content">
                  <ClusterIcon sx={{ fontSize: 40, color: 'secondary.main' }} />
                  <Typography variant="h4" fontWeight="bold">{clusters.length}</Typography>
                  <Typography variant="body2" color="textSecondary">Story Clusters</Typography>
                </div>
              </div>
              <div className="unified-stat-card">
                <div className="unified-stat-card-content">
                  <BusinessIcon sx={{ fontSize: 40, color: 'warning.main' }} />
                  <Typography variant="h4" fontWeight="bold">{entities.length}</Typography>
                  <Typography variant="body2" color="textSecondary">Entities</Typography>
                </div>
              </div>
              <div className="unified-stat-card">
                <div className="unified-stat-card-content">
                  <TrendingUpIcon sx={{ fontSize: 40, color: 'success.main' }} />
                  <Typography variant="h4" fontWeight="bold">{new Date().toLocaleDateString()}</Typography>
                  <Typography variant="body2" color="textSecondary">Last Updated</Typography>
                </div>
              </div>
            </div>
          </div>
        </div>

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
            {filteredArticles.length === 0 ? (
              <Box textAlign="center" py={4}>
                <ArticleIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" color="text.secondary">
                  No articles found
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Try adjusting your filters or refresh the data
                </Typography>
              </Box>
            ) : (
              <List>
                {filteredArticles.map((article, index) => (
                  <React.Fragment key={article.id || index}>
                    <ListItem 
                      sx={{ 
                        '&:hover': { backgroundColor: 'action.hover' },
                        cursor: 'pointer',
                        borderRadius: 1,
                        mb: 1
                      }}
                      onClick={() => handleArticleClick(article)}
                    >
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1} mb={1}>
                            <Typography variant="subtitle1" fontWeight="medium" color="primary.main">
                              {article.title || 'Untitled Article'}
                            </Typography>
                            {article.category && (
                              <Chip label={article.category} size="small" color="primary" variant="outlined" />
                            )}
                            {article.processingStatus === 'processed' && (
                              <Chip label="Processed" size="small" color="success" variant="outlined" />
                            )}
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              {article.summary || article.content?.substring(0, 200) + '...'}
                            </Typography>
                            <Box display="flex" justifyContent="space-between" alignItems="center">
                              <Box display="flex" gap={1} alignItems="center">
                                {article.source && (
                                  <Chip label={article.source} size="small" variant="outlined" />
                                )}
                                <Typography variant="caption" color="text.secondary">
                                  {article.publishedDate ? new Date(article.publishedDate).toLocaleDateString() : 'No date'}
                                </Typography>
                              </Box>
                              <Box display="flex" gap={1}>
                                {article.url && article.url !== '#' && (
                                  <Tooltip title="Open Original Article">
                                    <IconButton 
                                      size="small" 
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        window.open(article.url, '_blank');
                                      }}
                                    >
                                      <ViewIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                )}
                                <Tooltip title="View Full Analysis">
                                  <IconButton 
                                    size="small" 
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleArticleClick(article);
                                    }}
                                  >
                                    <AutoAwesome fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            </Box>
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < filteredArticles.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderDailyDigestTab = () => {
    const today = new Date().toISOString().split('T')[0];
    const todayArticles = articles.filter(article => 
      article.publishedDate && article.publishedDate.startsWith(today)
    );
    const processedToday = todayArticles.filter(article => 
      article.processingStatus === 'completed' || article.processingStatus === 'processed'
    );
    const pendingToday = todayArticles.filter(article => 
      article.processingStatus === 'pending'
    );

    return (
      <div className="unified-section">
        <div className="unified-grid unified-grid-3">
          {/* Today's Summary */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <TrendingUpIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Today's Summary</div>
            </div>
            <div className="unified-content-body">
              <div className="unified-content-text">
                <strong>{todayArticles.length}</strong> articles collected today
                <br />
                <strong>{processedToday.length}</strong> articles processed
                <br />
                <strong>{pendingToday.length}</strong> articles pending
                <br />
                <strong>{Math.round((processedToday.length / todayArticles.length) * 100) || 0}%</strong> processing rate
              </div>
            </div>
          </div>

          {/* Processed Articles */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <ArticleIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Processed Today</div>
            </div>
            <div className="unified-content-body">
              {processedToday.length > 0 ? (
                <List>
                  {processedToday.slice(0, 5).map((article) => (
                    <ListItem key={article.id} button onClick={() => handleArticleClick(article)}>
                      <ListItemText
                        primary={article.title}
                        secondary={`${article.source} • ${new Date(article.publishedDate).toLocaleTimeString()}`}
                      />
                    </ListItem>
                  ))}
                  {processedToday.length > 5 && (
                    <ListItem>
                      <ListItemText primary={`... and ${processedToday.length - 5} more`} />
                    </ListItem>
                  )}
                </List>
              ) : (
                <div className="unified-content-text">No articles processed today yet.</div>
              )}
            </div>
          </div>

          {/* Pending Articles */}
          <div className="unified-content-card unified-fade-in">
            <div className="unified-content-header">
              <BuildIcon sx={{ mr: 1 }} />
              <div className="unified-content-title">Pending Processing</div>
            </div>
            <div className="unified-content-body">
              {pendingToday.length > 0 ? (
                <List>
                  {pendingToday.slice(0, 5).map((article) => (
                    <ListItem key={article.id} button onClick={() => handleArticleClick(article)}>
                      <ListItemText
                        primary={article.title}
                        secondary={`${article.source} • ${new Date(article.publishedDate).toLocaleTimeString()}`}
                      />
                    </ListItem>
                  ))}
                  {pendingToday.length > 5 && (
                    <ListItem>
                      <ListItemText primary={`... and ${pendingToday.length - 5} more`} />
                    </ListItem>
                  )}
                </List>
              ) : (
                <div className="unified-content-text">All articles processed!</div>
              )}
            </div>
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
    <div className="unified-container-fluid">
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
            <Tab label="Daily Digest" icon={<TrendingUpIcon />} />
            <Tab label="Clusters" icon={<ClusterIcon />} />
            <Tab label="Entities" icon={<AutoAwesome />} />
          </Tabs>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 0 && renderArticlesTab()}
      {activeTab === 1 && renderDailyDigestTab()}
      {activeTab === 2 && renderClustersTab()}
      {activeTab === 3 && renderEntitiesTab()}

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
