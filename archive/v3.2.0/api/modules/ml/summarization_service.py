"""
ML Summarization Service for News Intelligence System
Provides AI-powered summarization using Ollama and Llama 3.1 70B
"""

import requests
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class MLSummarizationService:
    """
    AI-powered summarization service using Ollama and Llama 3.1 70B
    """
    
    def __init__(self, ollama_url: str = "http://192.168.93.92:11434", model_name: str = "llama3.1:70b-instruct-q4_K_M"):
        """
        Initialize the ML Summarization Service
        
        Args:
            ollama_url: URL of the Ollama service
            model_name: Name of the model to use for summarization
        """
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.timeout = 300  # 5 minutes timeout for large models
        
        # Test connection on initialization
        self._test_connection()
    
    def _test_connection(self) -> bool:
        """Test connection to Ollama service"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                
                if self.model_name in model_names:
                    logger.info(f"✅ Ollama connection successful. Model '{self.model_name}' available.")
                    return True
                else:
                    logger.warning(f"⚠️ Model '{self.model_name}' not found. Available models: {model_names}")
                    return False
            else:
                logger.error(f"❌ Ollama connection failed. Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ollama connection error: {e}")
            return False
    
    def _call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """
        Make a call to Ollama API
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Generated text response
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent summaries
                    "top_p": 0.9,
                    "num_predict": 2000,  # Significantly increased for comprehensive analysis
                    "stop": ["\n\n\n\n", "---", "##", "###", "####"]
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            logger.info(f"🤖 Calling Ollama with model: {self.model_name}")
            start_time = time.time()
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                generation_time = time.time() - start_time
                
                logger.info(f"✅ Ollama response received in {generation_time:.2f}s")
                return response_text
            else:
                logger.error(f"❌ Ollama API error: {response.status_code} - {response.text}")
                return ""
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Ollama request timeout after {self.timeout}s")
            return ""
        except Exception as e:
            logger.error(f"❌ Ollama API error: {e}")
            return ""
    
    def generate_summary(self, article_content: str, article_title: str = None) -> Dict[str, any]:
        """
        Generate a concise summary of an article
        
        Args:
            article_content: The full article content
            article_title: Optional article title for context
            
        Returns:
            Dictionary containing summary and metadata
        """
        try:
            # Truncate content if too long (models have token limits)
            max_content_length = 4000  # Approximate token limit
            if len(article_content) > max_content_length:
                article_content = article_content[:max_content_length] + "..."
            
            # Create system prompt for detailed, comprehensive analysis
            system_prompt = """You are a professional intelligence analyst and news summarizer. Create comprehensive, detailed summaries that capture all key information without bias. Focus on facts, main events, important details, and provide thorough analysis.

For controversial or debated topics, provide extensive balanced analysis including:
- Detailed summary of different perspectives and arguments
- Comprehensive assessment of argument strength and evidence quality
- In-depth analysis of key points from all sides of the debate
- Rich context about the controversy or disagreement
- Historical context and implications
- Expert opinions and stakeholder perspectives

Prioritize depth and completeness over brevity. Use the full capacity of your analysis to provide comprehensive coverage. Maintain journalistic objectivity while acknowledging multiple viewpoints when they exist. Include relevant background information, context, and implications."""
            
            # Create user prompt for detailed analysis
            if article_title:
                prompt = f"Article Title: {article_title}\n\nArticle Content: {article_content}\n\nProvide a comprehensive, detailed analysis of this news article. Structure your response as follows:\n\n**EXECUTIVE SUMMARY** (2-3 sentences)\nProvide a brief overview of the main story.\n\n**DETAILED ANALYSIS**\nProvide thorough coverage including:\n- Complete breakdown of all key facts and events\n- Detailed analysis of different perspectives and arguments (if applicable)\n- Comprehensive assessment of argument strength and evidence quality\n- Rich context about controversies, debates, or disagreements\n- Historical background and implications\n- Expert opinions and stakeholder perspectives\n- Potential future developments or consequences\n\n**KEY TAKEAWAYS**\nSummarize the most important points for decision-making.\n\nBe comprehensive and detailed. Use the full analytical capacity to provide thorough coverage."
            else:
                prompt = f"Article Content: {article_content}\n\nProvide a comprehensive, detailed analysis of this news article. Structure your response as follows:\n\n**EXECUTIVE SUMMARY** (2-3 sentences)\nProvide a brief overview of the main story.\n\n**DETAILED ANALYSIS**\nProvide thorough coverage including:\n- Complete breakdown of all key facts and events\n- Detailed analysis of different perspectives and arguments (if applicable)\n- Comprehensive assessment of argument strength and evidence quality\n- Rich context about controversies, debates, or disagreements\n- Historical background and implications\n- Expert opinions and stakeholder perspectives\n- Potential future developments or consequences\n\n**KEY TAKEAWAYS**\nSummarize the most important points for decision-making.\n\nBe comprehensive and detailed. Use the full analytical capacity to provide thorough coverage."
            
            # Generate summary
            summary = self._call_ollama(prompt, system_prompt)
            
            if summary:
                return {
                    "summary": summary,
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content),
                    "summary_length": len(summary),
                    "status": "success"
                }
            else:
                return {
                    "summary": "",
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content),
                    "summary_length": 0,
                    "status": "failed",
                    "error": "No response from model"
                }
                
        except Exception as e:
            logger.error(f"❌ Error generating summary: {e}")
            return {
                "summary": "",
                "model_used": self.model_name,
                "generated_at": datetime.now().isoformat(),
                "content_length": len(article_content) if article_content else 0,
                "summary_length": 0,
                "status": "failed",
                "error": str(e)
            }
    
    def extract_key_points(self, article_content: str, article_title: str = None) -> Dict[str, any]:
        """
        Extract key points from an article
        
        Args:
            article_content: The full article content
            article_title: Optional article title for context
            
        Returns:
            Dictionary containing key points and metadata
        """
        try:
            # Truncate content if too long
            max_content_length = 4000
            if len(article_content) > max_content_length:
                article_content = article_content[:max_content_length] + "..."
            
            system_prompt = """You are a professional news analyst. Extract the most important key points from news articles. Focus on facts, events, people, and significant details."""
            
            if article_title:
                prompt = f"Article Title: {article_title}\n\nArticle Content: {article_content}\n\nExtract 3-5 key points from this article. Format each point as a bullet point starting with '•'."
            else:
                prompt = f"Article Content: {article_content}\n\nExtract 3-5 key points from this article. Format each point as a bullet point starting with '•'."
            
            key_points_text = self._call_ollama(prompt, system_prompt)
            
            if key_points_text:
                # Parse bullet points
                key_points = []
                for line in key_points_text.split('\n'):
                    line = line.strip()
                    if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                        key_points.append(line[1:].strip())
                
                return {
                    "key_points": key_points,
                    "key_points_text": key_points_text,
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content),
                    "points_count": len(key_points),
                    "status": "success"
                }
            else:
                return {
                    "key_points": [],
                    "key_points_text": "",
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content) if article_content else 0,
                    "points_count": 0,
                    "status": "failed",
                    "error": "No response from model"
                }
                
        except Exception as e:
            logger.error(f"❌ Error extracting key points: {e}")
            return {
                "key_points": [],
                "key_points_text": "",
                "model_used": self.model_name,
                "generated_at": datetime.now().isoformat(),
                "content_length": len(article_content) if article_content else 0,
                "points_count": 0,
                "status": "failed",
                "error": str(e)
            }
    
    def analyze_arguments(self, article_content: str, article_title: str = None) -> Dict[str, any]:
        """
        Analyze arguments and perspectives in controversial content
        
        Args:
            article_content: The article content to analyze
            article_title: Optional article title for context
            
        Returns:
            Dictionary containing argument analysis results
        """
        try:
            max_content_length = 3000
            if len(article_content) > max_content_length:
                article_content = article_content[:max_content_length] + "..."
            
            system_prompt = """You are a professional debate analyst and fact-checker. Analyze arguments objectively, identifying different perspectives, assessing evidence quality, and evaluating argument strength. Maintain neutrality while providing clear analysis of competing viewpoints."""
            
            if article_title:
                prompt = f"Article Title: {article_title}\n\nArticle Content: {article_content}\n\nAnalyze this article for arguments and perspectives. Provide:\n\n1. **Main Arguments**: What are the key arguments presented?\n2. **Different Perspectives**: What viewpoints or sides are represented?\n3. **Evidence Quality**: How well-supported are the arguments with evidence?\n4. **Argument Strength**: Which arguments appear stronger and why?\n5. **Controversy Level**: How controversial or debated is this topic?\n6. **Missing Perspectives**: Are there important viewpoints not represented?\n\nFormat your response clearly with headings for each section."
            else:
                prompt = f"Article Content: {article_content}\n\nAnalyze this article for arguments and perspectives. Provide:\n\n1. **Main Arguments**: What are the key arguments presented?\n2. **Different Perspectives**: What viewpoints or sides are represented?\n3. **Evidence Quality**: How well-supported are the arguments with evidence?\n4. **Argument Strength**: Which arguments appear stronger and why?\n5. **Controversy Level**: How controversial or debated is this topic?\n6. **Missing Perspectives**: Are there important viewpoints not represented?\n\nFormat your response clearly with headings for each section."
            
            analysis_response = self._call_ollama(prompt, system_prompt)
            
            if analysis_response:
                return {
                    "argument_analysis": analysis_response,
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content),
                    "status": "success"
                }
            else:
                return {
                    "argument_analysis": "",
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content) if article_content else 0,
                    "status": "failed",
                    "error": "No response from model"
                }
                
        except Exception as e:
            logger.error(f"❌ Error analyzing arguments: {e}")
            return {
                "argument_analysis": "",
                "model_used": self.model_name,
                "generated_at": datetime.now().isoformat(),
                "content_length": len(article_content) if article_content else 0,
                "status": "failed",
                "error": str(e)
            }

    def analyze_sentiment(self, article_content: str) -> Dict[str, any]:
        """
        Analyze sentiment of an article
        
        Args:
            article_content: The article content to analyze
            
        Returns:
            Dictionary containing sentiment analysis results
        """
        try:
            max_content_length = 3000
            if len(article_content) > max_content_length:
                article_content = article_content[:max_content_length] + "..."
            
            system_prompt = """You are a sentiment analysis expert. Analyze the sentiment of news articles and provide objective assessments."""
            
            prompt = f"Article Content: {article_content}\n\nAnalyze the sentiment of this article. Respond with only one word: 'positive', 'negative', or 'neutral', followed by a brief explanation in one sentence."
            
            sentiment_response = self._call_ollama(prompt, system_prompt)
            
            if sentiment_response:
                # Parse sentiment
                sentiment = "neutral"  # default
                if "positive" in sentiment_response.lower():
                    sentiment = "positive"
                elif "negative" in sentiment_response.lower():
                    sentiment = "negative"
                
                return {
                    "sentiment": sentiment,
                    "sentiment_analysis": sentiment_response,
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content),
                    "status": "success"
                }
            else:
                return {
                    "sentiment": "neutral",
                    "sentiment_analysis": "",
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "content_length": len(article_content) if article_content else 0,
                    "status": "failed",
                    "error": "No response from model"
                }
                
        except Exception as e:
            logger.error(f"❌ Error analyzing sentiment: {e}")
            return {
                "sentiment": "neutral",
                "sentiment_analysis": "",
                "model_used": self.model_name,
                "generated_at": datetime.now().isoformat(),
                "content_length": len(article_content) if article_content else 0,
                "status": "failed",
                "error": str(e)
            }
    
    def get_service_status(self) -> Dict[str, any]:
        """
        Get the current status of the ML service
        
        Returns:
            Dictionary containing service status information
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                
                return {
                    "status": "online",
                    "ollama_url": self.ollama_url,
                    "model_name": self.model_name,
                    "model_available": self.model_name in model_names,
                    "available_models": model_names,
                    "checked_at": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "offline",
                    "ollama_url": self.ollama_url,
                    "model_name": self.model_name,
                    "model_available": False,
                    "available_models": [],
                    "checked_at": datetime.now().isoformat(),
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "ollama_url": self.ollama_url,
                "model_name": self.model_name,
                "model_available": False,
                "available_models": [],
                "checked_at": datetime.now().isoformat(),
                "error": str(e)
            }
