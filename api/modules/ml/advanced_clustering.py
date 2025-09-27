"""
Advanced Clustering Module for News Intelligence System v3.0
Uses local LLM models via Ollama for intelligent document clustering
"""

import logging
import json
import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import requests
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
import re

logger = logging.getLogger(__name__)

@dataclass
class ClusterResult:
    """Structured clustering result"""
    cluster_id: int
    articles: List[Dict[str, Any]]
    centroid: List[float]
    size: int
    keywords: List[str]
    summary: str
    coherence_score: float
    local_processing: bool = True

@dataclass
class ClusteringAnalysis:
    """Complete clustering analysis result"""
    clusters: List[ClusterResult]
    total_articles: int
    num_clusters: int
    algorithm_used: str
    silhouette_score: float
    processing_time: float
    model_used: str
    local_processing: bool = True

class LocalAdvancedClustering:
    """
    Local advanced clustering using Ollama models
    No training required - uses pre-trained embeddings and clustering algorithms
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.available_models = ["llama3.1:70b", "llama3.1:70b", "nomic-embed-text"]
        self.default_model = "nomic-embed-text"  # Best for embeddings
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Clustering algorithms
        self.algorithms = {
            'kmeans': KMeans,
            'dbscan': DBSCAN,
            'agglomerative': AgglomerativeClustering
        }
    
    def cluster_articles(self, 
                        articles: List[Dict[str, Any]], 
                        algorithm: str = 'kmeans',
                        num_clusters: Optional[int] = None,
                        model: Optional[str] = None,
                        use_cache: bool = True) -> ClusteringAnalysis:
        """
        Cluster articles using advanced algorithms
        
        Args:
            articles: List of articles to cluster
            algorithm: Clustering algorithm to use
            num_clusters: Number of clusters (auto-determined if None)
            model: Specific model to use (optional)
            use_cache: Whether to use cached results
            
        Returns:
            ClusteringAnalysis with cluster results
        """
        try:
            start_time = time.time()
            
            if not articles or len(articles) < 2:
                raise ValueError("Need at least 2 articles to cluster")
            
            # Check cache first
            if use_cache:
                cache_key = f"{hash(str(articles))}_{algorithm}_{num_clusters}_{model or self.default_model}"
                if cache_key in self.cache:
                    cached_result = self.cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self.cache_ttl:
                        logger.info(f"Using cached clustering result for {len(articles)} articles")
                        return ClusteringAnalysis(**cached_result['data'])
            
            # Select model
            selected_model = model or self.default_model
            if selected_model not in self.available_models:
                logger.warning(f"Model {selected_model} not available, using {self.default_model}")
                selected_model = self.default_model
            
            # Prepare text data
            texts = [self._prepare_article_text(article) for article in articles]
            
            # Generate embeddings
            embeddings = self._generate_embeddings(texts, selected_model)
            
            # Determine optimal number of clusters
            if num_clusters is None:
                num_clusters = self._find_optimal_clusters(embeddings, algorithm)
            
            # Perform clustering
            cluster_labels = self._perform_clustering(embeddings, algorithm, num_clusters)
            
            # Create cluster results
            clusters = self._create_cluster_results(articles, cluster_labels, embeddings, selected_model)
            
            # Calculate silhouette score
            silhouette = self._calculate_silhouette_score(embeddings, cluster_labels)
            
            # Create analysis result
            processing_time = time.time() - start_time
            
            result = ClusteringAnalysis(
                clusters=clusters,
                total_articles=len(articles),
                num_clusters=len(clusters),
                algorithm_used=algorithm,
                silhouette_score=silhouette,
                processing_time=processing_time,
                model_used=selected_model
            )
            
            # Cache result
            if use_cache:
                self.cache[cache_key] = {
                    'data': {
                        'clusters': [
                            {
                                'cluster_id': cluster.cluster_id,
                                'articles': cluster.articles,
                                'centroid': cluster.centroid,
                                'size': cluster.size,
                                'keywords': cluster.keywords,
                                'summary': cluster.summary,
                                'coherence_score': cluster.coherence_score,
                                'local_processing': cluster.local_processing
                            } for cluster in clusters
                        ],
                        'total_articles': len(articles),
                        'num_clusters': len(clusters),
                        'algorithm_used': algorithm,
                        'silhouette_score': silhouette,
                        'processing_time': processing_time,
                        'model_used': selected_model,
                        'local_processing': True
                    },
                    'timestamp': time.time()
                }
            
            logger.info(f"Clustering completed in {processing_time:.2f}s: {len(clusters)} clusters found")
            return result
            
        except Exception as e:
            logger.error(f"Error in clustering: {e}")
            # Return empty result on error
            return ClusteringAnalysis(
                clusters=[],
                total_articles=len(articles) if articles else 0,
                num_clusters=0,
                algorithm_used=algorithm,
                silhouette_score=0.0,
                processing_time=time.time() - start_time,
                model_used=selected_model
            )
    
    def _prepare_article_text(self, article: Dict[str, Any]) -> str:
        """Prepare article text for clustering"""
        # Combine title, content, and summary
        text_parts = []
        
        if article.get('title'):
            text_parts.append(article['title'])
        
        if article.get('content'):
            # Clean and truncate content
            content = re.sub(r'<[^>]+>', '', str(article['content']))
            content = content[:1000]  # Limit length
            text_parts.append(content)
        
        if article.get('summary'):
            text_parts.append(article['summary'])
        
        return ' '.join(text_parts)
    
    def _generate_embeddings(self, texts: List[str], model: str) -> np.ndarray:
        """Generate embeddings using local LLM"""
        try:
            if model == "nomic-embed-text":
                # Use specialized embedding model
                embeddings = self._call_embedding_model(texts, model)
            else:
                # Use general LLM for embeddings
                embeddings = self._call_llm_for_embeddings(texts, model)
            
            return np.array(embeddings)
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Fallback to TF-IDF
            return self._generate_tfidf_embeddings(texts)
    
    def _call_embedding_model(self, texts: List[str], model: str) -> List[List[float]]:
        """Call specialized embedding model"""
        try:
            embeddings = []
            
            for text in texts:
                response = requests.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={
                        "model": model,
                        "prompt": text
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get('embedding', [])
                    embeddings.append(embedding)
                else:
                    raise Exception(f"Embedding API error: {response.status_code}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error calling embedding model: {e}")
            raise
    
    def _call_llm_for_embeddings(self, texts: List[str], model: str) -> List[List[float]]:
        """Use general LLM to generate embeddings"""
        try:
            embeddings = []
            
            for text in texts:
                # Create prompt for embedding generation
                prompt = f"""
