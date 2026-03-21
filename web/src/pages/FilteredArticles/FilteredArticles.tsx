/**
 * Filtered Articles Management Page
 * Displays articles that would be filtered by current RSS collector criteria
 * Allows users to review and delete filtered articles
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Paper,
  Chip,
  Button,
  IconButton,
  Tooltip,
  Alert,
  TextField,
  InputAdornment,
  Checkbox,
  FormControlLabel,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
} from '@mui/material';
import {
  Search,
  Delete,
  Refresh,
  Warning,
  CheckCircle,
  FilterList,
  DeleteSweep,
} from '@mui/icons-material';

import apiService from '../../services/apiService';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { useNotification } from '../../hooks/useNotification';
import LoadingState from '../../components/shared/LoadingState';
import EmptyState from '../../components/shared/EmptyState';

interface FilteredArticle {
  article_id: number;
  title: string;
  source: string;
  source_domain?: string;
  url: string;
  reasons: string[];
  quality_score: number;
  impact_score: number;
  schema: string;
  created_at: string | null;
}

interface AnalysisData {
  summary: {
    total_articles: number;
    total_filtered: number;
    filtered_percentage: number;
    total_passing: number;
    passing_percentage: number;
  };
  by_domain: Record<string, any>;
  top_sources: Array<{ source: string; count: number }>;
  sample_articles: FilteredArticle[];
  total_filtered_articles: number;
}

const FilteredArticles: React.FC = () => {
  const { domain } = useDomainRoute();
  const { showSuccess, showError, showWarning, NotificationComponent } =
    useNotification();

  // State
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [filteredArticles, setFilteredArticles] = useState<FilteredArticle[]>(
    []
  );
  const [selectedArticles, setSelectedArticles] = useState<Set<number>>(
    new Set()
  );
  const [deleting, setDeleting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Filters
  const [sourceFilter, setSourceFilter] = useState('');
  const [limit, setLimit] = useState(1000);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // Load analysis
  const loadAnalysis = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const params: any = { limit, sample_size: 100 };
      if (sourceFilter) {
        params.source = sourceFilter;
      }

      const response = await apiService.analyzeArticles(params);

      if (response.success) {
        setAnalysisData(response.data);
        setFilteredArticles(response.data.sample_articles || []);
      } else {
        setError(response.error || 'Failed to analyze articles');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to analyze articles');
      showError('Failed to analyze articles');
    } finally {
      setAnalyzing(false);
    }
  }, [sourceFilter, limit, showError]);

  useEffect(() => {
    loadAnalysis();
  }, []);

  // Handle selection
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedArticles(new Set(filteredArticles.map(a => a.article_id)));
    } else {
      setSelectedArticles(new Set());
    }
  };

  const handleSelectArticle = (articleId: number, checked: boolean) => {
    const newSelected = new Set(selectedArticles);
    if (checked) {
      newSelected.add(articleId);
    } else {
      newSelected.delete(articleId);
    }
    setSelectedArticles(newSelected);
  };

  // Delete articles
  const handleDeleteSelected = async () => {
    if (selectedArticles.size === 0) {
      showWarning('No articles selected');
      return;
    }

    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      const articleIds = Array.from(selectedArticles);

      // Group by domain/schema
      const bySchema: Record<string, number[]> = {};
      filteredArticles.forEach(article => {
        if (articleIds.includes(article.article_id)) {
          if (!bySchema[article.schema]) {
            bySchema[article.schema] = [];
          }
          bySchema[article.schema].push(article.article_id);
        }
      });

      // Delete from each domain
      let totalDeleted = 0;
      for (const [schema, ids] of Object.entries(bySchema)) {
        const domainKey = schema.replace('_', '-');
        const response = await apiService.deleteArticlesBulk(ids, domainKey);
        if (response.success) {
          totalDeleted += response.deleted_count || ids.length;
        }
      }

      showSuccess(`Deleted ${totalDeleted} article(s) successfully`);
      setSelectedArticles(new Set());
      setDeleteDialogOpen(false);

      // Reload analysis
      await loadAnalysis();
    } catch (err: any) {
      showError(err.message || 'Failed to delete articles');
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteSingle = async (article: FilteredArticle) => {
    try {
      const domainKey = article.schema.replace('_', '-');
      const response = await apiService.deleteArticle(
        article.article_id,
        domainKey
      );

      if (response.success) {
        showSuccess('Article deleted successfully');
        // Remove from list
        setFilteredArticles(prev =>
          prev.filter(a => a.article_id !== article.article_id)
        );
        // Reload analysis
        await loadAnalysis();
      } else {
        showError(response.error || 'Failed to delete article');
      }
    } catch (err: any) {
      showError(err.message || 'Failed to delete article');
    }
  };

  const getReasonColor = (reason: string) => {
    if (reason === 'excluded_content') return 'error';
    if (reason === 'clickbait') return 'warning';
    if (reason === 'advertisement') return 'info';
    if (reason.startsWith('low_quality')) return 'default';
    if (reason.startsWith('low_impact')) return 'default';
    return 'default';
  };

  const getReasonLabel = (reason: string) => {
    if (reason === 'excluded_content') return 'Excluded Content';
    if (reason === 'clickbait') return 'Clickbait';
    if (reason === 'advertisement') return 'Advertisement';
    if (reason.startsWith('low_quality_')) {
      const score = reason.split('_')[2];
      return `Low Quality (${score})`;
    }
    if (reason.startsWith('low_impact_')) {
      const score = reason.split('_')[2];
      return `Low Impact (${score})`;
    }
    return reason;
  };

  return (
    <Box>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Box>
          <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
            Filtered Articles Review
          </Typography>
          <Typography variant='body1' color='text.secondary'>
            Review and manage articles that would be filtered by current
            criteria
          </Typography>
        </Box>
        <Box display='flex' gap={2}>
          <Button
            variant='outlined'
            startIcon={<Refresh />}
            onClick={loadAnalysis}
            disabled={analyzing}
          >
            Refresh
          </Button>
          {selectedArticles.size > 0 && (
            <Button
              variant='contained'
              color='error'
              startIcon={<DeleteSweep />}
              onClick={handleDeleteSelected}
              disabled={deleting}
            >
              Delete Selected ({selectedArticles.size})
            </Button>
          )}
        </Box>
      </Box>

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems='center'>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label='Filter by Source'
                value={sourceFilter}
                onChange={e => setSourceFilter(e.target.value)}
                placeholder='e.g., telegraph'
                InputProps={{
                  startAdornment: (
                    <InputAdornment position='start'>
                      <Search />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label='Limit per Domain'
                type='number'
                value={limit}
                onChange={e => setLimit(parseInt(e.target.value) || 1000)}
                inputProps={{ min: 1, max: 10000 }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <Button
                fullWidth
                variant='contained'
                onClick={loadAnalysis}
                disabled={analyzing}
                startIcon={
                  analyzing ? <CircularProgress size={20} /> : <FilterList />
                }
              >
                {analyzing ? 'Analyzing...' : 'Run Analysis'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Summary Statistics */}
      {analysisData && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant='h6' color='text.secondary'>
                  Total Articles
                </Typography>
                <Typography variant='h4' sx={{ fontWeight: 'bold' }}>
                  {analysisData.summary.total_articles.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card sx={{ bgcolor: 'error.light', color: 'error.contrastText' }}>
              <CardContent>
                <Typography variant='h6'>Filtered Articles</Typography>
                <Typography variant='h4' sx={{ fontWeight: 'bold' }}>
                  {analysisData.summary.total_filtered.toLocaleString()}
                </Typography>
                <Typography variant='body2'>
                  {analysisData.summary.filtered_percentage}% of total
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card
              sx={{ bgcolor: 'success.light', color: 'success.contrastText' }}
            >
              <CardContent>
                <Typography variant='h6'>Passing Articles</Typography>
                <Typography variant='h4' sx={{ fontWeight: 'bold' }}>
                  {analysisData.summary.total_passing.toLocaleString()}
                </Typography>
                <Typography variant='body2'>
                  {analysisData.summary.passing_percentage}% of total
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant='h6' color='text.secondary'>
                  Sample Size
                </Typography>
                <Typography variant='h4' sx={{ fontWeight: 'bold' }}>
                  {filteredArticles.length}
                </Typography>
                <Typography variant='body2'>
                  Showing sample of filtered articles
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Top Sources */}
      {analysisData && analysisData.top_sources.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Top Sources with Filtered Articles
            </Typography>
            <Box display='flex' flexWrap='wrap' gap={1}>
              {analysisData.top_sources.slice(0, 10).map(source => (
                <Chip
                  key={source.source}
                  label={`${source.source}: ${source.count}`}
                  onClick={() => setSourceFilter(source.source)}
                  color={sourceFilter === source.source ? 'primary' : 'default'}
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Alert severity='error' sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading */}
      {analyzing && (
        <Box sx={{ mb: 3 }}>
          <LinearProgress />
          <Typography
            variant='body2'
            color='text.secondary'
            sx={{ mt: 1, textAlign: 'center' }}
          >
            Analyzing articles... This may take a moment.
          </Typography>
        </Box>
      )}

      {/* Articles Table */}
      {!analyzing && (
        <>
          {filteredArticles.length === 0 ? (
            <EmptyState
              title='No Filtered Articles Found'
              message={
                sourceFilter
                  ? `No filtered articles found for source "${sourceFilter}". Try a different source or remove the filter.`
                  : 'No articles match the current filtering criteria. This is good!'
              }
            />
          ) : (
            <Card>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell padding='checkbox'>
                        <Checkbox
                          checked={
                            selectedArticles.size === filteredArticles.length &&
                            filteredArticles.length > 0
                          }
                          indeterminate={
                            selectedArticles.size > 0 &&
                            selectedArticles.size < filteredArticles.length
                          }
                          onChange={e => handleSelectAll(e.target.checked)}
                        />
                      </TableCell>
                      <TableCell>Title</TableCell>
                      <TableCell>Source</TableCell>
                      <TableCell>Reasons</TableCell>
                      <TableCell>Quality</TableCell>
                      <TableCell>Impact</TableCell>
                      <TableCell>Domain</TableCell>
                      <TableCell align='right'>Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filteredArticles
                      .slice(
                        page * rowsPerPage,
                        page * rowsPerPage + rowsPerPage
                      )
                      .map(article => (
                        <TableRow
                          key={article.article_id}
                          hover
                          sx={{
                            bgcolor: selectedArticles.has(article.article_id)
                              ? 'action.selected'
                              : 'inherit',
                          }}
                        >
                          <TableCell padding='checkbox'>
                            <Checkbox
                              checked={selectedArticles.has(article.article_id)}
                              onChange={e =>
                                handleSelectArticle(
                                  article.article_id,
                                  e.target.checked
                                )
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Typography
                              variant='body2'
                              sx={{
                                fontWeight: 'medium',
                                maxWidth: 400,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {article.title}
                            </Typography>
                            {article.url && (
                              <Typography
                                variant='caption'
                                color='text.secondary'
                                sx={{
                                  display: 'block',
                                  maxWidth: 400,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {article.url}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            {article.source || article.source_domain || '—'}
                          </TableCell>
                          <TableCell>
                            <Box display='flex' flexWrap='wrap' gap={0.5}>
                              {article.reasons.map(reason => (
                                <Chip
                                  key={reason}
                                  label={getReasonLabel(reason)}
                                  size='small'
                                  color={getReasonColor(reason) as any}
                                />
                              ))}
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Typography
                              variant='body2'
                              color={
                                article.quality_score < 0.4
                                  ? 'error'
                                  : 'text.secondary'
                              }
                            >
                              {article.quality_score.toFixed(2)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography
                              variant='body2'
                              color={
                                article.impact_score < 0.4
                                  ? 'error'
                                  : 'text.secondary'
                              }
                            >
                              {article.impact_score.toFixed(2)}
                            </Typography>
                          </TableCell>
                          <TableCell>{article.schema}</TableCell>
                          <TableCell align='right'>
                            <Tooltip title='Delete Article'>
                              <IconButton
                                size='small'
                                color='error'
                                onClick={() => handleDeleteSingle(article)}
                              >
                                <Delete />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <TablePagination
                component='div'
                count={filteredArticles.length}
                page={page}
                onPageChange={(_, newPage) => setPage(newPage)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={e => {
                  setRowsPerPage(parseInt(e.target.value, 10));
                  setPage(0);
                }}
                rowsPerPageOptions={[10, 25, 50, 100]}
              />
            </Card>
          )}
        </>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete {selectedArticles.size} article(s)?
            This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setDeleteDialogOpen(false)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            onClick={confirmDelete}
            color='error'
            variant='contained'
            disabled={deleting}
            startIcon={deleting ? <CircularProgress size={20} /> : <Delete />}
          >
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      <NotificationComponent />
    </Box>
  );
};

export default FilteredArticles;
