import {
  Article,
  Search,
  OpenInNew as ViewIcon,
  AutoAwesome,
  Refresh,
  TrendingUp as TrendingUpIcon,
  GroupWork as ClusterIcon,
  Business as BusinessIcon,
  FilterList,
  Person as PersonIcon,
  LocationOn as LocationIcon,
  Schedule,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  Chip,
  IconButton,
  Tooltip,
  Grid,
  Container,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  InputAdornment,
  CircularProgress,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Paper,
  Tabs,
  Tab,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import ArticleViewer from '../../components/ArticleViewer/ArticleViewer';
import newsSystemService from '../../services/newsSystemService';

const NewsStyleArticles = () => {
  const [articles, setArticles] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [sortBy, setSortBy] = useState('newest');

  // Article dialog
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [showArticleDialog, setShowArticleDialog] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async() => {
    try {
      setLoading(true);
      setError(null);

      const [articlesData, clustersData, entitiesData] = await Promise.all([
        newsSystemService.getArticles(),
        newsSystemService.getClusters(),
        newsSystemService.getEntities(),
      ]);

      if (articlesData.success) {
        setArticles(articlesData.articles || []);
      }
      if (clustersData.success) {
        setClusters(clustersData.clusters || []);
      }
      if (entitiesData.success) {
        setEntities(entitiesData.entities || []);
      }
    } catch (err) {
      setError(`Failed to load data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getFilteredArticles = () => {
    let filtered = articles;

    if (searchQuery) {
      filtered = filtered.filter(
        article =>
          article.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          article.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          article.summary?.toLowerCase().includes(searchQuery.toLowerCase()),
      );
    }

    if (filterCategory) {
      filtered = filtered.filter(
        article => article.category === filterCategory,
      );
    }

    if (filterSource) {
      filtered = filtered.filter(article => article.source === filterSource);
    }

    // Sort articles
    switch (sortBy) {
    case 'newest':
      filtered.sort(
        (a, b) => new Date(b.publishedDate) - new Date(a.publishedDate),
      );
      break;
    case 'oldest':
      filtered.sort(
        (a, b) => new Date(a.publishedDate) - new Date(b.publishedDate),
      );
      break;
    case 'title':
      filtered.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
      break;
    case 'source':
      filtered.sort((a, b) => (a.source || '').localeCompare(b.source || ''));
      break;
    }

    return filtered;
  };

  const getGroupedArticles = () => {
    const filtered = getFilteredArticles();
    const grouped = {};

    filtered.forEach(article => {
      const topic = article.category || 'General';
      if (!grouped[topic]) {
        grouped[topic] = [];
      }
      grouped[topic].push(article);
    });

    return grouped;
  };

  const getUniqueCategories = () => {
    return Array.from(new Set(articles.map(a => a.category).filter(Boolean)));
  };

  const getUniqueSources = () => {
    return Array.from(new Set(articles.map(a => a.source).filter(Boolean)));
  };

  const handleArticleClick = article => {
    setSelectedArticle(article);
    setShowArticleDialog(true);
  };

  const handleCloseDialog = () => {
    setShowArticleDialog(false);
    setSelectedArticle(null);
  };

  const renderNewsGrid = () => {
    const groupedArticles = getGroupedArticles();
    const topics = Object.keys(groupedArticles);

    if (topics.length === 0) {
      return (
        <Box display='flex' flexDirection='column' alignItems='center' py={8}>
          <Article sx={{ fontSize: 80, color: 'action.disabled', mb: 2 }} />
          <Typography variant='h5' color='textSecondary' gutterBottom>
            No articles found
          </Typography>
          <Typography variant='body1' color='textSecondary' textAlign='center'>
            Try adjusting your filters or refresh the data
          </Typography>
        </Box>
      );
    }

    return (
      <Box>
        {topics.map((topic, topicIndex) => (
          <Box key={topic} sx={{ mb: 4 }}>
            {/* Topic Header */}
            <Box sx={{ mb: 3 }}>
              <Typography
                variant='h4'
                component='h2'
                sx={{
                  fontWeight: 'bold',
                  color: 'primary.main',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                }}
              >
                <ClusterIcon />
                {topic}
                <Chip
                  label={`${groupedArticles[topic].length} articles`}
                  size='small'
                  color='primary'
                  variant='outlined'
                />
              </Typography>
              <Divider sx={{ mt: 1 }} />
            </Box>

            {/* Articles Grid */}
            <Grid container spacing={3}>
              {groupedArticles[topic].map((article, index) => (
                <Grid
                  item
                  xs={12}
                  sm={6}
                  md={4}
                  lg={3}
                  key={article.id || index}
                >
                  <Card
                    sx={{
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: 4,
                      },
                    }}
                    onClick={() => handleArticleClick(article)}
                  >
                    <CardContent sx={{ flexGrow: 1, pb: 1 }}>
                      {/* Article Title */}
                      <Typography
                        variant='h6'
                        component='h3'
                        sx={{
                          fontWeight: 'bold',
                          lineHeight: 1.3,
                          mb: 2,
                          color: 'primary.main',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {article.title || 'Untitled Article'}
                      </Typography>

                      {/* Article Meta */}
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          mb: 2,
                          flexWrap: 'wrap',
                        }}
                      >
                        {article.source && (
                          <Chip
                            label={article.source}
                            size='small'
                            variant='outlined'
                            color='primary'
                          />
                        )}
                        {article.processingStatus === 'processed' && (
                          <Chip
                            label='Processed'
                            size='small'
                            color='success'
                            variant='filled'
                          />
                        )}
                      </Box>

                      {/* Article Summary */}
                      <Typography
                        variant='body2'
                        color='text.secondary'
                        sx={{
                          display: '-webkit-box',
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          lineHeight: 1.4,
                        }}
                      >
                        {article.summary ||
                          article.content?.substring(0, 150) + '...'}
                      </Typography>
                    </CardContent>

                    <CardActions
                      sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}
                    >
                      <Typography variant='caption' color='text.secondary'>
                        {article.publishedDate
                          ? new Date(article.publishedDate).toLocaleDateString()
                          : 'No date'}
                      </Typography>
                      <Box>
                        {article.url && article.url !== '#' && (
                          <Tooltip title='Open Original Article'>
                            <IconButton
                              size='small'
                              onClick={e => {
                                e.stopPropagation();
                                window.open(article.url, '_blank');
                              }}
                            >
                              <ViewIcon fontSize='small' />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title='View Full Analysis'>
                          <IconButton
                            size='small'
                            onClick={e => {
                              e.stopPropagation();
                              handleArticleClick(article);
                            }}
                          >
                            <AutoAwesome fontSize='small' />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        ))}
      </Box>
    );
  };

  const renderStatsTab = () => (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={2}>
                <Article sx={{ fontSize: 40, color: 'primary.main' }} />
                <Box>
                  <Typography variant='h4' fontWeight='bold'>
                    {articles.length}
                  </Typography>
                  <Typography variant='body2' color='textSecondary'>
                    Total Articles
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={2}>
                <ClusterIcon sx={{ fontSize: 40, color: 'secondary.main' }} />
                <Box>
                  <Typography variant='h4' fontWeight='bold'>
                    {Object.keys(getGroupedArticles()).length}
                  </Typography>
                  <Typography variant='body2' color='textSecondary'>
                    Topics
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={2}>
                <BusinessIcon sx={{ fontSize: 40, color: 'warning.main' }} />
                <Box>
                  <Typography variant='h4' fontWeight='bold'>
                    {entities.length}
                  </Typography>
                  <Typography variant='body2' color='textSecondary'>
                    Entities
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display='flex' alignItems='center' gap={2}>
                <TrendingUpIcon sx={{ fontSize: 40, color: 'success.main' }} />
                <Box>
                  <Typography variant='h4' fontWeight='bold'>
                    {new Date().toLocaleDateString()}
                  </Typography>
                  <Typography variant='body2' color='textSecondary'>
                    Last Updated
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  if (loading) {
    return (
      <Container maxWidth='xl' sx={{ py: 4 }}>
        <Box
          display='flex'
          justifyContent='center'
          alignItems='center'
          minHeight='400px'
        >
          <CircularProgress size={60} />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth='xl' sx={{ py: 2 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box
          display='flex'
          justifyContent='space-between'
          alignItems='center'
          mb={2}
        >
          <Typography variant='h3' component='h1' fontWeight='bold'>
            News Intelligence Dashboard
          </Typography>
          <Button
            variant='outlined'
            startIcon={<Refresh />}
            onClick={loadData}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>

        {error && (
          <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </Box>

      {/* Tabs */}
      <Box sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
        >
          <Tab label='News Grid' icon={<Article />} />
          <Tab label='Statistics' icon={<TrendingUpIcon />} />
        </Tabs>
      </Box>

      {/* Filters */}
      {activeTab === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant='h6' gutterBottom>
            <FilterList sx={{ mr: 1, verticalAlign: 'middle' }} />
            Filters
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                size='small'
                label='Search Articles'
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position='start'>
                      <Search />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size='small'>
                <InputLabel>Category</InputLabel>
                <Select
                  value={filterCategory}
                  label='Category'
                  onChange={e => setFilterCategory(e.target.value)}
                >
                  <MenuItem value=''>All Categories</MenuItem>
                  {getUniqueCategories().map(category => (
                    <MenuItem key={category} value={category}>
                      {category}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size='small'>
                <InputLabel>Source</InputLabel>
                <Select
                  value={filterSource}
                  label='Source'
                  onChange={e => setFilterSource(e.target.value)}
                >
                  <MenuItem value=''>All Sources</MenuItem>
                  {getUniqueSources().map(source => (
                    <MenuItem key={source} value={source}>
                      {source}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size='small'>
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={sortBy}
                  label='Sort By'
                  onChange={e => setSortBy(e.target.value)}
                >
                  <MenuItem value='newest'>Newest First</MenuItem>
                  <MenuItem value='oldest'>Oldest First</MenuItem>
                  <MenuItem value='title'>Title A-Z</MenuItem>
                  <MenuItem value='source'>Source A-Z</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Tab Content */}
      {activeTab === 0 && renderNewsGrid()}
      {activeTab === 1 && renderStatsTab()}

      {/* Article Dialog */}
      <Dialog
        open={showArticleDialog}
        onClose={handleCloseDialog}
        maxWidth='lg'
        fullWidth
      >
        <DialogTitle>{selectedArticle?.title || 'Article Details'}</DialogTitle>
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
    </Container>
  );
};

export default NewsStyleArticles;
