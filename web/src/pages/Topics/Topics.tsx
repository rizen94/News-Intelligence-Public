import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Badge,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Tabs,
  Tab,
  Paper,
  LinearProgress,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
} from '@mui/material';
import {
  TrendingUp,
  Article,
  Search,
  Refresh,
  Transform,
  Analytics,
  ExpandMore,
  Visibility,
  Cloud,
  BarChart,
  Timeline,
  Psychology,
  Settings,
  Warning,
  Close,
  Block,
  MergeType,
} from '@mui/icons-material';
// Import with multiple patterns to handle webpack module resolution issues
import apiServiceDefault from '../../services/apiService';
import { getApiService } from '../../services/apiService';
import TopicManagement from './TopicManagement';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { useNotification } from '../../hooks/useNotification';
import { getUserFriendlyError } from '../../utils/errorHandler';
import LoadingState from '../../components/shared/LoadingState';
import EmptyState from '../../components/shared/EmptyState';

// Robust apiService initialization - handle all webpack import patterns
let apiService: any = null;

// Try multiple import patterns to handle webpack module resolution
// Pattern 1: Default export
if (apiServiceDefault && typeof apiServiceDefault === 'object' && typeof (apiServiceDefault as any).getTopics === 'function') {
  apiService = apiServiceDefault;
  console.log('✅ apiService loaded via default export');
}

// Fallback to getter function
if (!apiService || typeof apiService.getTopics !== 'function') {
  try {
    const service = getApiService();
    if (service && typeof service.getTopics === 'function') {
      apiService = service;
      console.log('✅ apiService loaded via getApiService()');
    }
  } catch (e) {
    console.error('❌ Failed to get apiService:', e);
  }
}

// Final safety check - create a proxy that logs errors
if (!apiService || typeof apiService.getTopics !== 'function') {
  console.error('❌ apiService is still undefined or invalid:', {
    apiServiceDefault,
    apiService,
    hasGetApiService: typeof getApiService === 'function',
  });

  // Create a minimal fallback that at least prevents crashes
  apiService = {
    getTopics: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getTopicArticles: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getTopicSummary: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getArticles: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getCategoryStats: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getWordCloud: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getBigPicture: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    getTrendingTopics: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    clusterArticles: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
    convertTopicToStoryline: () => Promise.resolve({ success: false, error: 'apiService not initialized' }),
  };
}

// Helper function to get apiService safely
const getApiServiceSafe = () => {
  const service = apiService || getApiService();
  if (!service || typeof service.getTopics !== 'function') {
    console.error('❌ apiService is invalid, using fallback');
    return apiService; // Return the fallback
  }
  return service;
};

interface Topic {
  name: string;
  category?: string;
  subcategory?: string;
  article_count?: number;
  avg_confidence?: number;
  latest_article?: string;
}

interface TopicArticle {
  id: number;
  title: string;
  source?: string;
  source_domain?: string;
  created_at?: string;
  published_at?: string;
  sentiment?: string;
  sentiment_label?: string;
  urgency?: string;
  topic_confidence?: number;
  relevance_score?: number;
  url?: string;
  summary?: string;
  content?: string;
}

interface TopicSummary {
  total_articles: number;
  unique_sources: number;
  breaking_news: number;
  avg_confidence?: number;
}

interface Category {
  category: string;
  article_count: number;
}

interface WordCloudWord {
  text: string;
  size: number;
  frequency: number;
  relevance: number;
  category?: string;
}

interface WordCloudData {
  word_cloud?: WordCloudWord[];
  words?: WordCloudWord[];
}

interface TopicDistribution {
  category: string;
  article_count: number;
  percentage: number;
}

interface SourceDiversity {
  source: string;
  article_count: number;
  percentage: number;
}

interface BigPictureInsights {
  total_articles: number;
  active_topics: number;
  top_category: string;
  source_diversity: number;
}

interface BigPictureData {
  insights: BigPictureInsights;
  topic_distribution?: TopicDistribution[];
  source_diversity?: SourceDiversity[];
}

interface TrendingTopic {
  name: string;
  category: string;
  description?: string;
  recent_articles: number;
  avg_relevance: number;
  source_diversity: number;
  trend_score: number;
  latest_article_date?: string;
}

