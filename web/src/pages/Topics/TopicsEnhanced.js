import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Loader2, TrendingUp, Eye, BarChart3, Cloud, RefreshCw } from 'lucide-react';
import apiService from '../../services/apiService';

const TopicsEnhanced = () => {
  const [wordCloudData, setWordCloudData] = useState(null);
  const [bigPictureData, setBigPictureData] = useState(null);
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timePeriod, setTimePeriod] = useState(24);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async() => {
    try {
      setLoading(true);
      setError(null);

      // Fetch word cloud data
      const wordCloudResponse = await fetch(`http://localhost:8001/api/v4/content-analysis/topics/word-cloud?time_period_hours=${timePeriod}&min_frequency=1`);
      if (wordCloudResponse.ok) {
        const wordCloudResult = await wordCloudResponse.json();
        setWordCloudData(wordCloudResult.data);
      }

      // Fetch big picture analysis
      const bigPictureResponse = await fetch(`http://localhost:8001/api/v4/content-analysis/topics/big-picture?time_period_hours=${timePeriod}`);
      if (bigPictureResponse.ok) {
        const bigPictureResult = await bigPictureResponse.json();
        setBigPictureData(bigPictureResult.data);
      }

      // Fetch trending topics
      const trendingResponse = await fetch(`http://localhost:8001/api/v4/content-analysis/topics/trending?time_period_hours=${timePeriod}&limit=20`);
      if (trendingResponse.ok) {
        const trendingResult = await trendingResponse.json();
        setTrendingTopics(trendingResult.data.trending_topics || []);
      }

    } catch (err) {
      console.error('Error fetching topic data:', err);
      setError('Failed to load topic data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const triggerClustering = async() => {
    try {
      setRefreshing(true);
      const response = await fetch('http://localhost:8001/api/v4/content-analysis/topics/cluster', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ limit: 100 }),
      });

      if (response.ok) {
        // Wait a moment for processing, then refresh data
        setTimeout(() => {
          fetchData();
        }, 2000);
      }
    } catch (err) {
      console.error('Error triggering clustering:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [timePeriod]);

  const getCategoryColor = (category) => {
    const colors = {
      'politics': 'bg-red-100 text-red-800',
      'economy': 'bg-green-100 text-green-800',
      'technology': 'bg-blue-100 text-blue-800',
      'environment': 'bg-emerald-100 text-emerald-800',
      'health': 'bg-pink-100 text-pink-800',
      'international': 'bg-purple-100 text-purple-800',
      'social': 'bg-yellow-100 text-yellow-800',
      'business': 'bg-indigo-100 text-indigo-800',
      'general': 'bg-gray-100 text-gray-800',
      'semantic': 'bg-gray-100 text-gray-800',
    };
    return colors[category] || colors['general'];
  };

  const getTrendIcon = (direction) => {
    switch (direction) {
    case 'rising':
      return <TrendingUp className="h-4 w-4 text-green-500" />;
    case 'falling':
      return <TrendingUp className="h-4 w-4 text-red-500 rotate-180" />;
    default:
      return <BarChart3 className="h-4 w-4 text-gray-500" />;
    }
  };

  const WordCloudVisualization = ({ words }) => {
    if (!words || words.length === 0) {
      return (
        <div className="text-center py-12">
          <Cloud className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">No topics found for the selected time period.</p>
          <p className="text-sm text-gray-400 mt-2">Try triggering article clustering or expanding the time period.</p>
        </div>
      );
    }

    return (
      <div className="flex flex-wrap gap-2 justify-center p-6">
        {words.map((word, index) => {
          const size = Math.max(12, Math.min(32, word.size / 2));
          const opacity = Math.max(0.6, word.relevance);

          return (
            <div
              key={index}
              className="inline-block cursor-pointer hover:scale-105 transition-transform duration-200"
              style={{
                fontSize: `${size}px`,
                opacity: opacity,
                fontWeight: word.frequency > 5 ? 'bold' : 'normal',
              }}
              title={`${word.text}: ${word.frequency} articles, ${(word.relevance * 100).toFixed(1)}% relevance`}
            >
              <Badge
                variant="outline"
                className={`px-3 py-1 text-sm hover:bg-opacity-80 ${getCategoryColor(word.category || 'general')}`}
              >
                {word.text}
              </Badge>
            </div>
          );
        })}
      </div>
    );
  };

  const BigPictureInsights = ({ data }) => {
    if (!data) return null;

    const { insights, topic_distribution, source_diversity } = data;

    return (
      <div className="space-y-6">
        {/* Key Insights */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Articles</p>
                  <p className="text-2xl font-bold text-blue-600">{insights.total_articles}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Cloud className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium text-gray-600">Active Topics</p>
                  <p className="text-2xl font-bold text-green-600">{insights.active_topics}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Eye className="h-5 w-5 text-purple-500" />
                <div>
                  <p className="text-sm font-medium text-gray-600">Top Category</p>
                  <p className="text-lg font-bold text-purple-600">{insights.top_category}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <TrendingUp className="h-5 w-5 text-orange-500" />
                <div>
                  <p className="text-sm font-medium text-gray-600">Sources</p>
                  <p className="text-2xl font-bold text-orange-600">{insights.source_diversity}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Topic Distribution */}
        {topic_distribution && topic_distribution.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5" />
                <span>Topic Distribution</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {topic_distribution.map((topic, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Badge className={getCategoryColor(topic.category)}>
                        {topic.category}
                      </Badge>
                      <span className="text-sm text-gray-600">{topic.article_count} articles</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full"
                          style={{ width: `${topic.percentage}%` }}
                        ></div>
                      </div>
                      <span className="text-sm text-gray-500 w-12 text-right">{topic.percentage}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Source Diversity */}
        {source_diversity && source_diversity.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Eye className="h-5 w-5" />
                <span>Source Diversity</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {source_diversity.slice(0, 5).map((source, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-sm font-medium">{source.source}</span>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-600">{source.article_count} articles</span>
                      <span className="text-sm text-gray-500">({source.percentage}%)</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  const TrendingTopicsList = ({ topics }) => {
    if (!topics || topics.length === 0) {
      return (
        <div className="text-center py-8">
          <TrendingUp className="h-8 w-8 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500">No trending topics found.</p>
          <p className="text-sm text-gray-400">Try expanding the time period or triggering clustering.</p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {topics.map((topic, index) => (
          <Card key={index} className="hover:shadow-md transition-shadow">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <h3 className="font-semibold text-lg">{topic.name}</h3>
                    <Badge className={getCategoryColor(topic.category)}>
                      {topic.category}
                    </Badge>
                    {getTrendIcon(topic.trend_direction)}
                  </div>

                  {topic.description && (
                    <p className="text-sm text-gray-600 mb-3">{topic.description}</p>
                  )}

                  <div className="flex items-center space-x-4 text-sm text-gray-500">
                    <span>{topic.recent_articles} articles</span>
                    <span>{(topic.avg_relevance * 100).toFixed(1)}% relevance</span>
                    <span>{topic.source_diversity} sources</span>
                    <span className="font-medium text-blue-600">Score: {topic.trend_score}</span>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-sm text-gray-500">
                    {topic.latest_article_date && new Date(topic.latest_article_date).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p>Loading topic analysis...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Topic Analysis & Word Cloud</h1>
            <p className="text-gray-600 mt-2">Discover trending topics and see the big picture of current news</p>
          </div>

          <div className="flex items-center space-x-4">
            <select
              value={timePeriod}
              onChange={(e) => setTimePeriod(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value={1}>Last Hour</option>
              <option value={24}>Last 24 Hours</option>
              <option value={168}>Last 7 Days</option>
              <option value={720}>Last 30 Days</option>
            </select>

            <Button
              onClick={triggerClustering}
              disabled={refreshing}
              className="flex items-center space-x-2"
            >
              {refreshing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              <span>Refresh Topics</span>
            </Button>
          </div>
        </div>

        {error && (
          <Alert className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>

      <Tabs defaultValue="word-cloud" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="word-cloud" className="flex items-center space-x-2">
            <Cloud className="h-4 w-4" />
            <span>Word Cloud</span>
          </TabsTrigger>
          <TabsTrigger value="big-picture" className="flex items-center space-x-2">
            <Eye className="h-4 w-4" />
            <span>Big Picture</span>
          </TabsTrigger>
          <TabsTrigger value="trending" className="flex items-center space-x-2">
            <TrendingUp className="h-4 w-4" />
            <span>Trending</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="word-cloud">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Cloud className="h-5 w-5" />
                <span>Word Cloud - What's Happening</span>
              </CardTitle>
              <p className="text-sm text-gray-600">
                Visual representation of topics based on article frequency. Larger words indicate more coverage.
              </p>
            </CardHeader>
            <CardContent>
              <WordCloudVisualization words={wordCloudData?.words || []} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="big-picture">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Eye className="h-5 w-5" />
                <span>Big Picture Analysis</span>
              </CardTitle>
              <p className="text-sm text-gray-600">
                High-level overview of the current news landscape and topic distribution.
              </p>
            </CardHeader>
            <CardContent>
              <BigPictureInsights data={bigPictureData} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trending">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <TrendingUp className="h-5 w-5" />
                <span>Trending Topics</span>
              </CardTitle>
              <p className="text-sm text-gray-600">
                Topics gaining momentum based on recent article activity and relevance.
              </p>
            </CardHeader>
            <CardContent>
              <TrendingTopicsList topics={trendingTopics} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default TopicsEnhanced;
