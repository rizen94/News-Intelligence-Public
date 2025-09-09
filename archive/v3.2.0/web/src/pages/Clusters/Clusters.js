import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  Button,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Pagination,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Badge,
} from '@mui/material';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
  GroupWork as ClusterIcon,
  Visibility as ViewIcon,
  Article as ArticleIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
  ExpandMore as ExpandMoreIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Topic as TopicIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useNewsSystem } from '../../contexts/NewsSystemContext';
import Breadcrumb from '../../components/Breadcrumb/Breadcrumb';

export default function Clusters() {
  const { state, actions } = useNewsSystem();
  const { clusters } = state;
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(10);

  useEffect(() => {
    // Load clusters on component mount
    actions.fetchClusters();
  }, [actions]);

  const handleSearch = () => {
    // Filter clusters based on search query
    setCurrentPage(1);
  };

  const handleViewCluster = (cluster) => {
    setSelectedCluster(cluster);
    setViewDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setViewDialogOpen(false);
    setSelectedCluster(null);
  };

  const handleRefresh = () => {
    actions.fetchClusters();
  };

  const getEntityIcon = (type) => {
    switch (type) {
      case 'PERSON': return <PersonIcon fontSize="small" />;
      case 'ORG': return <BusinessIcon fontSize="small" />;
      case 'GPE': return <LocationIcon fontSize="small" />;
      default: return <ArticleIcon fontSize="small" />;
    }
  };

  const getEntityColor = (type) => {
    switch (type) {
      case 'PERSON': return 'primary';
      case 'ORG': return 'secondary';
      case 'GPE': return 'success';
      default: return 'default';
    }
  };

  const getCohesionColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  const getTopicColor = (topic) => {
    const colors = ['primary', 'secondary', 'success', 'info', 'warning'];
    const index = topic.length % colors.length;
    return colors[index];
  };

  const filteredClusters = clusters.list.filter(cluster => {
    if (searchQuery && !cluster.topic.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !cluster.summary.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  const paginatedClusters = filteredClusters.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPages = Math.ceil(filteredClusters.length / itemsPerPage);

  const ClusterCard = ({ cluster }) => (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="h6" component="div" sx={{ fontWeight: 500, lineHeight: 1.3 }}>
            {cluster.topic}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={`${cluster.articleCount} articles`}
              color="primary"
              size="small"
            />
            <Chip
              label={`${(cluster.cohesionScore * 100).toFixed(0)}% cohesion`}
              color={getCohesionColor(cluster.cohesionScore)}
              size="small"
            />
          </Box>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {cluster.summary}
          </Typography>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            Key Entities:
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {cluster.keyEntities && cluster.keyEntities.slice(0, 3).map((entity, index) => (
              <Chip
                key={index}
                icon={getEntityIcon(entity.type)}
                label={entity.text}
                size="small"
                color={getEntityColor(entity.type)}
                variant="outlined"
              />
            ))}
            {cluster.keyEntities && cluster.keyEntities.length > 3 && (
              <Chip
                label={`+${cluster.keyEntities.length - 3} more`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          <Chip
            icon={<TopicIcon />}
            label={cluster.category}
            size="small"
            variant="outlined"
            color={getTopicColor(cluster.category)}
          />
          <Chip
            icon={<TrendingUpIcon />}
            label={`${cluster.trendScore}% trending`}
            size="small"
            variant="outlined"
            color={cluster.trendScore > 50 ? 'success' : 'default'}
          />
          <Chip
            icon={<ScheduleIcon />}
            label={new Date(cluster.lastUpdated).toLocaleDateString()}
            size="small"
            variant="outlined"
          />
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 'auto' }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<ViewIcon />}
            onClick={() => handleViewCluster(cluster)}
          >
            View Details
          </Button>
          <Badge badgeContent={cluster.articleCount} color="primary">
            <ArticleIcon color="action" />
          </Badge>
        </Box>
      </CardContent>
    </Card>
  );

  const ClusterDetailDialog = () => (
    <Dialog
      open={viewDialogOpen}
      onClose={handleCloseDialog}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Cluster Details</Typography>
          <IconButton onClick={handleCloseDialog}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {selectedCluster && (
          <Box>
            <Typography variant="h5" gutterBottom sx={{ fontWeight: 'bold' }}>
              {selectedCluster.topic}
            </Typography>
            
            <Box sx={{ mb: 3 }}>
              <Typography variant="body1" paragraph>
                {selectedCluster.summary}
              </Typography>
            </Box>

            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Category
                </Typography>
                <Chip
                  label={selectedCluster.category}
                  color={getTopicColor(selectedCluster.category)}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Article Count
                </Typography>
                <Typography variant="body1">{selectedCluster.articleCount} articles</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Cohesion Score
                </Typography>
                <Chip
                  label={`${(selectedCluster.cohesionScore * 100).toFixed(0)}%`}
                  color={getCohesionColor(selectedCluster.cohesionScore)}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Trend Score
                </Typography>
                <Chip
                  label={`${selectedCluster.trendScore}%`}
                  color={selectedCluster.trendScore > 50 ? 'success' : 'default'}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Last Updated
                </Typography>
                <Typography variant="body1">
                  {new Date(selectedCluster.lastUpdated).toLocaleDateString()}
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Created Date
                </Typography>
                <Typography variant="body1">
                  {new Date(selectedCluster.createdDate).toLocaleDateString()}
                </Typography>
              </Grid>
            </Grid>

            {selectedCluster.keyEntities && selectedCluster.keyEntities.length > 0 && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>Key Entities</Typography>
                <Grid container spacing={1}>
                  {selectedCluster.keyEntities.map((entity, index) => (
                    <Grid item key={index}>
                      <Chip
                        icon={getEntityIcon(entity.type)}
                        label={entity.text}
                        color={getEntityColor(entity.type)}
                        variant="outlined"
                      />
                    </Grid>
                  ))}
                </Grid>
              </Box>
            )}

            {selectedCluster.articles && selectedCluster.articles.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="h6" gutterBottom>Sample Articles</Typography>
                <List dense>
                  {selectedCluster.articles.slice(0, 5).map((article, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        <ArticleIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText
                        primary={article.title}
                        secondary={article.source}
                      />
                    </ListItem>
                  ))}
                  {selectedCluster.articles.length > 5 && (
                    <ListItem>
                      <ListItemText
                        primary={`... and ${selectedCluster.articles.length - 5} more articles`}
                        color="text.secondary"
                      />
                    </ListItem>
                  )}
                </List>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCloseDialog}>Close</Button>
      </DialogActions>
    </Dialog>
  );

  return (
    <Box sx={{ p: 3 }}>
      {/* Breadcrumb Navigation */}
      <Breadcrumb />
      
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          Article Clusters
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={handleRefresh}
          disabled={clusters.loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Search */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={8}>
              <TextField
                fullWidth
                label="Search Clusters"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                InputProps={{
                  startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <Button
                variant="contained"
                onClick={handleSearch}
                fullWidth
                startIcon={<SearchIcon />}
              >
                Search
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="body1" color="text.secondary">
          Showing {filteredClusters.length} of {clusters.total} clusters
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Page {currentPage} of {totalPages}
        </Typography>
      </Box>

      {/* Loading State */}
      {clusters.loading && (
        <Box sx={{ mb: 2 }}>
          <LinearProgress />
        </Box>
      )}

      {/* Clusters Grid */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {paginatedClusters.map((cluster) => (
          <Grid item xs={12} md={6} lg={4} key={cluster.id}>
            <ClusterCard cluster={cluster} />
          </Grid>
        ))}
      </Grid>

      {/* No Results */}
      {filteredClusters.length === 0 && !clusters.loading && (
        <Card>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No clusters found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Try adjusting your search criteria
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination
            count={totalPages}
            page={currentPage}
            onChange={(e, page) => setCurrentPage(page)}
            color="primary"
            showFirstButton
            showLastButton
          />
        </Box>
      )}

      {/* Cluster Detail Dialog */}
      <ClusterDetailDialog />
    </Box>
  );
}
