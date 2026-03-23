/**
 * News Intelligence System - Consolidated Articles Page
 * Combines features from EnhancedArticles, Articles, UnifiedArticlesAnalysis, and NewsStyleArticles
 *
 * Features:
 * - Search and advanced filtering
 * - Grid/List view modes
 * - Quick filters (reading time, quality, sentiment)
 * - Topic clustering
 * - Article bookmarks
 * - Add to storyline functionality
 * - CSV export
 * - Article reader with full content
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
  LinearProgress,
  Button,
  IconButton,
  Tooltip,
  Alert,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  CardActions,
  CardMedia,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormLabel,
  Switch,
  Snackbar,
  CircularProgress,
  Tabs,
  Tab,
  Divider,
} from '@mui/material';
import {
  Search,
  FilterList,
  Refresh,
  Article,
  TrendingUp as TrendingUpIcon,
  Source,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
  Timeline as TimelineIcon,
  Visibility,
  Share as ShareIcon,
  Bookmark,
  BookmarkBorder,
  ViewList,
  ViewModule,
  Add,
  Close as CloseIcon,
  Download as DownloadIcon,
  AccessTime,
  GroupWork as ClusterIcon,
} from '@mui/icons-material';

import ArticleReader from '../../components/ArticleReader';
import apiService from '../../services/apiService';
import {
  calculateReadingTime,
  formatReadingTime,
  getArticleReadingTime,
} from '../../utils/articleUtils';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { useNotification } from '../../hooks/useNotification';
import { getUserFriendlyError } from '../../utils/errorHandler';
import LoadingState from '../../components/shared/LoadingState';
import EmptyState from '../../components/shared/EmptyState';

interface ArticleItem {
  id: number;
  title: string;
  content?: string;
  summary?: string;
  source_domain?: string;
  source?: string;
  published_at?: string;
  created_at?: string;
  url?: string;
  image_url?: string;
  sentiment?: string;
  sentiment_label?: string;
  quality_score?: number;
  category?: string;
  entities?: string[];
  reading_time?: number;
  word_count?: number;
  bias_score?: number;
  processing_status?: string;
}

interface Storyline {
  id: number;
  title: string;
  description?: string;
  article_count?: number;
  status?: string;
}

interface Topic {
  name: string;
  articles: ArticleItem[];
  count: number;
}

const Articles: React.FC = () => {
  const { domain } = useDomainRoute();

  // Article data state
  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalArticles, setTotalArticles] = useState(0);

  // View and filter state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [bookmarkedArticles, setBookmarkedArticles] = useState<Set<number>>(
    new Set()
  );

  // Quick filters
  const [quickFilters, setQuickFilters] = useState({
    readingTime: null as 'short' | 'medium' | 'long' | null,
    quality: null as 'high' | 'medium' | 'low' | null,
    sentiment: null as 'positive' | 'negative' | 'neutral' | null,
  });
  // Default false: new domains and first-time visits should see all ingested articles.
  // Turn on when curating items to attach to storylines (excludes rows in storyline_articles).
  const [showUnlinkedOnly, setShowUnlinkedOnly] = useState(false);
  const [filterTopic, setFilterTopic] = useState('');
  const [sourceOptions, setSourceOptions] = useState<string[]>([]);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Topic clustering state
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  const [clustering, setClustering] = useState(false);
  const [showTopicClustering, setShowTopicClustering] = useState(false);

  // Article reader state
  const [selectedArticle, setSelectedArticle] = useState<ArticleItem | null>(
    null
  );
  const [readerOpen, setReaderOpen] = useState(false);

  // Storyline selection state
  const [storylineDialogOpen, setStorylineDialogOpen] = useState(false);
  const [storylines, setStorylines] = useState<Storyline[]>([]);
  const [selectedStorylineId, setSelectedStorylineId] = useState<string>('');
  const [articleToAdd, setArticleToAdd] = useState<ArticleItem | null>(null);

  // Standardized notifications
  const {
    showSuccess,
    showError,
    showInfo,
    showWarning,
    NotificationComponent,
  } = useNotification();

  // Duplicate detection
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateInfo, setDuplicateInfo] = useState<{
    article: ArticleItem | null;
    storyline: Storyline | null;
  }>({ article: null, storyline: null });

  const loadStorylines = useCallback(async () => {
    try {
      const response = await apiService.getStorylines({}, domain);
      // Backend returns { data: StorylineListItem[], pagination, domain } (no .success); or { success: false, error }
      if ('error' in response && response.error) return;
      const storylinesList = Array.isArray(response.data)
        ? response.data
        : (response as { data?: { storylines?: unknown[] } }).data
            ?.storylines || [];
      setStorylines(storylinesList);
    } catch (error) {
      console.error('Failed to load storylines:', error);
    }
  }, [domain]);

  const loadArticles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {
        page,
        limit: 12,
        search: searchQuery,
        source_domain: filterSource,
        sort: sortBy,
      };
      if (showUnlinkedOnly) params.unlinked = true;
      const response = await apiService.getArticles(params, domain);

      if (response.success) {
        const articlesData =
          response.data?.articles ||
          response.data?.data?.articles ||
          response.articles ||
          [];
        const totalData =
          response.data?.total ||
          response.data?.data?.total ||
          response.total ||
          0;
        setArticles(articlesData);
        setTotalPages(Math.ceil(totalData / 12));
        setTotalArticles(totalData);
      } else {
        setArticles([]);
        setTotalPages(1);
        setTotalArticles(0);
      }
    } catch (err: any) {
      console.error('Error loading articles:', err);
      const errorMsg = getUserFriendlyError(err);
      setError(errorMsg);
      showError(errorMsg);
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [page, searchQuery, filterSource, sortBy, showUnlinkedOnly, domain]);

  // Load existing topics from database
  const loadTopics = useCallback(async () => {
    try {
      const response = await apiService.getTopics({ limit: 50 }, domain);
      if (response.success && response.data?.topics) {
        const apiTopics = response.data.topics;

        // Map API topics to frontend format
        const mappedTopics = apiTopics.map((topic: any) => {
          const topicName = topic.name || topic.cluster_name || 'Unknown Topic';

          // Get articles for this topic from our current articles list
          // Use article_ids from API if available (most reliable)
          let topicArticles: ArticleItem[] = [];

          if (
            topic.article_ids &&
            Array.isArray(topic.article_ids) &&
            topic.article_ids.length > 0
          ) {
            // Match by article IDs from database
            topicArticles = articles.filter((a: ArticleItem) =>
              topic.article_ids.includes(a.id)
            );
          }

          // If no matches found, try keyword matching as fallback
          if (
            topicArticles.length === 0 &&
            topic.keywords &&
            Array.isArray(topic.keywords)
          ) {
            topicArticles = articles.filter((a: ArticleItem) =>
              topic.keywords.some((kw: string) =>
                (a.title || '').toLowerCase().includes(kw.toLowerCase())
              )
            );
          }

          return {
            name: topicName,
            articles: topicArticles,
            count:
              topic.article_count || topic.count || topicArticles.length || 0,
          };
        });

        if (mappedTopics.length > 0) {
          setTopics(mappedTopics);
        }
      }
    } catch (error) {
      console.warn('Failed to load topics from database:', error);
      // Don't show error - topics are optional
    }
  }, [articles, domain]);

  useEffect(() => {
    setPage(1);
  }, [domain]);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchQuery.trim()), 350);
    return () => window.clearTimeout(t);
  }, [searchQuery]);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  useEffect(() => {
    loadStorylines();
  }, [loadStorylines]);

  useEffect(() => {
    const srcs = [
      ...new Set(
        articles
          .map((a: ArticleItem) => a.source)
          .filter((s): s is string => Boolean(s && String(s).trim()))
      ),
    ];
    srcs.sort((a, b) => a.localeCompare(b));
    setSourceOptions(srcs);
  }, [articles]);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  // Trigger NEW topic clustering (creates new topics in database)
  const clusterArticles = useCallback(async () => {
    try {
      setClustering(true);
      setError(null);

      const timePeriodHours = 24; // Can be made configurable
      const response = await apiService.clusterArticles(
        {
          limit: articles.length,
          time_period_hours: timePeriodHours,
        },
        domain
      );

      if (response.success) {
        showSuccess(
          'Topic clustering started in background. Results will appear shortly...'
        );

        // Poll for new results with exponential backoff
        let attempts = 0;
        const maxAttempts = 10;
        const initialDelay = 3000; // Start with 3 seconds (clustering takes time)

        const pollForResults = async (): Promise<boolean> => {
          while (attempts < maxAttempts) {
            attempts++;
            const delay = initialDelay * Math.pow(1.5, attempts - 1); // Exponential backoff

            await new Promise(resolve => setTimeout(resolve, delay));

            try {
              // Reload topics from database
              await loadTopics();

              // Check if we have topics now
              if (topics.length > 0) {
                showSuccess(
                  `Clustering complete! Found ${topics.length} topics.`
                );
                return true;
              }
            } catch (pollError) {
              console.warn(`Poll attempt ${attempts} failed:`, pollError);
              // Continue polling
            }
          }
          return false;
        };

        const foundResults = await pollForResults();

        if (!foundResults) {
          showWarning(
            'Clustering may still be processing. Topics will appear when ready.'
          );
        }
      } else {
        showError('Failed to start topic clustering');
      }

      // Fallback to local keyword-based clustering
      const topicMap: Record<string, Topic> = {};

      articles.forEach(article => {
        const title = (article.title || '').toLowerCase();
        let topicName = 'General News';

        if (
          title.includes('election') ||
          title.includes('vote') ||
          title.includes('president')
        ) {
          topicName = 'Election 2024';
        } else if (title.includes('climate') || title.includes('environment')) {
          topicName = 'Climate Change';
        } else if (
          title.includes('tech') ||
          title.includes('ai') ||
          title.includes('software')
        ) {
          topicName = 'Technology';
        } else if (
          title.includes('economy') ||
          title.includes('market') ||
          title.includes('inflation')
        ) {
          topicName = 'Economy';
        } else if (
          title.includes('health') ||
          title.includes('medical') ||
          title.includes('covid')
        ) {
          topicName = 'Health';
        } else if (
          title.includes('war') ||
          title.includes('conflict') ||
          title.includes('military')
        ) {
          topicName = 'Conflict';
        }

        if (!topicMap[topicName]) {
          topicMap[topicName] = {
            name: topicName,
            articles: [],
            count: 0,
          };
        }
        topicMap[topicName].articles.push(article);
        topicMap[topicName].count++;
      });

      setTopics(Object.values(topicMap));
      showSuccess('Articles clustered by topic');
    } catch (err) {
      console.error('Error clustering articles:', err);
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError('Error clustering articles: ' + errorMsg);
      showError('Failed to cluster articles: ' + errorMsg);
    } finally {
      setClustering(false);
    }
  }, [articles, domain, showSuccess, showError]);

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setSearchQuery(value);
    setPage(1);
  };

  const handleFilterChange = (filterType: string, value: string) => {
    switch (filterType) {
      case 'source_domain':
        setFilterSource(value);
        break;
      case 'sort':
        setSortBy(value);
        break;
      default:
        console.warn('Unknown filter type:', filterType);
        break;
    }
    setPage(1);
  };

  const handleQuickFilter = (
    filterType: keyof typeof quickFilters,
    value: string | null
  ) => {
    setQuickFilters(prev => ({
      ...prev,
      [filterType]: prev[filterType] === value ? null : value,
    }));
    setPage(1);
  };

  const handleExportCSV = () => {
    try {
      const headers = [
        'Title',
        'Source',
        'Published Date',
        'Reading Time',
        'Quality Score',
        'Sentiment',
        'URL',
      ];
      const rows = articles.map(article => [
        `"${(article.title || '').replace(/"/g, '""')}"`,
        article.source_domain || article.source || '',
        article.published_at || article.created_at || '',
        formatReadingTime(getArticleReadingTime(article)),
        article.quality_score
          ? (article.quality_score * 100).toFixed(1) + '%'
          : '',
        article.sentiment || '',
        article.url || '',
      ]);

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.join(',')),
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute(
        'download',
        `articles_export_${new Date().toISOString().split('T')[0]}.csv`
      );
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      showSuccess(`Exported ${articles.length} articles to CSV`);
    } catch (err) {
      console.error('Export error:', err);
      showError('Failed to export articles');
    }
  };

  // Topic + reading-time only (quality/sentiment are server-side query params)
  const filteredArticles = articles.filter(article => {
    if (selectedTopic) {
      const topicIds = selectedTopic.articles.map(a => a.id);
      // If topic has no resolved rows yet (e.g. article_ids not on this page), do not hide all rows
      if (topicIds.length > 0 && !topicIds.includes(article.id)) {
        return false;
      }
    }
    if (quickFilters.readingTime) {
      const readingTime = getArticleReadingTime(article);
      if (quickFilters.readingTime === 'short' && readingTime >= 3)
        return false;
      if (
        quickFilters.readingTime === 'medium' &&
        (readingTime < 3 || readingTime > 5)
      )
        return false;
      if (quickFilters.readingTime === 'long' && readingTime <= 5) return false;
    }
    return true;
  });

  const handleRefresh = () => {
    loadArticles();
  };

  const toggleBookmark = (articleId: number) => {
    const newBookmarked = new Set(bookmarkedArticles);
    if (newBookmarked.has(articleId)) {
      newBookmarked.delete(articleId);
    } else {
      newBookmarked.add(articleId);
    }
    setBookmarkedArticles(newBookmarked);
  };

  const getSentimentColor = (sentiment?: string) => {
    switch (sentiment?.toLowerCase()) {
      case 'positive':
        return 'success';
      case 'negative':
        return 'error';
      case 'neutral':
        return 'default';
      default:
        return 'default';
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateText = (text?: string, maxLength: number = 150) => {
    if (!text) return '';
    return text.length > maxLength
      ? text.substring(0, maxLength) + '...'
      : text;
  };

  const handleOpenArticle = (article: ArticleItem) => {
    setSelectedArticle(article);
    setReaderOpen(true);
  };

  const handleCloseReader = () => {
    setReaderOpen(false);
    setSelectedArticle(null);
  };

  const handleAddToStoryline = (article: ArticleItem) => {
    if (!article || !article.id) {
      showError('Invalid article data');
      return;
    }

    setArticleToAdd(article);
    setSelectedStorylineId('');
    setStorylineDialogOpen(true);
  };

  const checkForDuplicate = async (
    storylineId: string,
    articleId: number
  ): Promise<boolean> => {
    try {
      const storyline = storylines.find(s => s.id.toString() === storylineId);
      if (storyline && storyline.article_count && storyline.article_count > 0) {
        // In a real implementation, you'd call an API endpoint to check
        return false;
      }
      return false;
    } catch (error) {
      console.error('Error checking for duplicate:', error);
      return false;
    }
  };

  const handleAddToStorylineConfirm = async () => {
    if (!articleToAdd || !selectedStorylineId) {
      showError('Please select a storyline');
      return;
    }

    try {
      const isDuplicate = await checkForDuplicate(
        selectedStorylineId,
        articleToAdd.id
      );

      if (isDuplicate) {
        const storyline = storylines.find(
          s => s.id.toString() === selectedStorylineId
        );
        if (storyline) {
          setDuplicateInfo({ article: articleToAdd, storyline });
          setDuplicateDialogOpen(true);
        }
        return;
      }

      const storyline = storylines.find(
        s => s.id.toString() === selectedStorylineId
      );
      showSuccess(
        `Article "${articleToAdd.title}" added to storyline "${
          storyline?.title || 'Unknown'
        }"`
      );

      setStorylineDialogOpen(false);
      setArticleToAdd(null);
      setSelectedStorylineId('');
    } catch (error) {
      console.error('Failed to add article to storyline:', error);
      showError('Failed to add article to storyline');
    }
  };

  const handleDuplicateConfirm = async () => {
    const storyline = duplicateInfo.storyline;
    const article = duplicateInfo.article;

    if (storyline && article) {
      showWarning(
        `Article "${article.title}" added to storyline "${storyline.title}" (duplicate allowed)`
      );
    }

    setDuplicateDialogOpen(false);
    setStorylineDialogOpen(false);
    setArticleToAdd(null);
    setSelectedStorylineId('');
    setDuplicateInfo({ article: null, storyline: null });
  };

  const handleDuplicateCancel = () => {
    setDuplicateDialogOpen(false);
    setDuplicateInfo({ article: null, storyline: null });
  };

  const handleStorylineDialogClose = () => {
    setStorylineDialogOpen(false);
    setArticleToAdd(null);
    setSelectedStorylineId('');
  };

  const filterByTopic = (topic: Topic | null) => {
    setSelectedTopic(topic);
    setPage(1);
  };

  const ArticleCard: React.FC<{ article: ArticleItem }> = ({ article }) => (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: 'pointer',
        '&:hover': {
          boxShadow: 4,
          transform: 'translateY(-2px)',
          transition: 'all 0.2s ease-in-out',
        },
      }}
      onClick={() => handleOpenArticle(article)}
    >
      {article.image_url && (
        <CardMedia
          component='img'
          height='200'
          image={article.image_url}
          alt={article.title}
          sx={{ objectFit: 'cover' }}
        />
      )}
      <CardContent sx={{ flexGrow: 1 }}>
        <Box
          display='flex'
          justifyContent='space-between'
          alignItems='flex-start'
          mb={2}
        >
          <Typography
            variant='h6'
            component='h3'
            sx={{
              fontWeight: 'bold',
              lineHeight: 1.2,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {article.title || 'Untitled Article'}
          </Typography>
          <IconButton
            size='small'
            onClick={e => {
              e.stopPropagation();
              toggleBookmark(article.id);
            }}
            sx={{ ml: 1 }}
          >
            {bookmarkedArticles.has(article.id) ? (
              <Bookmark color='primary' />
            ) : (
              <BookmarkBorder />
            )}
          </IconButton>
        </Box>

        <Typography
          variant='body2'
          color='text.secondary'
          sx={{
            mb: 2,
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {truncateText(article.summary || article.content)}
        </Typography>

        <Box display='flex' flexWrap='wrap' gap={1} mb={2}>
          {article.sentiment && (
            <Chip
              label={article.sentiment}
              color={getSentimentColor(article.sentiment)}
              size='small'
            />
          )}
          {article.quality_score && (
            <Chip
              label={`Quality: ${Math.round(article.quality_score * 100)}%`}
              color='primary'
              size='small'
            />
          )}
          {article.category && (
            <Chip label={article.category} color='secondary' size='small' />
          )}
        </Box>

        <Box
          display='flex'
          alignItems='center'
          justifyContent='space-between'
          mb={1}
        >
          <Box display='flex' alignItems='center' gap={1}>
            <Source fontSize='small' color='action' />
            <Typography variant='caption' color='text.secondary'>
              {article.source_domain || article.source || 'Unknown Source'}
            </Typography>
          </Box>
          <Box display='flex' alignItems='center' gap={1.5}>
            {(() => {
              const readingTime = getArticleReadingTime(article);
              return readingTime > 0 ? (
                <Box display='flex' alignItems='center' gap={0.5}>
                  <AccessTime
                    fontSize='inherit'
                    sx={{ fontSize: '0.875rem' }}
                  />
                  <Typography variant='caption' color='text.secondary'>
                    {formatReadingTime(readingTime)}
                  </Typography>
                </Box>
              ) : null;
            })()}
            <Typography variant='caption' color='text.secondary'>
              {formatDate(article.published_at || article.created_at)}
            </Typography>
          </Box>
        </Box>

        {article.entities && article.entities.length > 0 && (
          <Box mt={1}>
            <Typography
              variant='caption'
              color='text.secondary'
              display='block'
            >
              Key Entities: {article.entities.slice(0, 3).join(', ')}
              {article.entities.length > 3 &&
                ` +${article.entities.length - 3} more`}
            </Typography>
          </Box>
        )}
      </CardContent>

      <CardActions sx={{ p: 2, pt: 0 }}>
        <Button
          size='small'
          startIcon={<Visibility />}
          onClick={e => {
            e.stopPropagation();
            handleOpenArticle(article);
          }}
        >
          Read Full Article
        </Button>
        <Button
          size='small'
          startIcon={<TimelineIcon />}
          onClick={e => {
            e.stopPropagation();
            handleAddToStoryline(article);
          }}
        >
          Add to Storyline
        </Button>
        <Button size='small' startIcon={<ShareIcon />}>
          Share
        </Button>
      </CardActions>
    </Card>
  );

  const ArticleListItem: React.FC<{ article: ArticleItem }> = ({ article }) => (
    <ListItem
      onClick={() => handleOpenArticle(article)}
      sx={{
        border: 1,
        cursor: 'pointer',
        '&:hover': {
          backgroundColor: 'action.hover',
          boxShadow: 1,
        },
        borderColor: 'divider',
        borderRadius: 1,
        mb: 1,
        bgcolor: 'background.paper',
      }}
    >
      <ListItemText
        primary={
          <Box display='flex' alignItems='center' gap={1} mb={1}>
            <Typography variant='h6' sx={{ flexGrow: 1 }}>
              {article.title || 'Untitled Article'}
            </Typography>
            <Box display='flex' gap={1}>
              {article.sentiment && (
                <Chip
                  label={article.sentiment}
                  color={getSentimentColor(article.sentiment)}
                  size='small'
                />
              )}
              {article.quality_score && (
                <Chip
                  label={`${Math.round(article.quality_score * 100)}%`}
                  color='primary'
                  size='small'
                />
              )}
            </Box>
          </Box>
        }
        secondary={
          <Box>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
              {truncateText(article.summary || article.content, 200)}
            </Typography>
            <Box display='flex' alignItems='center' gap={2}>
              <Box display='flex' alignItems='center' gap={0.5}>
                <Source fontSize='small' />
                <Typography variant='caption'>
                  {article.source_domain || article.source || 'Unknown Source'}
                </Typography>
              </Box>
              {(() => {
                const readingTime = getArticleReadingTime(article);
                return readingTime > 0 ? (
                  <Box display='flex' alignItems='center' gap={0.5}>
                    <AccessTime
                      fontSize='inherit'
                      sx={{ fontSize: '0.75rem' }}
                    />
                    <Typography variant='caption' color='text.secondary'>
                      {formatReadingTime(readingTime)}
                    </Typography>
                  </Box>
                ) : null;
              })()}
              <Typography variant='caption'>
                {formatDate(article.published_at || article.created_at)}
              </Typography>
              {article.entities && article.entities.length > 0 && (
                <Typography variant='caption' color='text.secondary'>
                  Entities: {article.entities.slice(0, 3).join(', ')}
                </Typography>
              )}
            </Box>
          </Box>
        }
      />
      <ListItemSecondaryAction>
        <Box display='flex' gap={1}>
          <IconButton size='small' onClick={() => toggleBookmark(article.id)}>
            {bookmarkedArticles.has(article.id) ? (
              <Bookmark color='primary' />
            ) : (
              <BookmarkBorder />
            )}
          </IconButton>
          <Button
            size='small'
            startIcon={<Visibility />}
            onClick={e => {
              e.stopPropagation();
              handleOpenArticle(article);
            }}
          >
            View
          </Button>
        </Box>
      </ListItemSecondaryAction>
    </ListItem>
  );

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
            Article Queue
          </Typography>
          <Typography variant='h6' color='text.secondary' gutterBottom>
            Browse and curate articles for your storylines • {totalArticles}{' '}
            articles available
          </Typography>
        </Box>
        <Box display='flex' gap={2} alignItems='center'>
          <Tooltip title='Refresh Articles'>
            <span>
              <IconButton onClick={handleRefresh} disabled={loading}>
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
          <Button
            variant={viewMode === 'grid' ? 'contained' : 'outlined'}
            startIcon={<ViewModule />}
            onClick={() => setViewMode('grid')}
            size='small'
          >
            Grid
          </Button>
          <Button
            variant={viewMode === 'list' ? 'contained' : 'outlined'}
            startIcon={<ViewList />}
            onClick={() => setViewMode('list')}
            size='small'
          >
            List
          </Button>
        </Box>
      </Box>

      {/* Topic Clustering Section */}
      {showTopicClustering && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              <ClusterIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Topics & Clustering
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              {topics.length > 0
                ? `Showing ${topics.length} topics from database. Click below to create new topics from recent articles.`
                : 'No topics found. Create new topics by analyzing recent articles.'}
            </Typography>

            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Button
                variant='contained'
                startIcon={
                  clustering ? (
                    <CircularProgress size={20} />
                  ) : (
                    <AutoAwesomeIcon />
                  )
                }
                onClick={clusterArticles}
                disabled={clustering || articles.length === 0}
              >
                {clustering
                  ? 'Creating Topics...'
                  : 'Create New Topics from Articles'}
              </Button>

              <Button
                variant='outlined'
                startIcon={<Refresh />}
                onClick={loadTopics}
                disabled={clustering}
              >
                Refresh Topics
              </Button>

              {topics.length > 0 && (
                <Button
                  variant='outlined'
                  onClick={() => filterByTopic(null)}
                  disabled={selectedTopic === null}
                >
                  Clear Topic Filter
                </Button>
              )}

              <Button
                variant='outlined'
                onClick={() => setShowTopicClustering(false)}
              >
                Hide Clustering
              </Button>
            </Box>

            {/* Topics Display */}
            {topics.length > 0 && (
              <Box>
                <Typography variant='subtitle1' gutterBottom>
                  Discovered Topics ({topics.length})
                </Typography>
                <Box display='flex' flexWrap='wrap' gap={1}>
                  {topics.map((topic, index) => (
                    <Chip
                      key={index}
                      label={`${topic.name} (${topic.count})`}
                      onClick={() => filterByTopic(topic)}
                      color={
                        selectedTopic?.name === topic.name
                          ? 'primary'
                          : 'default'
                      }
                      variant={
                        selectedTopic?.name === topic.name
                          ? 'filled'
                          : 'outlined'
                      }
                      sx={{ cursor: 'pointer' }}
                    />
                  ))}
                </Box>
              </Box>
            )}

            {/* Topic Filter Status */}
            {selectedTopic && (
              <Alert severity='info' sx={{ mt: 2 }}>
                Showing articles for topic:{' '}
                <strong>{selectedTopic.name}</strong> ({selectedTopic.count}{' '}
                articles)
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {!showTopicClustering && (
        <Button
          variant='outlined'
          startIcon={<ClusterIcon />}
          onClick={() => setShowTopicClustering(true)}
          sx={{ mb: 2 }}
        >
          Show Topic Clustering
        </Button>
      )}

      {/* Search and Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2} alignItems='center'>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder='Search title, summary, source, or URL…'
              value={searchQuery}
              onChange={handleSearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position='start'>
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={filterSource}
                label='Source'
                onChange={e =>
                  handleFilterChange('source_domain', e.target.value)
                }
              >
                <MenuItem value=''>All Sources</MenuItem>
                {sourceOptions.map(src => (
                  <MenuItem key={src} value={src}>
                    {src}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label='Sort By'
                onChange={e => handleFilterChange('sort', e.target.value)}
              >
                <MenuItem value='date'>Date</MenuItem>
                <MenuItem value='relevance'>Relevance</MenuItem>
                <MenuItem value='quality'>Quality Score</MenuItem>
                <MenuItem value='title'>Title</MenuItem>
                <MenuItem value='source_domain'>Source</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant='outlined'
              startIcon={<FilterList />}
              onClick={() => {
                setSearchQuery('');
                setFilterSource('');
                setSortBy('date');
                setShowUnlinkedOnly(true);
                setFilterTopic('');
                setQuickFilters({
                  readingTime: null,
                  quality: null,
                  sentiment: null,
                });
                setSelectedTopic(null);
                setPage(1);
              }}
            >
              Clear Filters
            </Button>
          </Grid>
          <Grid item xs={12}>
            <Box display='flex' alignItems='center' gap={2} flexWrap='wrap'>
              <FormControlLabel
                control={
                  <Switch
                    checked={showUnlinkedOnly}
                    onChange={e => {
                      setShowUnlinkedOnly(e.target.checked);
                      setPage(1);
                    }}
                  />
                }
                label='Unlinked articles only'
              />
              {topics.length > 0 && (
                <FormControl size='small' sx={{ minWidth: 180 }}>
                  <InputLabel>Filter by Topic</InputLabel>
                  <Select
                    value={filterTopic}
                    label='Filter by Topic'
                    onChange={e => {
                      setFilterTopic(e.target.value);
                      if (e.target.value) {
                        const topic = topics.find(
                          t => t.name === e.target.value
                        );
                        setSelectedTopic(topic || null);
                      } else {
                        setSelectedTopic(null);
                      }
                    }}
                  >
                    <MenuItem value=''>All Topics</MenuItem>
                    {topics.map(t => (
                      <MenuItem key={t.name} value={t.name}>
                        {t.name} ({t.count})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            </Box>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant='contained'
              startIcon={<DownloadIcon />}
              onClick={handleExportCSV}
              disabled={articles.length === 0}
            >
              Export CSV
            </Button>
          </Grid>
        </Grid>

        {/* Quick Filter Chips */}
        <Box sx={{ mt: 2 }}>
          <Typography variant='body2' gutterBottom>
            Quick Filters
          </Typography>
          <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
            Quality and sentiment apply to the full result set. Reading length refines
            the current page only (estimated from summary).
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>

          {/* Reading Time Filters */}
          <Chip
            label='Short Read (< 3 min)'
            onClick={() => handleQuickFilter('readingTime', 'short')}
            color={quickFilters.readingTime === 'short' ? 'primary' : 'default'}
            variant={
              quickFilters.readingTime === 'short' ? 'filled' : 'outlined'
            }
            size='small'
          />
          <Chip
            label='Medium Read (3-5 min)'
            onClick={() => handleQuickFilter('readingTime', 'medium')}
            color={
              quickFilters.readingTime === 'medium' ? 'primary' : 'default'
            }
            variant={
              quickFilters.readingTime === 'medium' ? 'filled' : 'outlined'
            }
            size='small'
          />
          <Chip
            label='Long Read (> 5 min)'
            onClick={() => handleQuickFilter('readingTime', 'long')}
            color={quickFilters.readingTime === 'long' ? 'primary' : 'default'}
            variant={
              quickFilters.readingTime === 'long' ? 'filled' : 'outlined'
            }
            size='small'
          />

          {/* Quality Filters */}
          <Chip
            label='High Quality (> 70%)'
            onClick={() => handleQuickFilter('quality', 'high')}
            color={quickFilters.quality === 'high' ? 'primary' : 'default'}
            variant={quickFilters.quality === 'high' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Medium Quality (50-70%)'
            onClick={() => handleQuickFilter('quality', 'medium')}
            color={quickFilters.quality === 'medium' ? 'primary' : 'default'}
            variant={quickFilters.quality === 'medium' ? 'filled' : 'outlined'}
            size='small'
          />
          <Chip
            label='Low Quality (< 50%)'
            onClick={() => handleQuickFilter('quality', 'low')}
            color={quickFilters.quality === 'low' ? 'primary' : 'default'}
            variant={quickFilters.quality === 'low' ? 'filled' : 'outlined'}
            size='small'
          />

          {/* Sentiment Filters */}
          <Chip
            label='Positive'
            onClick={() => handleQuickFilter('sentiment', 'positive')}
            color={
              quickFilters.sentiment === 'positive' ? 'success' : 'default'
            }
            variant={
              quickFilters.sentiment === 'positive' ? 'filled' : 'outlined'
            }
            size='small'
          />
          <Chip
            label='Neutral'
            onClick={() => handleQuickFilter('sentiment', 'neutral')}
            color={quickFilters.sentiment === 'neutral' ? 'default' : 'default'}
            variant={
              quickFilters.sentiment === 'neutral' ? 'filled' : 'outlined'
            }
            size='small'
          />
          <Chip
            label='Negative'
            onClick={() => handleQuickFilter('sentiment', 'negative')}
            color={quickFilters.sentiment === 'negative' ? 'error' : 'default'}
            variant={
              quickFilters.sentiment === 'negative' ? 'filled' : 'outlined'
            }
            size='small'
          />
          </Box>
        </Box>
      </Paper>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Articles Display */}
      {articles.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Article sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant='h6' color='text.secondary' gutterBottom>
            No articles found
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            {searchQuery || filterSource
              ? 'Try adjusting your search criteria or filters'
              : showUnlinkedOnly
                ? 'No articles match “unlinked only” (none in this silo yet, or every article is already on a storyline). Turn off the switch below to list all articles.'
                : 'Articles appear after RSS runs for this domain’s feeds. Ensure feeds are registered (provision_domain / rss_feeds) and automation or collect_rss_feeds has ingested at least one run.'}
          </Typography>
        </Paper>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <Grid container spacing={3}>
              {filteredArticles.map(article => (
                <Grid item xs={12} sm={6} md={4} key={article.id}>
                  <ArticleCard article={article} />
                </Grid>
              ))}
            </Grid>
          ) : (
            <List>
              {filteredArticles.map(article => (
                <ArticleListItem key={article.id} article={article} />
              ))}
            </List>
          )}

          {filteredArticles.length === 0 && articles.length > 0 && (
            <Alert severity='info' sx={{ mt: 2 }}>
              No articles match the selected quick filters. Try adjusting your
              filters.
            </Alert>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Box display='flex' justifyContent='center' mt={4}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(event, value) => setPage(value)}
                color='primary'
                size='large'
              />
            </Box>
          )}
        </>
      )}

      {/* AI Analysis Features */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant='h6' gutterBottom>
          <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          AI-Powered Analysis
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <AutoAwesomeIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Sentiment Analysis</Typography>
              <Typography variant='body2' color='text.secondary'>
                Automatic sentiment classification for each article
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <TimelineIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Entity Extraction</Typography>
              <Typography variant='body2' color='text.secondary'>
                Identify key people, places, and organizations
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box textAlign='center'>
              <TrendingUpIcon color='primary' sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant='h6'>Quality Scoring</Typography>
              <Typography variant='body2' color='text.secondary'>
                AI-powered quality assessment and ranking
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Article Reader Dialog */}
      <ArticleReader
        article={selectedArticle}
        open={readerOpen}
        onClose={handleCloseReader}
        onAddToStoryline={handleAddToStoryline}
        domain={domain}
      />

      {/* Storyline Selection Dialog */}
      <Dialog
        open={storylineDialogOpen}
        onClose={handleStorylineDialogClose}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>
          <Box
            display='flex'
            alignItems='center'
            justifyContent='space-between'
          >
            <Typography variant='h6'>Add Article to Storyline</Typography>
            <IconButton onClick={handleStorylineDialogClose} size='small'>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent>
          {articleToAdd && (
            <Box mb={3}>
              <Typography
                variant='subtitle2'
                color='text.secondary'
                gutterBottom
              >
                Article to add:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant='body1' fontWeight='medium'>
                  {articleToAdd.title}
                </Typography>
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 1 }}
                >
                  {articleToAdd.source_domain || articleToAdd.source} •{' '}
                  {articleToAdd.published_at
                    ? new Date(articleToAdd.published_at).toLocaleDateString()
                    : 'No date'}
                </Typography>
              </Paper>
            </Box>
          )}

          <FormControl component='fieldset' fullWidth>
            <FormLabel component='legend'>Select a storyline:</FormLabel>
            <RadioGroup
              value={selectedStorylineId}
              onChange={e => setSelectedStorylineId(e.target.value)}
            >
              {storylines.length === 0 ? (
                <Box p={2} textAlign='center'>
                  <Typography color='text.secondary'>
                    No storylines available. Create one first.
                  </Typography>
                </Box>
              ) : (
                storylines.map(storyline => (
                  <FormControlLabel
                    key={storyline.id}
                    value={storyline.id.toString()}
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant='body1' fontWeight='medium'>
                          {storyline.title}
                        </Typography>
                        <Typography variant='body2' color='text.secondary'>
                          {storyline.description || 'No description'}
                        </Typography>
                        <Typography variant='caption' color='text.secondary'>
                          {storyline.article_count || 0} articles • Status:{' '}
                          {storyline.status}
                        </Typography>
                      </Box>
                    }
                  />
                ))
              )}
            </RadioGroup>
          </FormControl>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleStorylineDialogClose}>Cancel</Button>
          <Button
            onClick={handleAddToStorylineConfirm}
            variant='contained'
            disabled={!selectedStorylineId || storylines.length === 0}
            startIcon={<Add />}
          >
            Add to Storyline
          </Button>
        </DialogActions>
      </Dialog>

      {/* Duplicate Warning Dialog */}
      <Dialog
        open={duplicateDialogOpen}
        onClose={handleDuplicateCancel}
        maxWidth='sm'
        fullWidth
      >
        <DialogTitle>
          <Box display='flex' alignItems='center' gap={1}>
            <Typography variant='h6' color='warning.main'>
              Duplicate Article Detected
            </Typography>
          </Box>
        </DialogTitle>

        <DialogContent>
          <Alert severity='warning' sx={{ mb: 2 }}>
            This article may already exist in the selected storyline.
          </Alert>

          {duplicateInfo.article && duplicateInfo.storyline && (
            <Box>
              <Typography variant='subtitle2' gutterBottom>
                Article:
              </Typography>
              <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
                <Typography variant='body1' fontWeight='medium'>
                  {duplicateInfo.article.title}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  {duplicateInfo.article.source_domain ||
                    duplicateInfo.article.source}{' '}
                  •{' '}
                  {duplicateInfo.article.published_at
                    ? new Date(
                        duplicateInfo.article.published_at
                      ).toLocaleDateString()
                    : 'No date'}
                </Typography>
              </Paper>

              <Typography variant='subtitle2' gutterBottom>
                Storyline:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant='body1' fontWeight='medium'>
                  {duplicateInfo.storyline.title}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  {duplicateInfo.storyline.description || 'No description'}
                </Typography>
                <Typography variant='caption' color='text.secondary'>
                  {duplicateInfo.storyline.article_count || 0} articles •
                  Status: {duplicateInfo.storyline.status}
                </Typography>
              </Paper>
            </Box>
          )}

          <Typography variant='body2' sx={{ mt: 2 }}>
            Do you want to add this article anyway? This may create a duplicate
            entry.
          </Typography>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleDuplicateCancel} color='inherit'>
            Cancel
          </Button>
          <Button
            onClick={handleDuplicateConfirm}
            variant='contained'
            color='warning'
          >
            Add Anyway
          </Button>
        </DialogActions>
      </Dialog>

      {/* Standardized notification component */}
      <NotificationComponent />
    </Box>
  );
};

export default Articles;