Convert the following text into a numerical vector representation (embedding) that captures its semantic meaning.

Text: "{text}"

Provide the embedding as a JSON array of numbers between -1 and 1.
The embedding should be 384 numbers long.

Format: [0.1, -0.2, 0.3, ...]
"""
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 500
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Parse response to extract embedding
                    result = ""
                    for line in response.text.split('\n'):
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if 'response' in data:
                                    result += data['response']
                            except json.JSONDecodeError:
                                continue
                    
                    # Extract embedding from response
                    embedding = self._parse_embedding_response(result)
                    embeddings.append(embedding)
                else:
                    raise Exception(f"LLM API error: {response.status_code}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error calling LLM for embeddings: {e}")
            raise
    
    def _parse_embedding_response(self, response: str) -> List[float]:
        """Parse LLM response to extract embedding"""
        try:
            # Try to find JSON array in response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                embedding = json.loads(json_str)
                
                # Ensure it's a list of numbers
                if isinstance(embedding, list) and all(isinstance(x, (int, float)) for x in embedding):
                    # Normalize to -1 to 1 range
                    embedding = [max(-1, min(1, float(x))) for x in embedding]
                    return embedding
            
            # Fallback: generate random embedding
            return [np.random.uniform(-1, 1) for _ in range(384)]
            
        except Exception as e:
            logger.error(f"Error parsing embedding response: {e}")
            return [np.random.uniform(-1, 1) for _ in range(384)]
    
    def _generate_tfidf_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate TF-IDF embeddings as fallback"""
        try:
            vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
            tfidf_matrix = vectorizer.fit_transform(texts)
            return tfidf_matrix.toarray()
            
        except Exception as e:
            logger.error(f"Error generating TF-IDF embeddings: {e}")
            # Return random embeddings as last resort
            return np.random.rand(len(texts), 100)
    
    def _find_optimal_clusters(self, embeddings: np.ndarray, algorithm: str) -> int:
        """Find optimal number of clusters using silhouette score"""
        try:
            if len(embeddings) < 2:
                return 1
            
            max_clusters = min(10, len(embeddings) // 2)
            if max_clusters < 2:
                return 2
            
            best_k = 2
            best_score = -1
            
            for k in range(2, max_clusters + 1):
                try:
                    if algorithm == 'kmeans':
                        clusterer = KMeans(n_clusters=k, random_state=42)
                    elif algorithm == 'agglomerative':
                        clusterer = AgglomerativeClustering(n_clusters=k)
                    else:
                        continue
                    
                    cluster_labels = clusterer.fit_predict(embeddings)
                    score = silhouette_score(embeddings, cluster_labels)
                    
                    if score > best_score:
                        best_score = score
                        best_k = k
                        
                except Exception:
                    continue
            
            return best_k
            
        except Exception as e:
            logger.error(f"Error finding optimal clusters: {e}")
            return 3  # Default fallback
    
    def _perform_clustering(self, embeddings: np.ndarray, algorithm: str, num_clusters: int) -> np.ndarray:
        """Perform clustering using specified algorithm"""
        try:
            if algorithm == 'kmeans':
                clusterer = KMeans(n_clusters=num_clusters, random_state=42)
            elif algorithm == 'dbscan':
                clusterer = DBSCAN(eps=0.5, min_samples=2)
            elif algorithm == 'agglomerative':
                clusterer = AgglomerativeClustering(n_clusters=num_clusters)
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")
            
            cluster_labels = clusterer.fit_predict(embeddings)
            return cluster_labels
            
        except Exception as e:
            logger.error(f"Error performing clustering: {e}")
            # Return single cluster as fallback
            return np.zeros(len(embeddings), dtype=int)
    
    def _create_cluster_results(self, articles: List[Dict[str, Any]], 
                               cluster_labels: np.ndarray, 
                               embeddings: np.ndarray,
                               model: str) -> List[ClusterResult]:
        """Create cluster results from clustering output"""
        try:
            clusters = []
            unique_labels = np.unique(cluster_labels)
            
            for label in unique_labels:
                if label == -1:  # Skip noise points in DBSCAN
                    continue
                
                # Get articles in this cluster
                cluster_indices = np.where(cluster_labels == label)[0]
                cluster_articles = [articles[i] for i in cluster_indices]
                cluster_embeddings = embeddings[cluster_indices]
                
                # Calculate centroid
                centroid = np.mean(cluster_embeddings, axis=0).tolist()
                
                # Generate keywords and summary
                keywords, summary = self._analyze_cluster_content(cluster_articles, model)
                
                # Calculate coherence score
                coherence = self._calculate_cluster_coherence(cluster_embeddings)
                
                cluster_result = ClusterResult(
                    cluster_id=int(label),
                    articles=cluster_articles,
                    centroid=centroid,
                    size=len(cluster_articles),
                    keywords=keywords,
                    summary=summary,
                    coherence_score=coherence
                )
                
                clusters.append(cluster_result)
            
            return clusters
            
        except Exception as e:
            logger.error(f"Error creating cluster results: {e}")
            return []
    
    def _analyze_cluster_content(self, articles: List[Dict[str, Any]], model: str) -> Tuple[List[str], str]:
        """Analyze cluster content to generate keywords and summary"""
        try:
            # Combine all article texts
            combined_text = " ".join([
                self._prepare_article_text(article) for article in articles
            ])
            
            # Create prompt for analysis
            prompt = f"""
Analyze the following collection of articles and provide keywords and a summary.

Articles: {combined_text[:2000]}

Please provide your analysis in the following JSON format:
{{
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "summary": "Brief summary of the main topics covered in these articles"
}}

Guidelines:
- Extract 5 most important keywords
- Write a concise summary (1-2 sentences)
- Focus on common themes and topics
- Be objective and factual
"""
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 300
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = ""
                for line in response.text.split('\n'):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if 'response' in data:
                                result += data['response']
                        except json.JSONDecodeError:
                            continue
                
                # Parse response
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = result[json_start:json_end]
                    data = json.loads(json_str)
                    return data.get('keywords', []), data.get('summary', 'No summary available')
            
            # Fallback
            return ["topic1", "topic2", "topic3"], "Cluster of related articles"
            
        except Exception as e:
            logger.error(f"Error analyzing cluster content: {e}")
            return ["topic1", "topic2", "topic3"], "Cluster of related articles"
    
    def _calculate_cluster_coherence(self, embeddings: np.ndarray) -> float:
        """Calculate cluster coherence score"""
        try:
            if len(embeddings) < 2:
                return 1.0
            
            # Calculate average pairwise cosine similarity
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    similarity = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarities.append(similarity)
            
            return float(np.mean(similarities)) if similarities else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating cluster coherence: {e}")
            return 0.0
    
    def _calculate_silhouette_score(self, embeddings: np.ndarray, cluster_labels: np.ndarray) -> float:
        """Calculate silhouette score for clustering quality"""
        try:
            if len(np.unique(cluster_labels)) < 2:
                return 0.0
            
            return float(silhouette_score(embeddings, cluster_labels))
            
        except Exception as e:
            logger.error(f"Error calculating silhouette score: {e}")
            return 0.0
    
    def clear_cache(self):
        """Clear the clustering cache"""
        self.cache.clear()
        logger.info("Clustering cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_ttl": self.cache_ttl,
            "available_models": self.available_models,
            "default_model": self.default_model,
            "algorithms": list(self.algorithms.keys())
        }

# Global instance
advanced_clustering = LocalAdvancedClustering()


