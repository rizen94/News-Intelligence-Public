"""
News Intelligence System v3.1.0 - AI Processing Service
Local AI processing using Ollama for story analysis and journalistic reporting
"""

import os
import json
import logging
import asyncio
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logger = logging.getLogger(__name__)

class AIProcessingService:
    """Local AI processing service using Ollama"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.available_models = {
            'llama3.1:70b-instruct-q4_K_M': {
                'name': 'llama3.1:70b-instruct-q4_K_M',
                'description': 'Large language model for complex analysis',
                'max_tokens': 4096,
                'temperature': 0.7,
                'use_case': 'comprehensive_analysis'
            },
            'deepseek-coder:33b': {
                'name': 'deepseek-coder:33b',
                'description': 'Code-focused model for technical analysis',
                'max_tokens': 8192,
                'temperature': 0.3,
                'use_case': 'technical_analysis'
            }
        }
        
    async def check_ollama_health(self) -> Dict[str, Any]:
        """Check if Ollama is running and models are available"""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = [model['name'] for model in data.get('models', [])]
                return {
                    'status': 'healthy',
                    'models_available': len(models),
                    'models': models,
                    'base_url': self.ollama_base_url
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': f'Ollama returned status {response.status_code}',
                    'base_url': self.ollama_base_url
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'base_url': self.ollama_base_url
            }
    
    async def generate_story_analysis(self, story_id: str, articles: List[Dict[str, Any]], 
                                    analysis_type: str = 'comprehensive') -> Dict[str, Any]:
        """Generate comprehensive story analysis using local AI"""
        try:
            # Check if Ollama is available first
            health_status = await self.check_ollama_health()
            if health_status['status'] != 'healthy':
                return {
                    'error': 'AI processing unavailable',
                    'message': 'Ollama is not running or accessible. Please ensure Ollama is installed and running on localhost:11434',
                    'status': 'unavailable',
                    'story_id': story_id,
                    'analysis_type': analysis_type,
                    'articles_count': len(articles)
                }
            
            # Select appropriate model based on analysis type
            model_name = self._select_model(analysis_type)
            
            # Prepare context from articles
            context = self._prepare_article_context(articles)
            
            # Generate analysis prompt
            prompt = self._create_analysis_prompt(story_id, context, analysis_type)
            
            # Call Ollama API
            analysis_result = await self._call_ollama(model_name, prompt)
            
            # Parse and structure the response
            structured_analysis = self._parse_analysis_response(analysis_result, analysis_type)
            
            # Store analysis in database
            await self._store_analysis_result(story_id, analysis_type, structured_analysis)
            
            return structured_analysis
            
        except Exception as e:
            logger.error(f"Error generating story analysis: {e}")
            return {
                'error': 'AI processing failed',
                'message': f'Failed to generate story analysis: {str(e)}',
                'status': 'error',
                'story_id': story_id,
                'analysis_type': analysis_type,
                'articles_count': len(articles)
            }
    
    async def generate_consolidated_report(self, story_id: str, timeline_events: List[Dict[str, Any]], 
                                         articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate professional journalistic report"""
        try:
            # Check if Ollama is available first
            health_status = await self.check_ollama_health()
            if health_status['status'] != 'healthy':
                return {
                    'error': 'AI processing unavailable',
                    'message': 'Ollama is not running or accessible. Please ensure Ollama is installed and running on localhost:11434',
                    'status': 'unavailable',
                    'story_id': story_id,
                    'timeline_events_count': len(timeline_events),
                    'articles_count': len(articles)
                }
            
            model_name = 'llama3.1:70b-instruct-q4_K_M'  # Use the larger model for reports
            
            # Prepare comprehensive context
            context = {
                'timeline_events': timeline_events,
                'articles': articles,
                'story_id': story_id
            }
            
            # Create journalistic report prompt
            prompt = self._create_journalistic_prompt(story_id, context)
            
            # Generate report
            report_result = await self._call_ollama(model_name, prompt)
            
            # Parse and structure the report
            structured_report = self._parse_journalistic_report(report_result)
            
            # Store consolidated report
            await self._store_consolidated_report(story_id, structured_report)
            
            return structured_report
            
        except Exception as e:
            logger.error(f"Error generating consolidated report: {e}")
            return {
                'error': 'AI processing failed',
                'message': f'Failed to generate consolidated report: {str(e)}',
                'status': 'error',
                'story_id': story_id,
                'timeline_events_count': len(timeline_events),
                'articles_count': len(articles)
            }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text using local AI"""
        try:
            # Check if Ollama is available first
            health_status = await self.check_ollama_health()
            if health_status['status'] != 'healthy':
                return {
                    'error': 'AI processing unavailable',
                    'message': 'Ollama is not running or accessible. Please ensure Ollama is installed and running on localhost:11434',
                    'status': 'unavailable',
                    'text_length': len(text)
                }
            
            model_name = 'llama3.1:70b-instruct-q4_K_M'
            
            prompt = f"""
            Analyze the sentiment of the following text and provide a structured response.
            
            Text: "{text}"
            
            Please respond with a JSON object containing:
            - sentiment: "positive", "negative", or "neutral"
            - confidence: float between 0.0 and 1.0
            - reasoning: brief explanation of the analysis
            - emotional_tone: description of the emotional tone
            - key_indicators: list of words/phrases that influenced the sentiment
            
            Respond only with valid JSON.
            """
            
            result = await self._call_ollama(model_name, prompt)
            sentiment_data = self._parse_json_response(result)
            
            return {
                'sentiment': sentiment_data.get('sentiment', 'neutral'),
                'confidence': float(sentiment_data.get('confidence', 0.5)),
                'reasoning': sentiment_data.get('reasoning', ''),
                'emotional_tone': sentiment_data.get('emotional_tone', ''),
                'key_indicators': sentiment_data.get('key_indicators', []),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {
                'error': 'AI processing failed',
                'message': f'Failed to analyze sentiment: {str(e)}',
                'status': 'error',
                'text_length': len(text)
            }
    
    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from text using local AI"""
        try:
            # Check if Ollama is available first
            health_status = await self.check_ollama_health()
            if health_status['status'] != 'healthy':
                return {
                    'error': 'AI processing unavailable',
                    'message': 'Ollama is not running or accessible. Please ensure Ollama is installed and running on localhost:11434',
                    'status': 'unavailable',
                    'text_length': len(text)
                }
            
            model_name = 'llama3.1:70b-instruct-q4_K_M'
            
            prompt = f"""
            Extract entities from the following text and categorize them.
            
            Text: "{text}"
            
            Please respond with a JSON object containing:
            - people: list of person names
            - organizations: list of organization names
            - locations: list of location names
            - events: list of event names
            - topics: list of topic/subject names
            - dates: list of dates mentioned
            - numbers: list of important numbers/statistics
            
            Respond only with valid JSON.
            """
            
            result = await self._call_ollama(model_name, prompt)
            entities_data = self._parse_json_response(result)
            
            return {
                'people': entities_data.get('people', []),
                'organizations': entities_data.get('organizations', []),
                'locations': entities_data.get('locations', []),
                'events': entities_data.get('events', []),
                'topics': entities_data.get('topics', []),
                'dates': entities_data.get('dates', []),
                'numbers': entities_data.get('numbers', []),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {
                'error': 'AI processing failed',
                'message': f'Failed to extract entities: {str(e)}',
                'status': 'error',
                'text_length': len(text)
            }
    
    async def analyze_readability(self, text: str) -> Dict[str, Any]:
        """Analyze text readability and quality metrics"""
        try:
            # Check if Ollama is available first
            health_status = await self.check_ollama_health()
            if health_status['status'] != 'healthy':
                return {
                    'error': 'AI processing unavailable',
                    'message': 'Ollama is not running or accessible. Please ensure Ollama is installed and running on localhost:11434',
                    'status': 'unavailable',
                    'text_length': len(text)
                }
            
            model_name = 'llama3.1:70b-instruct-q4_K_M'
            
            prompt = f"""
            Analyze the readability and quality of the following text.
            
            Text: "{text}"
            
            Please respond with a JSON object containing:
            - readability_score: float between 0.0 and 1.0 (1.0 = very readable)
            - complexity_level: "simple", "moderate", or "complex"
            - writing_quality: "poor", "fair", "good", or "excellent"
            - sentence_structure: analysis of sentence structure
            - vocabulary_level: "basic", "intermediate", or "advanced"
            - clarity_score: float between 0.0 and 1.0
            - suggestions: list of improvement suggestions
            
            Respond only with valid JSON.
            """
            
            result = await self._call_ollama(model_name, prompt)
            readability_data = self._parse_json_response(result)
            
            return {
                'readability_score': float(readability_data.get('readability_score', 0.5)),
                'complexity_level': readability_data.get('complexity_level', 'moderate'),
                'writing_quality': readability_data.get('writing_quality', 'fair'),
                'sentence_structure': readability_data.get('sentence_structure', ''),
                'vocabulary_level': readability_data.get('vocabulary_level', 'intermediate'),
                'clarity_score': float(readability_data.get('clarity_score', 0.5)),
                'suggestions': readability_data.get('suggestions', []),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing readability: {e}")
            return {
                'error': 'AI processing failed',
                'message': f'Failed to analyze readability: {str(e)}',
                'status': 'error',
                'text_length': len(text)
            }
    
    def _select_model(self, analysis_type: str) -> str:
        """Select appropriate model based on analysis type"""
        if analysis_type in ['technical_analysis', 'code_analysis']:
            return 'deepseek-coder:33b'
        else:
            return 'llama3.1:70b-instruct-q4_K_M'
    
    def _prepare_article_context(self, articles: List[Dict[str, Any]]) -> str:
        """Prepare article context for AI analysis"""
        context_parts = []
        
        for i, article in enumerate(articles[:5]):  # Limit to 5 articles for context
            context_parts.append(f"""
Article {i+1}:
Title: {article.get('title', 'No title')}
Content: {article.get('content', 'No content')[:1000]}...
Source: {article.get('source', 'Unknown')}
Published: {article.get('published_at', 'Unknown')}
            """)
        
        return "\n".join(context_parts)
    
    def _create_analysis_prompt(self, story_id: str, context: str, analysis_type: str) -> str:
        """Create analysis prompt based on type"""
        base_prompt = f"""
        Analyze the following news story and provide a comprehensive analysis.
        
        Story ID: {story_id}
        
        Context:
        {context}
        
        """
        
        if analysis_type == 'comprehensive':
            return base_prompt + """
            Please provide a JSON response with:
            - summary: concise summary of the story
            - key_points: list of main points
            - sentiment: overall sentiment analysis
            - entities: important people, organizations, locations
            - timeline: chronological sequence of events
            - credibility: assessment of source credibility
            - bias: potential bias indicators
            - impact: potential impact assessment
            - recommendations: suggested follow-up actions
            
            Respond only with valid JSON.
            """
        elif analysis_type == 'sentiment':
            return base_prompt + """
            Focus on sentiment analysis. Provide JSON with:
            - overall_sentiment: positive/negative/neutral
            - confidence: 0.0-1.0
            - emotional_indicators: specific words/phrases
            - tone_analysis: formal/informal, objective/subjective
            - audience_impact: how different audiences might react
            
            Respond only with valid JSON.
            """
        else:
            return base_prompt + """
            Provide a general analysis in JSON format with:
            - summary: main points
            - key_findings: important discoveries
            - context: background information
            - implications: potential consequences
            
            Respond only with valid JSON.
            """
    
    def _create_journalistic_prompt(self, story_id: str, context: Dict[str, Any]) -> str:
        """Create journalistic report prompt"""
        timeline_text = "\n".join([
            f"- {event.get('timestamp', '')}: {event.get('title', '')} - {event.get('description', '')}"
            for event in context.get('timeline_events', [])
        ])
        
        articles_text = "\n".join([
            f"- {article.get('title', '')} ({article.get('source', '')})"
            for article in context.get('articles', [])[:10]
        ])
        
        return f"""
        Create a professional journalistic report for the following story.
        
        Story ID: {story_id}
        
        Timeline of Events:
        {timeline_text}
        
        Source Articles:
        {articles_text}
        
        Please create a comprehensive journalistic report in JSON format with:
        - headline: compelling news headline
        - lead_paragraph: engaging opening paragraph
        - body: detailed report body with multiple paragraphs
        - key_quotes: important quotes from sources
        - background: necessary background information
        - analysis: journalistic analysis and context
        - implications: potential consequences and next steps
        - sources: list of sources used
        - word_count: approximate word count
        - reading_time: estimated reading time in minutes
        - tone: professional, objective, engaging
        
        Write in a professional journalistic style suitable for publication.
        Respond only with valid JSON.
        """
    
    async def _call_ollama(self, model_name: str, prompt: str) -> str:
        """Call Ollama API with the specified model and prompt"""
        try:
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.available_models[model_name].get('temperature', 0.7),
                    "num_predict": self.available_models[model_name].get('max_tokens', 4096)
                }
            }
            
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=120  # 2 minute timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                raise Exception(f"Ollama API error {response.status_code}: {response.text}")
                        
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            raise
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from AI, handling common formatting issues"""
        try:
            # Try to extract JSON from response
            response = response.strip()
            
            # Look for JSON block markers
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                if end != -1:
                    response = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                if end != -1:
                    response = response[start:end].strip()
            
            # Try to find JSON object boundaries
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                response = response[start:end]
            
            # Clean up common JSON issues
            response = self._clean_json_string(response)
            
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            logger.error(f"Response was: {response[:500]}...")
            # Try to return a fallback structure
            return self._create_fallback_response(response)
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {}
    
    def _clean_json_string(self, json_str: str) -> str:
        """Clean JSON string by removing comments and fixing common issues"""
        import re
        
        # Remove single-line comments (// comment)
        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
        
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix common quote issues
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)  # Single quotes to double quotes for keys
        
        return json_str
    
    def _create_fallback_response(self, response: str) -> Dict[str, Any]:
        """Create a fallback response when JSON parsing fails"""
        return {
            "error": "JSON parsing failed",
            "raw_response": response[:200] + "..." if len(response) > 200 else response,
            "fallback": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _parse_analysis_response(self, response: str, analysis_type: str) -> Dict[str, Any]:
        """Parse analysis response based on type"""
        parsed = self._parse_json_response(response)
        
        # Add metadata
        parsed['analysis_type'] = analysis_type
        parsed['generated_at'] = datetime.now(timezone.utc).isoformat()
        parsed['model_used'] = self._select_model(analysis_type)
        
        return parsed
    
    def _parse_journalistic_report(self, response: str) -> Dict[str, Any]:
        """Parse journalistic report response"""
        parsed = self._parse_json_response(response)
        
        # Add metadata
        parsed['generated_at'] = datetime.now(timezone.utc).isoformat()
        parsed['model_used'] = 'llama3.1:70b-instruct-q4_K_M'
        parsed['report_type'] = 'journalistic'
        
        return parsed
    
    async def _store_analysis_result(self, story_id: str, analysis_type: str, analysis_data: Dict[str, Any]) -> None:
        """Store analysis result in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get story timeline ID
            cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
            timeline_row = cursor.fetchone()
            
            if timeline_row:
                timeline_id = timeline_row[0]
                
                cursor.execute("""
                    INSERT INTO ai_analysis 
                    (story_timeline_id, analysis_type, analysis_data, confidence, model_used, processing_time_ms)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    timeline_id,
                    analysis_type,
                    json.dumps(analysis_data),
                    analysis_data.get('confidence', 0.5),
                    analysis_data.get('model_used', 'unknown'),
                    analysis_data.get('processing_time_ms', 0)
                ))
                
                conn.commit()
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing analysis result: {e}")
    
    async def _store_consolidated_report(self, story_id: str, report_data: Dict[str, Any]) -> None:
        """Store consolidated report in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get story timeline ID
            cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
            timeline_row = cursor.fetchone()
            
            if timeline_row:
                timeline_id = timeline_row[0]
                
                cursor.execute("""
                    INSERT INTO story_consolidations 
                    (story_timeline_id, headline, consolidated_summary, key_points, 
                     professional_report, executive_summary, recommendations, ai_analysis, sources)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    timeline_id,
                    report_data.get('headline', ''),
                    report_data.get('body', ''),
                    json.dumps(report_data.get('key_points', [])),
                    report_data.get('body', ''),
                    report_data.get('lead_paragraph', ''),
                    json.dumps(report_data.get('implications', [])),
                    json.dumps(report_data),
                    json.dumps(report_data.get('sources', []))
                ))
                
                conn.commit()
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing consolidated report: {e}")

# Global instance
ai_service = None

def get_ai_service() -> AIProcessingService:
    """Get AI processing service instance"""
    global ai_service
    if ai_service is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        ai_service = AIProcessingService(db_config)
    return ai_service
