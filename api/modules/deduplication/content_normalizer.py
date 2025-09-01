#!/usr/bin/env python3
"""
Content Normalization Module for Deduplication
Handles HTML stripping, text cleaning, and content standardization
"""

import re
import hashlib
import logging
from typing import Tuple, Optional
from bs4 import BeautifulSoup
import unicodedata

logger = logging.getLogger(__name__)

class ContentNormalizer:
    """Normalizes article content for deduplication processing"""
    
    def __init__(self):
        """Initialize the content normalizer"""
        self.logger = logging.getLogger(__name__)
        
    def normalize_content(self, raw_content: str, title: str = "") -> Tuple[str, str, str]:
        """
        Normalize content for deduplication
        
        Args:
            raw_content: Raw HTML content from RSS feed
            title: Article title for context
            
        Returns:
            Tuple of (cleaned_content, normalized_content, content_hash)
        """
        try:
            # Step 1: Strip HTML and extract text
            cleaned_content = self._strip_html(raw_content)
            
            # Step 2: Clean and normalize text
            cleaned_content = self._clean_text(cleaned_content)
            
            # Step 3: Create normalized version for comparison
            normalized_content = self._normalize_for_comparison(cleaned_content)
            
            # Step 4: Generate content hash
            content_hash = self._generate_content_hash(normalized_content)
            
            self.logger.debug(f"Content normalized: {len(raw_content)} -> {len(cleaned_content)} chars")
            
            return cleaned_content, normalized_content, content_hash
            
        except Exception as e:
            self.logger.error(f"Error normalizing content: {e}")
            # Return fallback values
            fallback_content = raw_content[:1000] if raw_content else ""
            fallback_hash = self._generate_content_hash(fallback_content)
            return fallback_content, fallback_content, fallback_hash
    
    def _strip_html(self, html_content: str) -> str:
        """Remove HTML tags and extract clean text"""
        if not html_content:
            return ""
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Extract text
            text = soup.get_text()
            
            return text
            
        except Exception as e:
            self.logger.warning(f"HTML parsing failed, using regex fallback: {e}")
            # Fallback to regex-based HTML removal
            return self._strip_html_regex(html_content)
    
    def _strip_html_regex(self, html_content: str) -> str:
        """Fallback HTML stripping using regex"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        # Remove HTML entities
        text = re.sub(r'&[a-zA-Z]+;', ' ', text)
        return text
    
    def _clean_text(self, text: str) -> str:
        """Clean and standardize text content"""
        if not text:
            return ""
        
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        
        # Clean up whitespace around punctuation
        text = re.sub(r'\s+([\.\,\!\?\;\:])', r'\1', text)
        text = re.sub(r'([\.\,\!\?\;\:])\s+', r'\1 ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _normalize_for_comparison(self, text: str) -> str:
        """Create normalized version for similarity comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove common stop words and noise
        normalized = self._remove_common_noise(normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _remove_common_noise(self, text: str) -> str:
        """Remove common noise words and patterns"""
        # Common RSS feed noise
        noise_patterns = [
            r'\bclick here\b',
            r'\bread more\b',
            r'\bcontinue reading\b',
            r'\bsubscribe\b',
            r'\bsign up\b',
            r'\bnewsletter\b',
            r'\badvertisement\b',
            r'\bsponsored\b',
            r'\bpromoted\b'
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of normalized content"""
        if not content:
            return ""
        
        try:
            # Use normalized content for consistent hashing
            normalized = self._normalize_for_comparison(content)
            content_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
            return content_hash
        except Exception as e:
            self.logger.error(f"Error generating content hash: {e}")
            return ""
    
    def segment_content(self, content: str, max_sentences: int = 5) -> list:
        """
        Segment content into sentences for quick comparison
        
        Args:
            content: Clean text content
            max_sentences: Maximum number of sentences to return
            
        Returns:
            List of key sentences
        """
        if not content:
            return []
        
        try:
            # Simple sentence splitting (can be enhanced with NLTK later)
            sentences = re.split(r'[.!?]+', content)
            
            # Clean and filter sentences
            clean_sentences = []
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20:  # Only keep meaningful sentences
                    clean_sentences.append(sentence)
            
            # Return first N sentences
            return clean_sentences[:max_sentences]
            
        except Exception as e:
            self.logger.error(f"Error segmenting content: {e}")
            return [content[:200]]  # Fallback to first 200 chars
    
    def get_content_metrics(self, content: str) -> dict:
        """
        Get content metrics for analysis
        
        Args:
            content: Clean text content
            
        Returns:
            Dictionary of content metrics
        """
        if not content:
            return {}
        
        try:
            words = content.split()
            sentences = len(re.split(r'[.!?]+', content))
            
            metrics = {
                'word_count': len(words),
                'sentence_count': sentences,
                'avg_words_per_sentence': len(words) / max(sentences, 1),
                'content_length': len(content),
                'has_content': len(content.strip()) > 0
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating content metrics: {e}")
            return {}