const Topics: React.FC = () => {
  const navigate = useNavigate();
  const { domain } = useDomainRoute();
  const { showSuccess, showError, showInfo, NotificationComponent } = useNotification();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  const [topicArticles, setTopicArticles] = useState<TopicArticle[]>([]);
  const [topicSummary, setTopicSummary] = useState<TopicSummary | null>(null);
  const [clustering, setClustering] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [activeTab, setActiveTab] = useState(0);

  // New enhanced data states
  const [wordCloudData, setWordCloudData] = useState<WordCloudData | null>(null);
  const [bigPictureData, setBigPictureData] = useState<BigPictureData | null>(null);
  const [trendingTopics, setTrendingTopics] = useState<TrendingTopic[]>([]);
  const [timePeriod, setTimePeriod] = useState<number>(24);
  const [articleDialogOpen, setArticleDialogOpen] = useState(false);
  const [selectedArticle, setSelectedArticle] = useState<TopicArticle | null>(null);
  const [bannedTopicsDialogOpen, setBannedTopicsDialogOpen] = useState(false);
  const [bannedTopicsList, setBannedTopicsList] = useState<{ id: number; topic_name: string; created_at?: string; reason?: string }[]>([]);
  const [mergeSuggestions, setMergeSuggestions] = useState<{
    primary: { id: number; cluster_name: string; article_count: number };
    secondary: { id: number; cluster_name: string; article_count: number };
    score: number;
    reason: string;
    suggested_name: string;
  }[]>([]);
  const [mergeSuggestionsLoading, setMergeSuggestionsLoading] = useState(false);

  const loadTopics = useCallback(async() => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        limit: 50,
        search: searchQuery || undefined,
        category: selectedCategory || undefined,
      };

      const service = getApiServiceSafe();
      const response = await service.getTopics(params, domain);

      if (response.success) {
        const topicsData = response.data.topics || [];
        setTopics(topicsData);
        setError(null);
        if (topicsData.length === 0 && searchQuery) {
          showInfo(`No topics found matching "${searchQuery}"`);
        }
      } else {
        const errorMsg = response.message || 'Unable to load topics. Please try again.';
        setError(errorMsg);
        showError(errorMsg);
      }
    } catch (err: any) {
      const errorMsg = getUserFriendlyError(err);
      setError(errorMsg);
      showError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedCategory, domain]);

  const loadTopicArticles = useCallback(async(topicName: string) => {
    try {
      const service = getApiServiceSafe();
      console.log(`Loading articles for topic: "${topicName}"`);
      // Increase limit to get more articles
      const response = await service.getTopicArticles(topicName, 100, 0, domain);
      console.log('Topic articles response:', response);

      if (response.success) {
        const articles = response.data?.articles || response.data || [];
        console.log(`Found ${articles.length} articles for topic "${topicName}"`);

        // If no articles found via topic assignment, try searching by keyword
        if (articles.length === 0) {
          console.log(`No articles assigned to topic, searching articles by keyword: "${topicName}"`);
          const service = getApiServiceSafe();
          const searchResponse = await service.getArticles({
            search: topicName,
            limit: 100,
          }, domain);

          if (searchResponse.success) {
            const searchArticles = searchResponse.data?.articles || searchResponse.data?.data?.articles || [];
            console.log(`Found ${searchArticles.length} articles matching keyword "${topicName}"`);
            setTopicArticles(searchArticles);
            if (searchArticles.length > 0) {
              setError(`Found ${searchArticles.length} articles matching "${topicName}" but they're not yet assigned to this topic. Click "Run Topic Clustering" to assign articles to topics.`);
            } else {
              // Check if the search term is a domain name or category
              const domainNames = ['politics', 'finance', 'science-tech', 'science_tech', 'science & technology'];
              const categoryNames = ['technology', 'tech', 'science', 'health', 'business', 'economy', 'environment', 'sports', 'entertainment', 'education', 'employment'];
              
              const searchTermLower = topicName.toLowerCase();
              
              if (domainNames.includes(searchTermLower)) {
                setError(`"${topicName}" is a domain, not a topic. Topics are specific subjects extracted from articles (like "China", "Ukraine", "Donald Trump", "2026 elections"). To view all articles in the ${topicName} domain, go to the Articles page.`);
              } else if (categoryNames.includes(searchTermLower)) {
                setError(`"${topicName}" is a category, not a specific topic. Topics are granular subjects extracted from article content (like "Artificial Intelligence", "Space Exploration", "Quantum Computing"). Try running topic clustering to extract specific topics from articles, or search for a more specific topic name.`);
              } else {
                setError(`Topic "${topicName}" not found and no articles match this keyword. Try running topic clustering to create topics from articles, or search for an existing topic.`);
              }
              showInfo('No articles found. Try running topic clustering to process articles and assign them to topics.');
            }
          } else {
            setTopicArticles([]);
            setError(`No articles found for topic "${topicName}".`);
            showInfo('No articles assigned to this topic yet. Try running topic clustering to assign articles.');
          }
        } else {
          // Map API response fields to frontend format
          const mappedArticles = articles.map((article: any) => ({
            ...article,
            sentiment: article.sentiment_label || article.sentiment,
            topic_confidence: article.relevance_score || article.topic_confidence,
          }));
          setTopicArticles(mappedArticles);
          setError(null);
        }
      } else {
        // If topic doesn't exist, try searching by keyword
        const service = getApiServiceSafe();
        const searchResponse = await service.getArticles({
          search: topicName,
          limit: 100,
        }, domain);

        if (searchResponse.success) {
          const searchArticles = searchResponse.data?.articles || searchResponse.data?.data?.articles || [];
          if (searchArticles.length > 0) {
            setTopicArticles(searchArticles);
            setError(`Found ${searchArticles.length} articles matching "${topicName}" but they're not yet assigned to this topic. Click "Run Topic Clustering" to assign articles to topics.`);
          } else {
            // Check if the search term is a domain name
            const domainNames = ['politics', 'finance', 'science-tech', 'science_tech'];
            if (domainNames.includes(topicName.toLowerCase())) {
              setError(`"${topicName}" is a domain, not a topic. Topics are specific subjects extracted from articles (like "China", "Ukraine", "President Donald Trump"). To view all articles in the ${topicName} domain, go to the Articles page.`);
            } else {
              setError(`Topic "${topicName}" not found and no articles match this keyword.`);
            }
            showInfo('Topic not found. Try running topic clustering first to create topics from articles, or search for an existing topic.');
            setTopicArticles([]);
          }
        } else {
          const errorMsg = response.error || response.message || `Failed to load articles for topic "${topicName}"`;
          console.error('Topic articles API error:', errorMsg);
          setError(errorMsg);
          setTopicArticles([]);
        }
      }
    } catch (err: any) {
      console.error('Error loading topic articles:', err);
      setError(`Error loading articles: ${err.message}. The topic "${topicName}" may not exist in the database yet. Try running topic clustering.`);
      setTopicArticles([]);
    }
  }, [domain]);

  const loadTopicSummary = useCallback(async(topicName: string) => {
    try {
      const service = getApiServiceSafe();
      const response = await service.getTopicSummary(topicName, domain);

      if (response.success) {
        setTopicSummary(response.data);
      }
    } catch (err) {
      console.error('Error loading topic summary:', err);
    }
  }, [domain]);

  const loadCategories = useCallback(async() => {
    try {
      const service = getApiServiceSafe();
      const response = await service.getCategoryStats();

      if (response.success) {
        setCategories(response.data.categories || []);
      }
    } catch (err) {
      console.error('Error loading categories:', err);
    }
  }, []);

  // New enhanced data loading functions
  const loadWordCloudData = useCallback(async() => {
    try {
      const service = getApiServiceSafe();
      // Use min_frequency=1 to get all topics (even with 1 article)
      const response = await service.getWordCloud(timePeriod, 50, domain);
      if (response.success) {
        setWordCloudData(response.data);
        console.log('Word cloud data loaded:', response.data);
      } else {
        console.warn('Word cloud response not successful:', response);
        // Still set empty data so UI shows "No topics found" message
        setWordCloudData({ word_cloud: [], words: [] });
      }
    } catch (err) {
      console.error('Error loading word cloud data:', err);
      // Set empty data on error
      setWordCloudData({ word_cloud: [], words: [] });
    }
  }, [timePeriod, domain]);

  const loadBigPictureData = useCallback(async() => {
    try {
      const service = getApiServiceSafe();
      const response = await service.getBigPicture(timePeriod, domain);
      console.log('Big Picture API Response:', response);
      if (response.success && response.data) {
        console.log('Setting big picture data:', response.data);
        setBigPictureData(response.data);
      } else {
        console.warn('Big Picture API returned unsuccessful or no data:', response);
        setBigPictureData(null);
      }
    } catch (err) {
      console.error('Error loading big picture data:', err);
      setBigPictureData(null);
    }
  }, [timePeriod, domain]);

  const loadMergeSuggestions = useCallback(async() => {
    try {
      setMergeSuggestionsLoading(true);
      const service = getApiServiceSafe();
      const res = await service.getMergeSuggestions?.(0.35, 50, domain);
      if (res?.success && res?.data?.suggestions) {
        setMergeSuggestions(res.data.suggestions);
      } else {
        setMergeSuggestions([]);
      }
    } catch {
      setMergeSuggestions([]);
    } finally {
      setMergeSuggestionsLoading(false);
    }
  }, [domain]);

  const loadBannedTopics = useCallback(async() => {
    try {
      const service = getApiServiceSafe();
      const res = await service.getBannedTopics?.(domain);
      if (res?.success && Array.isArray(res.data)) {
        setBannedTopicsList(res.data);
      }
    } catch {
      setBannedTopicsList([]);
    }
  }, [domain]);

  const loadTrendingTopics = useCallback(async() => {
    try {
      const service = getApiServiceSafe();
      const response = await service.getTrendingTopics(timePeriod, 20, domain);
      if (response.success) {
        setTrendingTopics(response.data?.trending_topics || []);
      }
    } catch (err) {
      console.error('Error loading trending topics:', err);
    }
  }, [timePeriod, domain]);

  const handleTopicSelect = async(topic: Topic) => {
    setSelectedTopic(topic);
    setError(null); // Clear previous errors
    setTopicArticles([]); // Clear previous articles
    await Promise.all([
      loadTopicArticles(topic.name),
      loadTopicSummary(topic.name),
    ]);
  };

  const handleClusterArticles = async() => {
    try {
      setClustering(true);
      setError(null);
      const service = getApiServiceSafe();
      const response = await service.clusterArticles({ limit: 50 }, domain);

      if (response.success) {
        // Clustering started - wait a bit then reload topics
        showSuccess('Topic clustering started! Processing articles in the background...');
        // Wait a few seconds for processing, then reload
        setTimeout(async() => {
          await loadTopics();
          await loadBigPictureData();
          showSuccess('Topics updated! Check the results below.');
        }, 5000);
      } else {
        // Check if articles were queued (this is still success)
        const errorMsg = response.message || response.error || 'Topic clustering failed. Please try again.';
        if (errorMsg.includes('queued') || errorMsg.includes('queue')) {
          showInfo('Articles queued for processing. Topics will appear as processing completes.');
          setError(null);
          // Reload after a delay
          setTimeout(async() => {
            await loadTopics();
            await loadBigPictureData();
          }, 10000);
        } else {
          setError(errorMsg);
          showError(errorMsg);
        }
      }
    } catch (err: any) {
      const errorMsg = getUserFriendlyError(err);
      // Check if it's a network error vs actual failure
      if (errorMsg.includes('Network') || errorMsg.includes('ECONNREFUSED')) {
        setError('Cannot connect to server. Please check your connection.');
        showError('Cannot connect to server. Please check your connection.');
      } else {
        setError(errorMsg);
        showError(errorMsg);
      }
    } finally {
      setClustering(false);
    }
  };

  const handleTransformToStoryline = async(topicName: string) => {
    try {
      const service = getApiServiceSafe();
      const response = await service.convertTopicToStoryline(topicName, undefined, domain);

      if (response.success) {
        setError(null);
        showSuccess(`Successfully converted "${topicName}" to storyline: ${response.data.storyline_title}`);
      } else {
        const errorMsg = response.message || 'Failed to convert topic to storyline. Please try again.';
        setError(errorMsg);
        showError(errorMsg);
      }
    } catch (err: any) {
      const errorMsg = getUserFriendlyError(err);
      setError(errorMsg);
      showError(errorMsg);
    }
  };

  // Initial load - only run once on mount or when domain changes
  useEffect(() => {
    loadTopics();
    loadCategories();
    loadWordCloudData();
    loadBigPictureData();
    loadTrendingTopics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain]);

  // Reload when search or category changes
  useEffect(() => {
    loadTopics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, selectedCategory]);

  // Reload word cloud and trending when time period changes
  useEffect(() => {
    loadWordCloudData();
    loadBigPictureData();
    loadTrendingTopics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timePeriod]);

  const getUrgencyColor = (urgency?: string): 'error' | 'warning' | 'default' | 'info' => {
    switch (urgency) {
    case 'breaking':
      return 'error';
    case 'urgent':
      return 'warning';
    case 'normal':
      return 'default';
    case 'low':
      return 'info';
    default:
      return 'default';
    }
  };

  const getSentimentColor = (sentiment?: string): 'success' | 'error' | 'default' => {
    switch (sentiment) {
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

  const getCategoryColor = (category?: string): 'error' | 'success' | 'info' | 'warning' | 'secondary' | 'primary' | 'default' => {
    const colors = {
      politics: 'error',
      economy: 'success',
      technology: 'info',
      environment: 'success',
      health: 'warning',
      international: 'secondary',
      social: 'warning',
      business: 'primary',
      general: 'default',
      semantic: 'default',
    };
    return colors[category] || 'default';
  };

  const WordCloudVisualization: React.FC<{ words: WordCloudWord[]; onTopicClick?: (topicName: string) => void }> = ({ words, onTopicClick }) => {
    if (!words || words.length === 0) {
      return (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Cloud sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant='h6' color='text.secondary' gutterBottom>
            No topics found
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            Try triggering article clustering or expanding the time period.
          </Typography>
        </Box>
      );
    }

    const handleTopicClick = (topicName: string) => {
      if (onTopicClick) {
        onTopicClick(topicName);
      }
    };

    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 1,
          justifyContent: 'center',
        }}
      >
        {words.map((word, index) => {
          const size = Math.max(12, Math.min(24, word.size / 3));
          const opacity = Math.max(0.6, word.relevance);

          return (
            <Chip
              key={index}
              label={word.text}
              size='small'
              color={getCategoryColor(word.category || 'general')}
              onClick={() => handleTopicClick(word.text)}
              sx={{
                fontSize: `${size}px`,
                opacity: opacity,
                fontWeight: word.frequency > 5 ? 'bold' : 'normal',
                cursor: 'pointer',
                '&:hover': {
                  transform: 'scale(1.05)',
                  boxShadow: '0 4px 8px rgba(0,0,0,0.2)',
                },
                transition: 'all 0.2s ease-in-out',
              }}
              title={`Click to view ${word.frequency} articles about "${
                word.text
              }" (${(word.relevance * 100).toFixed(1)}% relevance)`}
            />
          );
        })}
      </Box>
    );
  };

  const BigPictureInsights: React.FC<{
    data: BigPictureData | null;
    domain?: string;
    onBanTopic?: (topicName: string) => Promise<void>;
  }> = ({ data, domain, onBanTopic }) => {
    if (!data || !data.insights) {
      return (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography color="text.secondary">Loading big picture data...</Typography>
        </Box>
      );
    }

    const { insights, topic_distribution, source_diversity } = data;

    return (
      <Box sx={{ space: 3 }}>
        {/* Key Insights */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={3}>
            <Card variant='outlined'>
              <CardContent sx={{ textAlign: 'center' }}>
                <BarChart sx={{ fontSize: 32, color: 'primary.main', mb: 1 }} />
                <Typography variant='h4' color='primary' gutterBottom>
                  {insights?.total_articles ?? 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Total Articles
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant='outlined'>
              <CardContent sx={{ textAlign: 'center' }}>
                <Cloud sx={{ fontSize: 32, color: 'success.main', mb: 1 }} />
                <Typography variant='h4' color='success.main' gutterBottom>
                  {insights?.active_topics ?? 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Active Topics
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant='outlined'>
              <CardContent sx={{ textAlign: 'center' }}>
                <Psychology
                  sx={{ fontSize: 32, color: 'warning.main', mb: 1 }}
                />
                <Typography variant='h6' color='warning.main' gutterBottom>
                  {insights?.top_category ?? 'None'}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Top Category
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant='outlined'>
              <CardContent sx={{ textAlign: 'center' }}>
                <Timeline sx={{ fontSize: 32, color: 'info.main', mb: 1 }} />
                <Typography variant='h4' color='info.main' gutterBottom>
                  {insights?.source_diversity ?? 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Sources
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Topic Distribution */}
        {topic_distribution && topic_distribution.length > 0 && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography
                variant='h6'
                gutterBottom
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <BarChart />
                Topic Distribution
              </Typography>
              <Box sx={{ space: 2 }}>
                {topic_distribution.map((topic, index) => (
                  <Box key={index} sx={{ mb: 2 }}>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        mb: 1,
                      }}
                    >
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <Chip
                          label={topic.category}
                          size='small'
                          color={getCategoryColor(topic.category)}
                        />
                        <Typography variant='body2' color='text.secondary'>
                          {topic.article_count} articles
                        </Typography>
                        {onBanTopic && (
                          <Tooltip title="Ban this topic (exclude from views – for vague or unhelpful topics like &quot;truth social post&quot;, &quot;on friday&quot;)">
                            <IconButton
                              size="small"
                              color="default"
                              onClick={async () => {
                                if (onBanTopic) await onBanTopic(topic.category);
                              }}
                              sx={{ ml: 0.5 }}
                              aria-label={`Ban topic: ${topic.category}`}
                            >
                              <Block fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Box>
                      <Typography variant='body2' color='text.secondary'>
                        {topic.percentage}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant='determinate'
                      value={topic.percentage}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        )}

        {/* Source Diversity */}
        {source_diversity && source_diversity.length > 0 && (
          <Card>
            <CardContent>
              <Typography
                variant='h6'
                gutterBottom
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <Timeline />
                Source Diversity
              </Typography>
              <List dense>
                {source_diversity.slice(0, 5).map((source, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={source.source}
                      secondary={`${source.article_count} articles (${source.percentage}%)`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        )}
      </Box>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h4' gutterBottom>
        📊 Topic Clustering & Analysis
      </Typography>

      <Typography variant='body1' color='text.secondary' sx={{ mb: 3 }}>
        Discover and explore topics automatically extracted from news articles
        using AI-powered clustering. See the big picture with word clouds,
        trending topics, and comprehensive analysis.
      </Typography>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems='center'>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label='Search Topics'
                value={searchQuery}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <Search sx={{ mr: 1, color: 'text.secondary' }} />
                  ),
                }}
                placeholder='Search for topics, categories, or keywords...'
              />
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={selectedCategory}
                  onChange={(e: any) => setSelectedCategory(e.target.value)}
                  label='Category'
                >
                  <MenuItem value=''>All Categories</MenuItem>
                  {categories.map((category: Category) => (
                    <MenuItem key={category.category} value={category.category}>
                      {category.category} ({category.article_count})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Time Period</InputLabel>
                <Select
                  value={timePeriod}
                  onChange={(e: any) => setTimePeriod(e.target.value)}
                  label='Time Period'
                >
                  <MenuItem value={1}>Last Hour</MenuItem>
                  <MenuItem value={24}>Last 24 Hours</MenuItem>
                  <MenuItem value={168}>Last 7 Days</MenuItem>
                  <MenuItem value={720}>Last 30 Days</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant='outlined'
                startIcon={<Refresh />}
                onClick={() => {
                  loadTopics();
                  loadWordCloudData();
                  loadBigPictureData();
                  loadTrendingTopics();
                }}
                disabled={loading}
              >
                Refresh
              </Button>
            </Grid>

            <Grid item xs={12} md={3}>
              <Button
                fullWidth
                variant='contained'
                startIcon={
                  clustering ? <CircularProgress size={20} /> : <Analytics />
                }
                onClick={handleClusterArticles}
                disabled={clustering}
              >
                {clustering ? 'Clustering...' : 'Cluster Articles'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity='error' sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Enhanced Tabs Interface */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e: React.SyntheticEvent, newValue: number) => {
            setActiveTab(newValue);
            if (newValue === 3) loadMergeSuggestions();
          }}
          variant='fullWidth'
        >
          <Tab icon={<Cloud />} label='Word Cloud' iconPosition='start' />
          <Tab icon={<BarChart />} label='Big Picture' iconPosition='start' />
          <Tab
            icon={<TrendingUp />}
            label='Trending Topics'
            iconPosition='start'
          />
          <Tab
            icon={<MergeType />}
            label='Merge Suggestions'
            iconPosition='start'
          />
          <Tab icon={<Article />} label='All Topics' iconPosition='start' />
          <Tab icon={<Settings />} label='Management' iconPosition='start' />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {activeTab === 0 && (
        <Card>
          <CardContent>
            <Typography
              variant='h6'
              gutterBottom
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <Cloud />
              Word Cloud - What's Happening
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              Visual representation of topics based on article frequency. Larger
              words indicate more coverage.
            </Typography>
            <WordCloudVisualization
              words={wordCloudData?.word_cloud || wordCloudData?.words || []}
              onTopicClick={async(topicName: string) => {
                // Find the topic from the topics list or create a minimal topic object
                const topic = topics.find(t => t.name === topicName) || {
                  name: topicName,
                  category: wordCloudData?.word_cloud?.find(w => w.text === topicName)?.category || 'general',
                };

                // Select the topic to show details with Transform button
                await handleTopicSelect(topic);

                // Scroll to topic details section
                setTimeout(() => {
                  const detailsElement = document.querySelector('[data-topic-details]');
                  if (detailsElement) {
                    detailsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }
                }, 100);
              }}
            />
          </CardContent>
        </Card>
      )}

      {activeTab === 1 && (
        <Card>
          <CardContent>
            <Typography
              variant='h6'
              gutterBottom
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <BarChart />
              Big Picture Analysis
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              High-level overview of the current news landscape and topic
              distribution.
            </Typography>
            <Button
              size="small"
              variant="outlined"
              startIcon={<Block />}
              onClick={() => {
                loadBannedTopics();
                setBannedTopicsDialogOpen(true);
              }}
              sx={{ mb: 2 }}
            >
              Manage banned topics
            </Button>
            <BigPictureInsights
              data={bigPictureData}
              domain={domain}
              onBanTopic={async (topicName) => {
                const service = getApiServiceSafe();
                const res = await service.banTopic(topicName, undefined, domain);
                if (res?.success) {
                  showSuccess(`Topic "${topicName}" banned and will be excluded from views`);
                  loadBigPictureData();
                  loadWordCloudData();
                  loadTrendingTopics();
                } else {
                  showError(res?.error || 'Failed to ban topic');
                }
              }}
            />
            <Dialog
              open={bannedTopicsDialogOpen}
              onClose={() => setBannedTopicsDialogOpen(false)}
              maxWidth="sm"
              fullWidth
            >
              <DialogTitle>Banned topics</DialogTitle>
              <DialogContent>
                <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
                  Topics you&apos;ve banned are excluded from Big Picture, Word Cloud, and Trending views.
                </Typography>
                {bannedTopicsList.length === 0 ? (
                  <Typography color="text.secondary">No banned topics.</Typography>
                ) : (
                  <List dense>
                    {bannedTopicsList.map((b) => (
                      <ListItem
                        key={b.id}
                        secondaryAction={
                          <Button
                            size="small"
                            onClick={async () => {
                              const service = getApiServiceSafe();
                              const res = await service.unbanTopic?.(b.topic_name, domain);
                              if (res?.success) {
                                showSuccess(`Topic "${b.topic_name}" unbanned`);
                                loadBannedTopics();
                                loadBigPictureData();
                                loadWordCloudData();
                                loadTrendingTopics();
                              } else {
                                showError(res?.error || 'Failed to unban topic');
                              }
                            }}
                          >
                            Unban
                          </Button>
                        }
                      >
                        <ListItemText primary={b.topic_name} secondary={b.reason} />
                      </ListItem>
                    ))}
                  </List>
                )}
              </DialogContent>
              <DialogActions>
                <Button onClick={() => setBannedTopicsDialogOpen(false)}>Close</Button>
              </DialogActions>
            </Dialog>
          </CardContent>
        </Card>
      )}

      {activeTab === 2 && (
        <Card>
          <CardContent>
            <Typography
              variant='h6'
              gutterBottom
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <TrendingUp />
              Trending Topics
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              Topics gaining momentum based on recent article activity and
              relevance.
            </Typography>
            {trendingTopics.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <TrendingUp
                  sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }}
                />
                <Typography variant='h6' color='text.secondary' gutterBottom>
                  No trending topics found
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Try expanding the time period or triggering clustering.
                </Typography>
              </Box>
            ) : (
              <Grid container spacing={2}>
                {trendingTopics.map((topic: TrendingTopic, index: number) => (
                  <Grid item xs={12} md={6} key={index}>
                    <Card variant='outlined' sx={{ height: '100%' }}>
                      <CardContent>
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            mb: 2,
                          }}
                        >
                          <Typography variant='h6' component='div'>
                            {topic.name}
                          </Typography>
                          <Chip
                            label={topic.category}
                            size='small'
                            color={getCategoryColor(topic.category)}
                          />
                        </Box>

                        {topic.description && (
                          <Typography
                            variant='body2'
                            color='text.secondary'
                            sx={{ mb: 2 }}
                          >
                            {topic.description}
                          </Typography>
                        )}

                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <Box sx={{ display: 'flex', gap: 2 }}>
                            <Typography variant='body2' color='text.secondary'>
                              {topic.recent_articles} articles
                            </Typography>
                            <Typography variant='body2' color='text.secondary'>
                              {(topic.avg_relevance * 100).toFixed(1)}%
                              relevance
                            </Typography>
                            <Typography variant='body2' color='text.secondary'>
                              {topic.source_diversity} sources
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Typography
                              variant='body2'
                              color='primary'
                              fontWeight='bold'
                            >
                              Score: {topic.trend_score}
                            </Typography>
                            <Tooltip title='Transform to Storyline'>
                              <IconButton
                                size='small'
                                onClick={e => {
                                  e.stopPropagation();
                                  handleTransformToStoryline(topic.name);
                                }}
                              >
                                <Transform />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 3 && (
        <Card>
          <CardContent>
            <Typography variant='h6' gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <MergeType />
              Merge Suggestions
            </Typography>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
              Second-layer clustering: topics that look similar and could be merged (e.g. &quot;Remove Former Prince Andrew&quot; and &quot;Removing Prince Andrew Succession&quot;).
            </Typography>
            <Button
              size='small'
              variant='outlined'
              startIcon={<Refresh />}
              onClick={loadMergeSuggestions}
              disabled={mergeSuggestionsLoading}
              sx={{ mb: 2 }}
            >
              {mergeSuggestionsLoading ? 'Analyzing...' : 'Refresh suggestions'}
            </Button>
            {mergeSuggestionsLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : mergeSuggestions.length === 0 ? (
              <Typography color='text.secondary'>No merge suggestions. Try refreshing after adding more topics.</Typography>
            ) : (
              <List>
                {mergeSuggestions.map((s, i) => (
                  <ListItem
                    key={i}
                    sx={{ flexDirection: 'column', alignItems: 'stretch', border: 1, borderColor: 'divider', borderRadius: 1, mb: 1, p: 2 }}
                    secondaryAction={
                      <Button
                        variant='contained'
                        size='small'
                        startIcon={<MergeType />}
                        onClick={async () => {
                          const service = getApiServiceSafe();
                          const res = await service.mergeClusters?.(
                            s.primary.cluster_name,
                            s.secondary.cluster_name,
                            domain,
                          );
                          if (res?.success) {
                            showSuccess(`Merged "${s.secondary.cluster_name}" into "${s.primary.cluster_name}"`);
                            setMergeSuggestions(prev => prev.filter((_, idx) => idx !== i));
                            loadTopics();
                            loadBigPictureData();
                            loadWordCloudData();
                            loadTrendingTopics();
                          } else {
                            showError(res?.error || 'Failed to merge');
                          }
                        }}
                      >
                        Merge
                      </Button>
                    }
                  >
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                          <Chip label={s.primary.cluster_name} size='small' color='primary' />
                          <Typography component='span' color='text.secondary'>+</Typography>
                          <Chip label={s.secondary.cluster_name} size='small' variant='outlined' />
                        </Box>
                      }
                      secondary={`Score: ${(s.score * 100).toFixed(0)}% • ${s.reason} • ${s.primary.article_count + s.secondary.article_count} articles combined`}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 4 && (
        <>
          {/* Loading */}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {/* Topics Grid */}
          {!loading && (
            <Grid container spacing={3}>
              {topics.map((topic: Topic) => (
                <Grid item xs={12} md={6} lg={4} key={topic.name}>
                  <Card
                    sx={{
                      height: '100%',
                      cursor: 'pointer',
                      '&:hover': { boxShadow: 3 },
                      border:
                        selectedTopic?.name === topic.name
                          ? '2px solid'
                          : 'none',
                      borderColor: 'primary.main',
                    }}
                    onClick={() => handleTopicSelect(topic)}
                  >
                    <CardContent>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          mb: 2,
                        }}
                      >
                        <Typography
                          variant='h6'
                          component='div'
                          sx={{ fontWeight: 'bold' }}
                        >
                          {topic.name}
                        </Typography>
                        <Badge
                          badgeContent={topic.article_count}
                          color='primary'
                        >
                          <Article />
                        </Badge>
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Chip
                          label={topic.category}
                          size='small'
                          color='primary'
                          variant='outlined'
                          sx={{ mr: 1 }}
                        />
                        {topic.subcategory && (
                          <Chip
                            label={topic.subcategory}
                            size='small'
                            variant='outlined'
                          />
                        )}
                      </Box>

                      <Typography
                        variant='body2'
                        color='text.secondary'
                        sx={{ mb: 2 }}
                      >
                        {topic.article_count} articles •{' '}
                        {topic.avg_confidence?.toFixed(1) || '0.0'}% confidence
                      </Typography>

                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <Typography variant='caption' color='text.secondary'>
                          Latest:{' '}
                          {topic.latest_article
                            ? new Date(
                              topic.latest_article,
                            ).toLocaleDateString()
                            : 'N/A'}
                        </Typography>

                        <Box>
                          <Tooltip title='View Articles'>
                            <IconButton
                              size='small'
                              onClick={e => {
                                e.stopPropagation();
                                handleTopicSelect(topic);
                              }}
                            >
                              <Visibility />
                            </IconButton>
                          </Tooltip>

                          <Tooltip title='Transform to Storyline'>
                            <IconButton
                              size='small'
                              onClick={e => {
                                e.stopPropagation();
                                handleTransformToStoryline(topic.name);
                              }}
                            >
                              <Transform />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}

      {/* Topic Details */}
      {selectedTopic && (
        <Card sx={{ mt: 3 }} data-topic-details>
          <CardContent>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 2,
              }}
            >
              <Typography variant='h5' gutterBottom sx={{ mb: 0 }}>
                📈 {selectedTopic.name} - Topic Analysis
              </Typography>
              <Button
                variant='contained'
                startIcon={<Transform />}
                onClick={() => handleTransformToStoryline(selectedTopic.name)}
                sx={{ ml: 2 }}
              >
                Convert to Storyline
              </Button>
            </Box>

            {topicSummary && (
              <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} md={3}>
                  <Card variant='outlined'>
                    <CardContent>
                      <Typography variant='h6' color='primary'>
                        {topicSummary.total_articles}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Total Articles
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={3}>
                  <Card variant='outlined'>
                    <CardContent>
                      <Typography variant='h6' color='primary'>
                        {topicSummary.unique_sources}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Unique Sources
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={3}>
                  <Card variant='outlined'>
                    <CardContent>
                      <Typography variant='h6' color='primary'>
                        {topicSummary.breaking_news}
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Breaking News
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={3}>
                  <Card variant='outlined'>
                    <CardContent>
                      <Typography variant='h6' color='primary'>
                        {topicSummary.avg_confidence?.toFixed(1)}%
                      </Typography>
                      <Typography variant='body2' color='text.secondary'>
                        Avg Confidence
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            )}

            {/* Topic Articles */}
            <Accordion defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                  <Typography variant='h6'>
                    📰 Articles ({topicArticles.length})
                  </Typography>
                  {topicArticles.length > 0 && (
                    <Button
                      variant='outlined'
                      size='small'
                      startIcon={<Transform />}
                      onClick={async(e) => {
                        e.stopPropagation();
                        await handleTransformToStoryline(selectedTopic.name);
                      }}
                      sx={{ ml: 'auto' }}
                    >
                      Add All to Storyline
                    </Button>
                  )}
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {error && topicArticles.length === 0 && (
                  <Alert severity='warning' sx={{ mb: 2 }}>
                    {error}
                  </Alert>
                )}
                {topicArticles.length === 0 ? (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <Article sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant='h6' color='text.secondary' gutterBottom>
                      No articles found
                    </Typography>
                    <Typography variant='body2' color='text.secondary' sx={{ mb: 3 }}>
                      This topic doesn't have any assigned articles yet. Run topic clustering to analyze articles and assign them to topics.
                    </Typography>
                    <Button
                      variant='contained'
                      startIcon={clustering ? <CircularProgress size={16} /> : <Analytics />}
                      onClick={handleClusterArticles}
                      disabled={clustering}
                      sx={{ mt: 2 }}
                    >
                      {clustering ? 'Clustering Articles...' : 'Run Topic Clustering'}
                    </Button>
                    <Typography variant='body2' color='text.secondary' sx={{ mt: 2 }}>
                      This will analyze all articles and assign them to relevant topics.
                    </Typography>
                  </Box>
                ) : (
                  <List>
                    {topicArticles.map((article: TopicArticle) => (
                      <ListItem 
                        key={article.id} 
                        divider
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        sx={{ cursor: 'default', pointerEvents: 'none' }}
                      >
                        <ListItemText
                          primary={article.title}
                          secondary={
                            <>
                              <span>
                                {article.source || article.source_domain} •{' '}
                                {new Date(
                                  article.created_at || article.published_at,
                                ).toLocaleDateString()}
                              </span>
                              <Box component='span' sx={{ mt: 1, ml: 1, display: 'inline-flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {article.sentiment && (
                                  <Chip
                                    label={article.sentiment}
                                    size='small'
                                    color={getSentimentColor(article.sentiment)}
                                    component='span'
                                  />
                                )}
                                {article.urgency && (
                                  <Chip
                                    label={article.urgency}
                                    size='small'
                                    color={getUrgencyColor(article.urgency)}
                                    component='span'
                                  />
                                )}
                                {article.topic_confidence && (
                                  <Chip
                                    label={`${(
                                      article.topic_confidence * 100
                                    ).toFixed(0)}% confidence`}
                                    size='small'
                                    variant='outlined'
                                    component='span'
                                  />
                                )}
                              </Box>
                            </>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Box
                            component='button'
                            type='button'
                            onClick={() => {
                              setSelectedArticle(article);
                              setArticleDialogOpen(true);
                            }}
                            sx={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              padding: '6px 16px',
                              fontSize: '0.875rem',
                              fontWeight: 500,
                              lineHeight: 1.75,
                              borderRadius: '4px',
                              textTransform: 'uppercase',
                              minWidth: '64px',
                              backgroundColor: '#1976d2',
                              color: '#fff',
                              border: 'none',
                              cursor: 'pointer',
                              '&:hover': {
                                backgroundColor: '#1565c0',
                              },
                              zIndex: 1000,
                            }}
                          >
                            <Visibility sx={{ fontSize: 18, mr: 1 }} />
                            Read
                          </Box>
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))}
                  </List>
                )}
              </AccordionDetails>
            </Accordion>
          </CardContent>
        </Card>
      )}

      {/* Tab Content: Management */}
      {activeTab === 5 && (
        <Box>
          <TopicManagement />
        </Box>
      )}

      {/* Article Summary Dialog */}
      <Dialog
        open={articleDialogOpen}
        onClose={() => {
          console.log('Dialog closing');
          setArticleDialogOpen(false);
        }}
        maxWidth='md'
        fullWidth
        PaperProps={{ sx: { minHeight: '50vh', maxHeight: '90vh' } }}
      >
        <DialogTitle>
          <Box display='flex' justifyContent='space-between' alignItems='center'>
            <Typography variant='h5' component='div' sx={{ flex: 1, pr: 2 }}>
              {selectedArticle?.title}
            </Typography>
            <IconButton onClick={() => setArticleDialogOpen(false)} size='small'>
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedArticle && (
            <Box>
              {/* Article Metadata */}
              <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {selectedArticle.source_domain && (
                  <Chip label={selectedArticle.source_domain} size='small' variant='outlined' />
                )}
                {(selectedArticle.published_at || selectedArticle.created_at) && (
                  <Chip
                    label={new Date(
                      selectedArticle.published_at || selectedArticle.created_at || '',
                    ).toLocaleDateString()}
                    size='small'
                    variant='outlined'
                  />
                )}
                {(selectedArticle.sentiment || selectedArticle.sentiment_label) && (
                  <Chip
                    label={selectedArticle.sentiment || selectedArticle.sentiment_label}
                    size='small'
                    color={getSentimentColor(selectedArticle.sentiment || selectedArticle.sentiment_label)}
                  />
                )}
                {(selectedArticle.topic_confidence || selectedArticle.relevance_score) && (
                  <Chip
                    label={`${((selectedArticle.topic_confidence || selectedArticle.relevance_score) * 100).toFixed(0)}% relevance`}
                    size='small'
                    variant='outlined'
                  />
                )}
              </Box>

              <Divider sx={{ my: 2 }} />

              {/* Article Summary */}
              {selectedArticle.summary ? (
                <Box>
                  <Typography variant='h6' gutterBottom>
                    Summary
                  </Typography>
                  <Typography variant='body1' sx={{ lineHeight: 1.8, textAlign: 'justify', mb: 2 }}>
                    {selectedArticle.summary}
                  </Typography>
                </Box>
              ) : selectedArticle.content ? (
                <Box>
                  <Typography variant='h6' gutterBottom>
                    Content
                  </Typography>
                  <Typography variant='body1' sx={{ lineHeight: 1.8, textAlign: 'justify', mb: 2 }}>
                    {selectedArticle.content.length > 2000
                      ? `${selectedArticle.content.substring(0, 2000)}...`
                      : selectedArticle.content}
                  </Typography>
                </Box>
              ) : (
                <Alert severity='info' sx={{ mb: 2 }}>
                  No summary or content available for this article.
                </Alert>
              )}

              {/* Link to Original */}
              {selectedArticle.url && (
                <Box sx={{ mt: 2 }}>
                  <Button
                    variant='outlined'
                    startIcon={<Visibility />}
                    onClick={() => window.open(selectedArticle.url, '_blank')}
                    fullWidth
                  >
                    Read Original Article
                  </Button>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setArticleDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Standardized notification component */}
      <NotificationComponent />
    </Box>
  );
};

export default Topics;
