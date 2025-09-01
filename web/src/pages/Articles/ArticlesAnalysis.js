import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
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
  Paper,
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
} from '@mui/icons-material';
import ArticleViewer from '../../components/ArticleViewer/ArticleViewer';

const ArticlesAnalysis = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [articles, setArticles] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [filters, setFilters] = useState({
    source: '',
    dateRange: '',
    priority: '',
    processed: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch articles
      const articlesResponse = await fetch('/api/articles');
      const articlesData = await articlesResponse.json();
      setArticles(articlesData.data || []);
      
      // Fetch clusters
      const clustersResponse = await fetch('/api/clusters');
      const clustersData = await clustersResponse.json();
      setClusters(clustersData.data || []);
      
      // Fetch entities
      const entitiesResponse = await fetch('/api/entities');
      const entitiesData = await entitiesResponse.json();
      setEntities(entitiesData.data || []);
      
    } catch (err) {
      setError('Failed to fetch data');
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    // Implement search functionality
    console.log('Searching for:', searchQuery);
  };

  const handleArticleClick = (article) => {
    setSelectedArticle(article);
    setViewerOpen(true);
  };

  const handleCloseViewer = () => {
    setViewerOpen(false);
    setSelectedArticle(null);
  };

  const filteredArticles = articles.filter(article => {
    if (searchQuery && !article.title.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (filters.source && article.source !== filters.source) {
      return false;
    }
    if (filters.processed && article.processed !== (filters.processed === 'true')) {
      return false;
    }
    return true;
  });

  const getEntityTypeIcon = (type) => {
    switch (type) {
      case 'PERSON': return <PersonIcon />;
      case 'ORG': return <BusinessIcon />;
      case 'GPE': return <LocationIcon />;
      default: return <PersonIcon />;
    }
  };

  const getEntityTypeColor = (type) => {
    switch (type) {
      case 'PERSON': return 'primary';
      case 'ORG': return 'secondary';
      case 'GPE': return 'success';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Articles & Analysis
        </Typography>
        <Button
          variant="contained"
          startIcon={<SearchIcon />}
          onClick={handleSearch}
        >
          Advanced Search
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Search and Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              placeholder="Search articles, entities, or topics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={filters.source}
                onChange={(e) => setFilters({...filters, source: e.target.value})}
                label="Source"
              >
                <MenuItem value="">All Sources</MenuItem>
                <MenuItem value="rss">RSS</MenuItem>
                <MenuItem value="api">API</MenuItem>
                <MenuItem value="manual">Manual</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.processed}
                onChange={(e) => setFilters({...filters, processed: e.target.value})}
                label="Status"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="true">Processed</MenuItem>
                <MenuItem value="false">Pending</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<FilterIcon />}
              onClick={() => setFilters({ source: '', dateRange: '', priority: '', processed: '' })}
            >
              Clear Filters
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
          indicatorColor="primary"
          textColor="primary"
        >
          <Tab 
            label={
              <Badge badgeContent={filteredArticles.length} color="primary">
                Articles
              </Badge>
            } 
            icon={<ArticleIcon />} 
          />
          <Tab 
            label={
              <Badge badgeContent={clusters.length} color="secondary">
                Clusters
              </Badge>
            } 
            icon={<ClusterIcon />} 
          />
          <Tab 
            label={
              <Badge badgeContent={entities.length} color="success">
                Entities
              </Badge>
            } 
            icon={<PersonIcon />} 
          />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {filteredArticles.map((article) => (
            <Grid item xs={12} md={6} lg={4} key={article.id}>
              <Card 
                sx={{ 
                  cursor: 'pointer',
                  '&:hover': { boxShadow: 4 }
                }}
                onClick={() => handleArticleClick(article)}
              >
                <CardContent>
                  <Typography variant="h6" gutterBottom noWrap>
                    {article.title || 'Untitled Article'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {article.source} • {new Date(article.published_at || Date.now()).toLocaleDateString()}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                    {article.processed ? (
                      <Chip label="Processed" color="success" size="small" />
                    ) : (
                      <Chip label="Pending" color="warning" size="small" />
                    )}
                    {article.priority && (
                      <Chip label={article.priority} color="primary" size="small" />
                    )}
                  </Box>
                  <Typography variant="body2" noWrap>
                    {article.summary || article.content?.substring(0, 100) + '...'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
          {filteredArticles.length === 0 && (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  No articles found
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Try adjusting your search or filters
                </Typography>
              </Paper>
            </Grid>
          )}
        </Grid>
      )}

      {activeTab === 1 && (
        <Grid container spacing={3}>
          {clusters.map((cluster) => (
            <Grid item xs={12} md={6} key={cluster.id}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {cluster.title || `Cluster ${cluster.id}`}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {cluster.article_count} articles • Similarity: {(cluster.similarity * 100).toFixed(1)}%
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {cluster.keywords?.slice(0, 5).map((keyword, index) => (
                      <Chip key={index} label={keyword} size="small" />
                    ))}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
          {clusters.length === 0 && (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  No clusters found
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Articles will be automatically clustered as they are processed
                </Typography>
              </Paper>
            </Grid>
          )}
        </Grid>
      )}

      {activeTab === 2 && (
        <Grid container spacing={3}>
          {entities.map((entity) => (
            <Grid item xs={12} sm={6} md={4} key={entity.id}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    {getEntityTypeIcon(entity.type)}
                    <Chip 
                      label={entity.type} 
                      color={getEntityTypeColor(entity.type)} 
                      size="small" 
                      sx={{ ml: 1 }}
                    />
                  </Box>
                  <Typography variant="h6" gutterBottom>
                    {entity.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Mentioned in {entity.mention_count} articles
                  </Typography>
                  {entity.description && (
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {entity.description}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          ))}
          {entities.length === 0 && (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  No entities found
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Entities will be extracted as articles are processed
                </Typography>
              </Paper>
            </Grid>
          )}
        </Grid>
      )}

      {/* Article Viewer Dialog */}
      <Dialog
        open={viewerOpen}
        onClose={handleCloseViewer}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">
              {selectedArticle?.title || 'Article Viewer'}
            </Typography>
            <IconButton onClick={handleCloseViewer}>
              <ViewIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedArticle && (
            <ArticleViewer 
              article={selectedArticle}
              onClose={handleCloseViewer}
            />
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default ArticlesAnalysis;
