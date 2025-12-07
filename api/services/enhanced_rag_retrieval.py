"""
Enhanced RAG Retrieval Service
Implements advanced retrieval techniques for better context gathering:
- Semantic search using embeddings
- Hybrid search (keyword + semantic)
- Query expansion
- Multi-signal re-ranking
- Improved entity extraction
"""

import logging
import json
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

class EnhancedRAGRetrieval:
    """Enhanced RAG retrieval with semantic search and hybrid matching"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.embedding_model = None
        self._load_embedding_model()
        
        # Configuration
        self.config = {
            'embedding_model': 'all-MiniLM-L6-v2',  # Lightweight, fast model
            'max_results_initial': 100,  # Initial retrieval before re-ranking
            'max_results_final': 25,     # Final results after re-ranking
            'hybrid_search_alpha': 0.7,  # Weight for semantic (0.7) vs keyword (0.3)
            'similarity_threshold': 0.3, # Minimum semantic similarity
            'rerank_top_k': 50,          # Top K for re-ranking
            'query_expansion_max_terms': 5,  # Max terms for query expansion
        }
    
    def _load_embedding_model(self):
        """Load sentence transformer model for embeddings"""
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
    
    async def retrieve_relevant_articles(
        self,
        query: str,
        max_results: int = None,
        use_semantic: bool = True,
        use_hybrid: bool = True,
        expand_query: bool = True,
        rerank: bool = True,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant articles using enhanced RAG techniques
        
        Args:
            query: Search query
            max_results: Maximum number of results
            use_semantic: Use semantic search
            use_hybrid: Use hybrid search (keyword + semantic)
            expand_query: Expand query with related terms
            rerank: Re-rank results using multiple signals
            filters: Additional filters (date range, quality, etc.)
        
        Returns:
            List of relevant articles with relevance scores
        """
        try:
            if max_results is None:
                max_results = self.config['max_results_final']
            
            logger.info(f"Enhanced RAG retrieval for query: {query}")
            
            # Step 1: Query expansion
            if expand_query:
                expanded_query = self._expand_query(query)
                logger.debug(f"Expanded query: {expanded_query}")
            else:
                expanded_query = query
            
            # Step 2: Initial retrieval
            if use_hybrid and self.embedding_model:
                # Hybrid search (keyword + semantic)
                initial_results = await self._hybrid_search(
                    query, expanded_query, 
                    self.config['max_results_initial'], 
                    filters
                )
            elif use_semantic and self.embedding_model:
                # Semantic search only
                initial_results = await self._semantic_search(
                    query, 
                    self.config['max_results_initial'], 
                    filters
                )
            else:
                # Keyword search only (fallback)
                initial_results = await self._keyword_search(
                    expanded_query, 
                    self.config['max_results_initial'], 
                    filters
                )
            
            if not initial_results:
                logger.warning("No articles found in initial retrieval")
                return []
            
            logger.info(f"Initial retrieval found {len(initial_results)} articles")
            
            # Step 3: Re-ranking
            if rerank and len(initial_results) > 1:
                reranked_results = self._rerank_results(
                    query, initial_results, max_results
                )
                return reranked_results
            else:
                return initial_results[:max_results]
            
        except Exception as e:
            logger.error(f"Error in enhanced RAG retrieval: {e}")
            # Fallback to simple keyword search
            return await self._keyword_search(query, max_results or 25, filters or {})
    
    async def _hybrid_search(
        self,
        original_query: str,
        expanded_query: str,
        max_results: int,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining keyword and semantic similarity"""
        try:
            # Get keyword search results
            keyword_results = await self._keyword_search(
                expanded_query, max_results * 2, filters
            )
            
            if not keyword_results:
                return await self._semantic_search(original_query, max_results, filters)
            
            # Get semantic search results
            semantic_results = await self._semantic_search(
                original_query, max_results * 2, filters
            )
            
            if not semantic_results:
                return keyword_results[:max_results]
            
            # Combine and merge results
            combined = self._merge_hybrid_results(
                keyword_results, semantic_results, max_results
            )
            
            return combined
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return await self._keyword_search(expanded_query, max_results, filters)
    
    async def _keyword_search(
        self,
        query: str,
        max_results: int,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Keyword-based search using PostgreSQL full-text search"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Extract keywords
            keywords = self._extract_keywords(query)
            
            # Build WHERE conditions
            conditions = []
            params = []
            
            if keywords:
                # Full-text search on title, content, and summary
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append(
                        "(LOWER(title) LIKE %s OR LOWER(content) LIKE %s OR LOWER(excerpt) LIKE %s)"
                    )
                    pattern = f'%{keyword.lower()}%'
                    params.extend([pattern, pattern, pattern])
                
                conditions.append(f"({' OR '.join(keyword_conditions)})")
            else:
                # No keywords, return recent articles
                conditions.append("1=1")
            
            # Apply filters
            if filters:
                if filters.get('min_quality'):
                    conditions.append("quality_score >= %s")
                    params.append(filters['min_quality'])
                
                if filters.get('date_from'):
                    conditions.append("published_at >= %s")
                    params.append(filters['date_from'])
                
                if filters.get('date_to'):
                    conditions.append("published_at <= %s")
                    params.append(filters['date_to'])
                
                if filters.get('min_word_count'):
                    conditions.append("word_count >= %s")
                    params.append(filters['min_word_count'])
            
            # Quality threshold
            conditions.append("quality_score >= 0.3")
            
            where_clause = " AND ".join(conditions)
            
            query_sql = f"""
                SELECT 
                    id, title, content, excerpt, summary,
                    url, published_at, source_domain, publisher,
                    quality_score, readability_score, credibility_score,
                    sentiment_label, sentiment_score,
                    entities, topics, keywords,
                    processing_status, created_at
                FROM articles
                WHERE {where_clause}
                ORDER BY 
                    quality_score DESC,
                    published_at DESC
                LIMIT %s
            """
            
            params.append(max_results)
            
            cursor.execute(query_sql, params)
            rows = cursor.fetchall()
            
            articles = []
            for row in rows:
                articles.append({
                    'id': row['id'],
                    'title': row['title'] or '',
                    'content': row['content'] or '',
                    'excerpt': row['excerpt'] or '',
                    'summary': row['summary'] or '',
                    'url': row['url'] or '',
                    'published_at': row['published_at'].isoformat() if row['published_at'] else None,
                    'source_domain': row['source_domain'] or '',
                    'publisher': row['publisher'] or '',
                    'quality_score': float(row['quality_score']) if row['quality_score'] else 0.0,
                    'readability_score': float(row['readability_score']) if row['readability_score'] else 0.0,
                    'credibility_score': float(row['credibility_score']) if row['credibility_score'] else 0.0,
                    'sentiment': {
                        'label': row['sentiment_label'],
                        'score': float(row['sentiment_score']) if row['sentiment_score'] else 0.0
                    },
                    'entities': row['entities'] if isinstance(row['entities'], dict) else json.loads(row['entities']) if row['entities'] else {},
                    'topics': row['topics'] if isinstance(row['topics'], list) else json.loads(row['topics']) if row['topics'] else [],
                    'keywords': row['keywords'] if isinstance(row['keywords'], list) else json.loads(row['keywords']) if row['keywords'] else [],
                    'relevance_score': 0.5,  # Default keyword match score
                    'retrieval_method': 'keyword'
                })
            
            conn.close()
            return articles
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    async def _semantic_search(
        self,
        query: str,
        max_results: int,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Semantic search using embeddings"""
        try:
            if not self.embedding_model:
                logger.warning("Embedding model not available, falling back to keyword search")
                return await self._keyword_search(query, max_results, filters)
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])[0]
            
            # Get candidate articles (larger pool for semantic matching)
            candidates = await self._keyword_search(query, max_results * 3, filters)
            
            if not candidates:
                return []
            
            # Compute semantic similarities
            similarities = []
            for article in candidates:
                # Use title + excerpt + summary for embedding
                article_text = f"{article.get('title', '')} {article.get('excerpt', '')} {article.get('summary', '')}"
                article_text = article_text[:1000]  # Limit length
                
                if article_text:
                    article_embedding = self.embedding_model.encode([article_text])[0]
                    similarity = float(np.dot(query_embedding, article_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(article_embedding)
                    ))
                    
                    if similarity >= self.config['similarity_threshold']:
                        article['relevance_score'] = similarity
                        article['retrieval_method'] = 'semantic'
                        similarities.append((similarity, article))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[0], reverse=True)
            
            # Return top results
            return [article for _, article in similarities[:max_results]]
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return await self._keyword_search(query, max_results, filters)
    
    def _merge_hybrid_results(
        self,
        keyword_results: List[Dict[str, Any]],
        semantic_results: List[Dict[str, Any]],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Merge keyword and semantic search results"""
        try:
            # Create article ID to result mapping
            merged = {}
            alpha = self.config['hybrid_search_alpha']
            
            # Process keyword results
            for i, article in enumerate(keyword_results):
                article_id = article['id']
                if article_id not in merged:
                    merged[article_id] = article.copy()
                    # Normalize keyword score (rank-based)
                    keyword_score = 1.0 - (i / max(len(keyword_results), 1))
                    merged[article_id]['keyword_score'] = keyword_score
                else:
                    keyword_score = 1.0 - (i / max(len(keyword_results), 1))
                    merged[article_id]['keyword_score'] = max(
                        merged[article_id].get('keyword_score', 0),
                        keyword_score
                    )
            
            # Process semantic results
            for article in semantic_results:
                article_id = article['id']
                if article_id not in merged:
                    merged[article_id] = article.copy()
                    merged[article_id]['semantic_score'] = article.get('relevance_score', 0)
                else:
                    merged[article_id]['semantic_score'] = article.get('relevance_score', 0)
            
            # Calculate hybrid scores
            for article_id, article in merged.items():
                keyword_score = article.get('keyword_score', 0)
                semantic_score = article.get('semantic_score', 0)
                
                # Hybrid score: weighted combination
                hybrid_score = (alpha * semantic_score) + ((1 - alpha) * keyword_score)
                article['relevance_score'] = hybrid_score
                article['retrieval_method'] = 'hybrid'
            
            # Sort by hybrid score
            sorted_articles = sorted(
                merged.values(),
                key=lambda x: x['relevance_score'],
                reverse=True
            )
            
            return sorted_articles[:max_results]
            
        except Exception as e:
            logger.error(f"Error merging hybrid results: {e}")
            # Fallback: return keyword results
            return keyword_results[:max_results]
    
    def _expand_query(self, query: str) -> str:
        """Expand query with related terms and synonyms"""
        try:
            # Extract keywords
            keywords = self._extract_keywords(query)
            if not keywords:
                return query
            
            expanded_terms = list(keywords)
            
            # Simple synonym expansion (can be enhanced with WordNet or other tools)
            synonym_map = {
                'ai': ['artificial intelligence', 'machine learning', 'automation'],
                'tech': ['technology', 'innovation', 'digital'],
                'company': ['corporation', 'business', 'firm', 'organization'],
                'market': ['economy', 'trading', 'financial'],
                'government': ['federal', 'state', 'official', 'administration'],
                'policy': ['regulation', 'law', 'legislation', 'rule'],
            }
            
            for keyword in keywords[:self.config['query_expansion_max_terms']]:
                keyword_lower = keyword.lower()
                if keyword_lower in synonym_map:
                    expanded_terms.extend(synonym_map[keyword_lower][:2])  # Add 2 synonyms
            
            # Also add variations
            for keyword in keywords:
                # Plural/singular variations
                if keyword.endswith('s'):
                    expanded_terms.append(keyword[:-1])
                elif not keyword.endswith('s'):
                    expanded_terms.append(keyword + 's')
            
            expanded_query = ' '.join(expanded_terms)
            return expanded_query
            
        except Exception as e:
            logger.error(f"Error expanding query: {e}")
            return query
    
    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Re-rank results using multiple signals"""
        try:
            if len(results) <= 1:
                return results
            
            # Calculate reranking scores
            reranked = []
            for article in results:
                rerank_score = self._calculate_rerank_score(query, article)
                article['rerank_score'] = rerank_score
                reranked.append(article)
            
            # Sort by rerank score
            reranked.sort(key=lambda x: x['rerank_score'], reverse=True)
            
            return reranked[:max_results]
            
        except Exception as e:
            logger.error(f"Error re-ranking results: {e}")
            return results[:max_results]
    
    def _calculate_rerank_score(
        self,
        query: str,
        article: Dict[str, Any]
    ) -> float:
        """Calculate rerank score using multiple signals"""
        try:
            scores = {}
            
            # 1. Relevance score (semantic/keyword match)
            relevance_score = article.get('relevance_score', 0.5)
            scores['relevance'] = relevance_score * 0.4  # 40% weight
            
            # 2. Quality score
            quality_score = article.get('quality_score', 0.5)
            scores['quality'] = quality_score * 0.2  # 20% weight
            
            # 3. Recency score (recent articles get boost)
            published_at = article.get('published_at')
            if published_at:
                try:
                    if isinstance(published_at, str):
                        pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    else:
                        pub_date = published_at
                    
                    days_ago = (datetime.now(pub_date.tzinfo) - pub_date).days
                    # Recency boost: articles from last 7 days get full score
                    recency_score = max(0, 1.0 - (days_ago / 30.0))
                    recency_score = min(1.0, recency_score)
                    scores['recency'] = recency_score * 0.2  # 20% weight
                except:
                    scores['recency'] = 0.1
            else:
                scores['recency'] = 0.1
            
            # 4. Title match boost (exact matches in title get boost)
            query_lower = query.lower()
            title_lower = article.get('title', '').lower()
            
            title_match_score = 0.0
            query_words = set(query_lower.split())
            title_words = set(title_lower.split())
            
            if query_words:
                match_ratio = len(query_words.intersection(title_words)) / len(query_words)
                title_match_score = match_ratio
            scores['title_match'] = title_match_score * 0.1  # 10% weight
            
            # 5. Credibility score
            credibility_score = article.get('credibility_score', 0.5)
            scores['credibility'] = credibility_score * 0.1  # 10% weight
            
            # Total rerank score
            total_score = sum(scores.values())
            
            return total_score
            
        except Exception as e:
            logger.error(f"Error calculating rerank score: {e}")
            return article.get('relevance_score', 0.5)
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query"""
        try:
            # Remove common stop words
            stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
            }
            
            # Extract words
            words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
            keywords = [word for word in words if word not in stop_words and len(word) > 2]
            
            return keywords[:10]  # Limit to 10 keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    def generate_article_embedding(self, article: Dict[str, Any]) -> Optional[np.ndarray]:
        """Generate embedding for an article"""
        try:
            if not self.embedding_model:
                return None
            
            # Combine title, excerpt, and summary
            text = f"{article.get('title', '')} {article.get('excerpt', '')} {article.get('summary', '')}"
            text = text[:1000]  # Limit length
            
            if not text.strip():
                return None
            
            embedding = self.embedding_model.encode([text])[0]
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating article embedding: {e}")
            return None
    
    async def store_article_embedding(self, article_id: int, embedding: np.ndarray):
        """Store article embedding in database metadata"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Store embedding in metadata JSONB field
            embedding_list = embedding.tolist()
            
            cursor.execute("""
                UPDATE articles
                SET metadata = COALESCE(metadata, '{}'::jsonb) || 
                    jsonb_build_object('embedding', %s::jsonb, 'embedding_generated_at', %s)
                WHERE id = %s
            """, (json.dumps(embedding_list), datetime.now().isoformat(), article_id))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Stored embedding for article {article_id}")
            
        except Exception as e:
            logger.error(f"Error storing article embedding: {e}")
