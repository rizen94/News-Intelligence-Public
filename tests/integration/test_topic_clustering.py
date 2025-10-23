"""
Integration tests for topic clustering
Tests ML-powered topic analysis and clustering
"""

import pytest
import requests
from tests.conftest import TestConfig, TestUtils

class TestTopicClustering:
    """Test topic clustering functionality"""
    
    def test_topic_clustering_pipeline(self, api_client, test_data_manager):
        """Test complete topic clustering pipeline"""
        # Create articles with different topics
        topics = ["technology", "politics", "business", "science", "sports"]
        articles = []
        
        for i, topic in enumerate(topics):
            article_data = {
                "title": f"Test Article about {topic.title()}",
                "url": f"https://example.com/{topic}-article-{i}",
                "content": f"This is a comprehensive article about {topic}. It discusses various aspects of {topic} and its impact on society.",
                "source_domain": "example.com",
                "published_at": TestConfig.SAMPLE_ARTICLE["published_at"]
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                articles.append(article_id)
        
        # Trigger topic clustering
        response = api_client.post(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics/cluster")
        TestUtils.assert_response_success(response)
        
        # Wait a moment for processing
        import time
        time.sleep(2)
        
        # Get topic clusters
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics")
        TestUtils.assert_response_success(response)
        
        data = response.json()["data"]
        assert len(data["topics"]) > 0, "Should have generated topic clusters"
        
        # Verify topic structure
        for topic in data["topics"]:
            TestUtils.assert_data_integrity(topic, ["id", "name", "description", "article_count"])
    
    def test_intelligent_word_cloud(self, api_client, test_data_manager):
        """Test intelligent word cloud generation"""
        # Create articles with various content
        articles = []
        for i in range(5):
            article_data = {
                "title": f"Word Cloud Test Article {i}",
                "url": f"https://example.com/wordcloud-article-{i}",
                "content": f"This article discusses technology, innovation, artificial intelligence, machine learning, and data science. It covers topics like programming, software development, and digital transformation.",
                "source_domain": "example.com",
                "published_at": TestConfig.SAMPLE_ARTICLE["published_at"]
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                articles.append(article_id)
        
        # Get word cloud data
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics/word-cloud")
        TestUtils.assert_response_success(response)
        
        data = response.json()["data"]
        TestUtils.assert_data_integrity(data, ["word_cloud", "total_topics", "filtered_from"])
        
        # Test intelligent filtering
        TestUtils.assert_no_noise_words(data)
        
        # Verify word cloud contains meaningful topics
        word_cloud = data["word_cloud"]
        meaningful_words = [topic["text"].lower() for topic in word_cloud]
        
        # Should contain technology-related terms
        tech_terms = ["technology", "innovation", "artificial", "intelligence", "machine", "learning", "data", "science"]
        found_tech_terms = [term for term in tech_terms if term in meaningful_words]
        assert len(found_tech_terms) > 0, f"Should find technology terms, found: {meaningful_words[:10]}"
    
    def test_topic_analysis_and_summary(self, api_client, test_data_manager):
        """Test topic analysis and summary generation"""
        # Create articles for a specific topic
        topic_articles = []
        for i in range(3):
            article_data = {
                "title": f"AI Technology Article {i}",
                "url": f"https://example.com/ai-article-{i}",
                "content": f"Artificial intelligence is revolutionizing technology. This article explores AI applications, machine learning algorithms, and the future of intelligent systems.",
                "source_domain": "example.com",
                "published_at": TestConfig.SAMPLE_ARTICLE["published_at"]
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                topic_articles.append(article_id)
        
        # Trigger clustering
        response = api_client.post(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics/cluster")
        TestUtils.assert_response_success(response)
        
        # Get topics
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics")
        TestUtils.assert_response_success(response)
        
        topics = response.json()["data"]["topics"]
        if topics:
            topic_name = topics[0]["name"]
            
            # Get topic summary
            response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics/{topic_name}/summary")
            TestUtils.assert_response_success(response)
            
            summary_data = response.json()["data"]
            TestUtils.assert_data_integrity(summary_data, ["summary", "total_articles", "key_points"])
            
            # Get articles for topic
            response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics/{topic_name}/articles")
            TestUtils.assert_response_success(response)
            
            articles_data = response.json()["data"]
            assert len(articles_data["articles"]) > 0, "Should have articles for the topic"
