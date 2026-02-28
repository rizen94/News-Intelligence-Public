#!/usr/bin/env python3
"""
Unit tests for StorylineService
Tests critical business logic for storyline evolution and content extraction
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from domains.storyline_management.services.storyline_service import StorylineService


class TestStorylineService:
    """Test suite for StorylineService"""
    
    @pytest.fixture
    def storyline_service(self):
        """Create StorylineService instance for testing"""
        return StorylineService(domain='politics')
    
    @pytest.fixture
    def mock_storyline(self):
        """Mock storyline data"""
        return {
            'id': 1,
            'title': 'Test Storyline',
            'description': 'Test description',
            'analysis_summary': 'Existing summary',
            'article_count': 5,
            'last_evolution_at': datetime.now(timezone.utc),
            'evolution_count': 2,
            'background_information': '{"key_facts": [], "entities": []}'
        }
    
    @pytest.fixture
    def mock_articles(self):
        """Mock articles data"""
        return [
            {
                'id': 1,
                'title': 'Article 1',
                'content': 'Content 1',
                'summary': 'Summary 1',
                'published_at': datetime.now(timezone.utc),
                'source_domain': 'test.com',
                'sentiment_score': 0.5,
                'quality_score': 0.7
            },
            {
                'id': 2,
                'title': 'Article 2',
                'content': 'Content 2',
                'summary': 'Summary 2',
                'published_at': datetime.now(timezone.utc),
                'source_domain': 'test.com',
                'sentiment_score': 0.6,
                'quality_score': 0.8
            }
        ]
    
    @pytest.mark.asyncio
    async def test_evolve_storyline_with_new_content_success(self, storyline_service, mock_storyline, mock_articles):
        """Test successful storyline evolution with new content"""
        with patch.object(storyline_service, 'get_db_connection') as mock_db:
            mock_conn = Mock()
            mock_db.return_value = mock_conn
            
            mock_cur = Mock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            # Mock database queries
            mock_cur.fetchone.side_effect = [
                mock_storyline,  # Get storyline
                mock_articles   # Get articles
            ]
            mock_cur.fetchall.return_value = mock_articles
            mock_cur.rowcount = 1
            
            # Mock content extraction
            with patch('domains.storyline_management.services.storyline_service.ContentExtractionService') as mock_extractor:
                mock_extractor_instance = Mock()
                mock_extractor.return_value = mock_extractor_instance
                
                mock_extraction_result = {
                    'success': True,
                    'data': {
                        'key_facts': ['Fact 1'],
                        'entities': ['Entity 1'],
                        'dates': ['2025-01-01']
                    }
                }
                mock_extractor_instance.extract_article_information = AsyncMock(return_value=mock_extraction_result)
                
                mock_new_info = {
                    'success': True,
                    'data': {
                        'has_new_information': True,
                        'new_facts': ['New fact'],
                        'new_entities': ['New entity']
                    }
                }
                mock_extractor_instance.identify_new_information = AsyncMock(return_value=mock_new_info)
                
                mock_merge = {
                    'success': True,
                    'data': {
                        'updated_summary': 'Updated summary',
                        'updated_context': {'key_facts': ['Fact 1', 'New fact']},
                        'merge_notes': {'facts_added': 1}
                    }
                }
                mock_extractor_instance.merge_context = AsyncMock(return_value=mock_merge)
                
                # Execute
                result = await storyline_service.evolve_storyline_with_new_content(
                    storyline_id=1,
                    new_article_ids=[3],
                    force_evolution=True
                )
                
                # Assert
                assert result['success'] is True
                assert result['data']['storyline_id'] == 1
                assert result['data']['summary_updated'] is True
                assert result['data']['context_updated'] is True
    
    @pytest.mark.asyncio
    async def test_evolve_storyline_not_found(self, storyline_service):
        """Test evolution when storyline doesn't exist"""
        with patch.object(storyline_service, 'get_db_connection') as mock_db:
            mock_conn = Mock()
            mock_db.return_value = mock_conn
            
            mock_cur = Mock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.fetchone.return_value = None  # Storyline not found
            
            result = await storyline_service.evolve_storyline_with_new_content(
                storyline_id=999,
                force_evolution=True
            )
            
            assert result['success'] is False
            assert 'not found' in result['error'].lower()
    
    @pytest.mark.asyncio
    async def test_evolve_storyline_too_soon(self, storyline_service, mock_storyline):
        """Test evolution throttling (too soon after last evolution)"""
        # Set last_evolution_at to recent time
        mock_storyline['last_evolution_at'] = datetime.now(timezone.utc)
        
        with patch.object(storyline_service, 'get_db_connection') as mock_db:
            mock_conn = Mock()
            mock_db.return_value = mock_conn
            
            mock_cur = Mock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.fetchone.return_value = mock_storyline
            
            result = await storyline_service.evolve_storyline_with_new_content(
                storyline_id=1,
                force_evolution=False  # Don't force
            )
            
            # Should return success but with message about recent evolution
            assert result['success'] is True
            assert 'recent' in result.get('message', '').lower() or 'message' in result


class TestContentExtractionService:
    """Test suite for ContentExtractionService"""
    
    @pytest.fixture
    def extraction_service(self):
        """Create ContentExtractionService instance"""
        from domains.storyline_management.services.content_extraction_service import ContentExtractionService
        return ContentExtractionService(domain='politics')
    
    @pytest.fixture
    def mock_article(self):
        """Mock article data"""
        return {
            'id': 1,
            'title': 'Test Article',
            'content': 'This is test content with important information.',
            'summary': 'Test summary'
        }
    
    @pytest.mark.asyncio
    async def test_extract_article_information_success(self, extraction_service, mock_article):
        """Test successful article information extraction"""
        with patch('domains.storyline_management.services.content_extraction_service.llm_service') as mock_llm:
            mock_llm.generate_text = AsyncMock(return_value={
                'success': True,
                'text': 'Key Facts: Fact 1\nEntities: Entity 1\nDates: 2025-01-01'
            })
            
            result = await extraction_service.extract_article_information(mock_article)
            
            assert result['success'] is True
            assert 'data' in result
            assert result['article_id'] == 1
    
    @pytest.mark.asyncio
    async def test_identify_new_information(self, extraction_service):
        """Test identification of new information"""
        extracted_info = {
            'key_facts': ['New fact about topic'],
            'entities': ['New Entity'],
            'dates': ['2025-01-01']
        }
        
        existing_context = {
            'key_facts': ['Old fact'],
            'entities': ['Old Entity'],
            'dates': []
        }
        
        result = await extraction_service.identify_new_information(extracted_info, existing_context)
        
        assert result['success'] is True
        assert result['data']['has_new_information'] is True
        assert len(result['data']['new_facts']) > 0
        assert len(result['data']['new_entities']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

