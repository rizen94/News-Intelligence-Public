"""
Iterative RAG Service for V2.9
Implements sequential, self-improving RAG processing that builds comprehensive dossiers
over multiple iterations until reaching a plateau of new information.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import json
import hashlib

from .rag_enhanced_service import RAGEnhancedService
from .gdelt_rag_service import GDELTRAGService
from .simple_rag_service import SimpleRAGService

logger = logging.getLogger(__name__)

@dataclass
class RAGIteration:
    """Represents a single RAG iteration with its results and metadata"""
    iteration_number: int
    timestamp: str
    phase: str  # 'timeline', 'context', 'analysis', 'synthesis'
    input_tags: List[str]
    output_tags: List[str]
    new_articles_found: int
    new_entities_found: int
    new_insights: List[str]
    processing_time: float
    plateau_score: float  # 0-1, higher means more new information
    success: bool
    error_message: Optional[str] = None

@dataclass
class RAGDossier:
    """Complete dossier built through iterative RAG processing"""
    dossier_id: str
    article_id: int
    created_at: str
    last_updated: str
    total_iterations: int
    current_phase: str
    is_complete: bool
    plateau_reached: bool
    iterations: List[RAGIteration]
    final_timeline: List[Dict]
    final_context: Dict
    final_analysis: Dict
    final_synthesis: Dict
    total_articles_analyzed: int
    total_entities_found: int
    historical_depth_years: int

class IterativeRAGService:
    """
    Iterative RAG Service that builds comprehensive dossiers through sequential processing
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.rag_enhanced = RAGEnhancedService(db_connection)
        self.gdelt_service = GDELTRAGService()
        self.simple_rag = SimpleRAGService(db_connection)
        
        # Configuration
        self.max_iterations = 10
        self.plateau_threshold = 0.1  # Stop when new info < 10%
        self.max_historical_years = 50
        self.min_iteration_gap_seconds = 30
        
        # Phase sequence
        self.phases = ['timeline', 'context', 'analysis', 'synthesis']
        
    def create_dossier(self, article_id: int, initial_keywords: List[str] = None) -> RAGDossier:
        """Create a new iterative RAG dossier for an article"""
        try:
            # Get article details
            article = self._get_article(article_id)
            if not article:
                raise ValueError(f"Article {article_id} not found")
            
            # Generate dossier ID
            dossier_id = self._generate_dossier_id(article_id, article.get('title', ''))
            
            # Create initial dossier
            dossier = RAGDossier(
                dossier_id=dossier_id,
                article_id=article_id,
                created_at=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
                total_iterations=0,
                current_phase='timeline',
                is_complete=False,
                plateau_reached=False,
                iterations=[],
                final_timeline=[],
                final_context={},
                final_analysis={},
                final_synthesis={},
                total_articles_analyzed=0,
                total_entities_found=0,
                historical_depth_years=0
            )
            
            # Save to database
            self._save_dossier(dossier)
            
            logger.info(f"Created iterative RAG dossier {dossier_id} for article {article_id}")
            return dossier
            
        except Exception as e:
            logger.error(f"Error creating dossier for article {article_id}: {e}")
            raise
    
    def process_iteration(self, dossier_id: str, force_continue: bool = False) -> RAGIteration:
        """Process the next iteration in the dossier sequence"""
        try:
            # Load dossier
            dossier = self._load_dossier(dossier_id)
            if not dossier:
                raise ValueError(f"Dossier {dossier_id} not found")
            
            # Check if already complete
            if dossier.is_complete and not force_continue:
                raise ValueError(f"Dossier {dossier_id} is already complete")
            
            # Determine current phase and iteration number
            iteration_number = dossier.total_iterations + 1
            current_phase = self._determine_next_phase(dossier)
            
            # Check iteration timing
            if not self._can_process_iteration(dossier):
                raise ValueError(f"Too soon for next iteration. Wait {self.min_iteration_gap_seconds} seconds")
            
            # Get input tags for this iteration
            input_tags = self._get_input_tags(dossier, current_phase)
            
            # Process the iteration
            start_time = time.time()
            iteration_result = self._process_phase(
                dossier, current_phase, input_tags, iteration_number
            )
            processing_time = time.time() - start_time
            
            # Create iteration record
            iteration = RAGIteration(
                iteration_number=iteration_number,
                timestamp=datetime.now().isoformat(),
                phase=current_phase,
                input_tags=input_tags,
                output_tags=iteration_result.get('output_tags', []),
                new_articles_found=iteration_result.get('new_articles', 0),
                new_entities_found=iteration_result.get('new_entities', 0),
                new_insights=iteration_result.get('insights', []),
                processing_time=processing_time,
                plateau_score=iteration_result.get('plateau_score', 0.0),
                success=iteration_result.get('success', False),
                error_message=iteration_result.get('error')
            )
            
            # Update dossier
            dossier.iterations.append(iteration)
            dossier.total_iterations = iteration_number
            dossier.last_updated = datetime.now().isoformat()
            dossier.current_phase = current_phase
            
            # Update dossier data based on phase
            self._update_dossier_data(dossier, current_phase, iteration_result)
            
            # Check for plateau
            dossier.plateau_reached = self._check_plateau(dossier)
            dossier.is_complete = self._check_completion(dossier)
            
            # Save updated dossier
            self._save_dossier(dossier)
            
            logger.info(f"Completed iteration {iteration_number} for dossier {dossier_id}")
            return iteration
            
        except Exception as e:
            logger.error(f"Error processing iteration for dossier {dossier_id}: {e}")
            raise
    
    def _process_phase(self, dossier: RAGDossier, phase: str, input_tags: List[str], iteration: int) -> Dict:
        """Process a specific phase of the RAG iteration"""
        try:
            if phase == 'timeline':
                return self._process_timeline_phase(dossier, input_tags, iteration)
            elif phase == 'context':
                return self._process_context_phase(dossier, input_tags, iteration)
            elif phase == 'analysis':
                return self._process_analysis_phase(dossier, input_tags, iteration)
            elif phase == 'synthesis':
                return self._process_synthesis_phase(dossier, input_tags, iteration)
            else:
                raise ValueError(f"Unknown phase: {phase}")
                
        except Exception as e:
            logger.error(f"Error processing phase {phase}: {e}")
            return {
                'success': False,
                'error': str(e),
                'output_tags': [],
                'new_articles': 0,
                'new_entities': 0,
                'insights': [],
                'plateau_score': 0.0
            }
    
    def _process_timeline_phase(self, dossier: RAGDossier, input_tags: List[str], iteration: int) -> Dict:
        """Process timeline expansion phase"""
        try:
            # Expand timeline backwards up to 50 years
            years_back = min(50, 5 * iteration)  # Progressive expansion
            
            # Use GDELT for historical timeline
            timeline_result = self.gdelt_service.get_event_timeline(
                query=' '.join(input_tags),
                days_back=years_back * 365
            )
            
            # Extract new entities and events
            new_entities = self._extract_entities_from_timeline(timeline_result)
            new_articles = len(timeline_result.get('events', []))
            
            # Generate output tags for next iteration
            output_tags = self._generate_timeline_tags(timeline_result, input_tags)
            
            # Calculate plateau score
            plateau_score = self._calculate_timeline_plateau_score(dossier, timeline_result)
            
            return {
                'success': True,
                'timeline_data': timeline_result,
                'output_tags': output_tags,
                'new_articles': new_articles,
                'new_entities': len(new_entities),
                'insights': self._extract_timeline_insights(timeline_result),
                'plateau_score': plateau_score
            }
            
        except Exception as e:
            logger.error(f"Error in timeline phase: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_context_phase(self, dossier: RAGDossier, input_tags: List[str], iteration: int) -> Dict:
        """Process context building phase"""
        try:
            # Use simple RAG for context building
            context_result = self.simple_rag.enhance_article_with_context(
                article_id=dossier.article_id,
                keywords=input_tags,
                max_articles=50 + (iteration * 10)  # Progressive expansion
            )
            
            # Extract new context
            new_articles = len(context_result.get('related_articles', []))
            new_entities = len(context_result.get('entity_analysis', {}))
            
            # Generate output tags
            output_tags = self._generate_context_tags(context_result, input_tags)
            
            # Calculate plateau score
            plateau_score = self._calculate_context_plateau_score(dossier, context_result)
            
            return {
                'success': True,
                'context_data': context_result,
                'output_tags': output_tags,
                'new_articles': new_articles,
                'new_entities': new_entities,
                'insights': self._extract_context_insights(context_result),
                'plateau_score': plateau_score
            }
            
        except Exception as e:
            logger.error(f"Error in context phase: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_analysis_phase(self, dossier: RAGDossier, input_tags: List[str], iteration: int) -> Dict:
        """Process analysis phase"""
        try:
            # Use enhanced RAG for deep analysis
            analysis_result = self.rag_enhanced.enhance_article_with_gdelt_timeline(
                article_id=dossier.article_id,
                keywords=input_tags
            )
            
            # Extract analysis insights
            new_articles = len(analysis_result.get('related_articles', []))
            new_entities = len(analysis_result.get('entity_analysis', {}))
            
            # Generate output tags
            output_tags = self._generate_analysis_tags(analysis_result, input_tags)
            
            # Calculate plateau score
            plateau_score = self._calculate_analysis_plateau_score(dossier, analysis_result)
            
            return {
                'success': True,
                'analysis_data': analysis_result,
                'output_tags': output_tags,
                'new_articles': new_articles,
                'new_entities': new_entities,
                'insights': self._extract_analysis_insights(analysis_result),
                'plateau_score': plateau_score
            }
            
        except Exception as e:
            logger.error(f"Error in analysis phase: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_synthesis_phase(self, dossier: RAGDossier, input_tags: List[str], iteration: int) -> Dict:
        """Process synthesis phase - combine all previous insights"""
        try:
            # Synthesize all previous iterations
            synthesis_result = self._synthesize_dossier_data(dossier)
            
            # Generate final output tags
            output_tags = self._generate_synthesis_tags(synthesis_result, input_tags)
            
            # Calculate plateau score
            plateau_score = self._calculate_synthesis_plateau_score(dossier, synthesis_result)
            
            return {
                'success': True,
                'synthesis_data': synthesis_result,
                'output_tags': output_tags,
                'new_articles': 0,  # Synthesis doesn't find new articles
                'new_entities': 0,
                'insights': self._extract_synthesis_insights(synthesis_result),
                'plateau_score': plateau_score
            }
            
        except Exception as e:
            logger.error(f"Error in synthesis phase: {e}")
            return {'success': False, 'error': str(e)}
    
    def _check_plateau(self, dossier: RAGDossier) -> bool:
        """Check if the dossier has reached a plateau of new information"""
        if len(dossier.iterations) < 3:
            return False
        
        # Get recent plateau scores
        recent_scores = [iter.plateau_score for iter in dossier.iterations[-3:]]
        avg_recent_score = sum(recent_scores) / len(recent_scores)
        
        # Check if below threshold
        if avg_recent_score < self.plateau_threshold:
            logger.info(f"Dossier {dossier.dossier_id} reached plateau (score: {avg_recent_score})")
            return True
        
        return False
    
    def _check_completion(self, dossier: RAGDossier) -> bool:
        """Check if dossier is complete"""
        # Complete if plateau reached or max iterations exceeded
        if dossier.plateau_reached:
            return True
        
        if dossier.total_iterations >= self.max_iterations:
            return True
        
        # Complete if all phases have been processed at least once
        phases_completed = set(iter.phase for iter in dossier.iterations)
        if len(phases_completed) >= len(self.phases):
            return True
        
        return False
    
    def get_dossier_status(self, dossier_id: str) -> Dict:
        """Get current status of a dossier"""
        try:
            dossier = self._load_dossier(dossier_id)
            if not dossier:
                return {'error': f'Dossier {dossier_id} not found'}
            
            return {
                'dossier_id': dossier.dossier_id,
                'article_id': dossier.article_id,
                'status': 'complete' if dossier.is_complete else 'processing',
                'current_phase': dossier.current_phase,
                'total_iterations': dossier.total_iterations,
                'plateau_reached': dossier.plateau_reached,
                'last_updated': dossier.last_updated,
                'progress': {
                    'phases_completed': len(set(iter.phase for iter in dossier.iterations)),
                    'total_phases': len(self.phases),
                    'articles_analyzed': dossier.total_articles_analyzed,
                    'entities_found': dossier.total_entities_found,
                    'historical_depth_years': dossier.historical_depth_years
                },
                'recent_iterations': [
                    {
                        'iteration': iter.iteration_number,
                        'phase': iter.phase,
                        'timestamp': iter.timestamp,
                        'plateau_score': iter.plateau_score,
                        'new_articles': iter.new_articles_found,
                        'new_entities': iter.new_entities_found
                    }
                    for iter in dossier.iterations[-5:]  # Last 5 iterations
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting dossier status: {e}")
            return {'error': str(e)}
    
    def get_complete_dossier(self, dossier_id: str) -> Dict:
        """Get the complete dossier with all data"""
        try:
            dossier = self._load_dossier(dossier_id)
            if not dossier:
                return {'error': f'Dossier {dossier_id} not found'}
            
            return asdict(dossier)
            
        except Exception as e:
            logger.error(f"Error getting complete dossier: {e}")
            return {'error': str(e)}
    
    # Helper methods
    def _generate_dossier_id(self, article_id: int, title: str) -> str:
        """Generate unique dossier ID"""
        content = f"{article_id}_{title}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _get_article(self, article_id: int) -> Optional[Dict]:
        """Get article from database"""
        try:
            cursor = self.db.cursor()
            cursor.execute("SELECT * FROM articles WHERE id = %s", (article_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting article {article_id}: {e}")
            return None
    
    def _save_dossier(self, dossier: RAGDossier):
        """Save dossier to database"""
        try:
            cursor = self.db.cursor()
            
            # Save dossier metadata
            cursor.execute("""
                INSERT INTO rag_dossiers (
                    dossier_id, article_id, created_at, last_updated,
                    total_iterations, current_phase, is_complete, plateau_reached,
                    total_articles_analyzed, total_entities_found, historical_depth_years,
                    final_timeline, final_context, final_analysis, final_synthesis
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dossier_id) DO UPDATE SET
                    last_updated = EXCLUDED.last_updated,
                    total_iterations = EXCLUDED.total_iterations,
                    current_phase = EXCLUDED.current_phase,
                    is_complete = EXCLUDED.is_complete,
                    plateau_reached = EXCLUDED.plateau_reached,
                    total_articles_analyzed = EXCLUDED.total_articles_analyzed,
                    total_entities_found = EXCLUDED.total_entities_found,
                    historical_depth_years = EXCLUDED.historical_depth_years,
                    final_timeline = EXCLUDED.final_timeline,
                    final_context = EXCLUDED.final_context,
                    final_analysis = EXCLUDED.final_analysis,
                    final_synthesis = EXCLUDED.final_synthesis
            """, (
                dossier.dossier_id, dossier.article_id, dossier.created_at, dossier.last_updated,
                dossier.total_iterations, dossier.current_phase, dossier.is_complete, dossier.plateau_reached,
                dossier.total_articles_analyzed, dossier.total_entities_found, dossier.historical_depth_years,
                json.dumps(dossier.final_timeline), json.dumps(dossier.final_context),
                json.dumps(dossier.final_analysis), json.dumps(dossier.final_synthesis)
            ))
            
            # Save iterations
            for iteration in dossier.iterations:
                cursor.execute("""
                    INSERT INTO rag_iterations (
                        dossier_id, iteration_number, timestamp, phase,
                        input_tags, output_tags, new_articles_found, new_entities_found,
                        new_insights, processing_time, plateau_score, success, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (dossier_id, iteration_number) DO UPDATE SET
                        timestamp = EXCLUDED.timestamp,
                        phase = EXCLUDED.phase,
                        input_tags = EXCLUDED.input_tags,
                        output_tags = EXCLUDED.output_tags,
                        new_articles_found = EXCLUDED.new_articles_found,
                        new_entities_found = EXCLUDED.new_entities_found,
                        new_insights = EXCLUDED.new_insights,
                        processing_time = EXCLUDED.processing_time,
                        plateau_score = EXCLUDED.plateau_score,
                        success = EXCLUDED.success,
                        error_message = EXCLUDED.error_message
                """, (
                    dossier.dossier_id, iteration.iteration_number, iteration.timestamp, iteration.phase,
                    json.dumps(iteration.input_tags), json.dumps(iteration.output_tags),
                    iteration.new_articles_found, iteration.new_entities_found,
                    json.dumps(iteration.new_insights), iteration.processing_time,
                    iteration.plateau_score, iteration.success, iteration.error_message
                ))
            
            self.db.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Error saving dossier: {e}")
            self.db.rollback()
            raise
    
    def _load_dossier(self, dossier_id: str) -> Optional[RAGDossier]:
        """Load dossier from database"""
        try:
            cursor = self.db.cursor()
            
            # Load dossier metadata
            cursor.execute("SELECT * FROM rag_dossiers WHERE dossier_id = %s", (dossier_id,))
            dossier_row = cursor.fetchone()
            
            if not dossier_row:
                cursor.close()
                return None
            
            # Load iterations
            cursor.execute("""
                SELECT * FROM rag_iterations 
                WHERE dossier_id = %s 
                ORDER BY iteration_number
            """, (dossier_id,))
            iteration_rows = cursor.fetchall()
            
            cursor.close()
            
            # Convert to RAGDossier object
            iterations = []
            for row in iteration_rows:
                iteration = RAGIteration(
                    iteration_number=row['iteration_number'],
                    timestamp=row['timestamp'],
                    phase=row['phase'],
                    input_tags=json.loads(row['input_tags']),
                    output_tags=json.loads(row['output_tags']),
                    new_articles_found=row['new_articles_found'],
                    new_entities_found=row['new_entities_found'],
                    new_insights=json.loads(row['new_insights']),
                    processing_time=row['processing_time'],
                    plateau_score=row['plateau_score'],
                    success=row['success'],
                    error_message=row['error_message']
                )
                iterations.append(iteration)
            
            dossier = RAGDossier(
                dossier_id=dossier_row['dossier_id'],
                article_id=dossier_row['article_id'],
                created_at=dossier_row['created_at'],
                last_updated=dossier_row['last_updated'],
                total_iterations=dossier_row['total_iterations'],
                current_phase=dossier_row['current_phase'],
                is_complete=dossier_row['is_complete'],
                plateau_reached=dossier_row['plateau_reached'],
                iterations=iterations,
                final_timeline=json.loads(dossier_row['final_timeline']),
                final_context=json.loads(dossier_row['final_context']),
                final_analysis=json.loads(dossier_row['final_analysis']),
                final_synthesis=json.loads(dossier_row['final_synthesis']),
                total_articles_analyzed=dossier_row['total_articles_analyzed'],
                total_entities_found=dossier_row['total_entities_found'],
                historical_depth_years=dossier_row['historical_depth_years']
            )
            
            return dossier
            
        except Exception as e:
            logger.error(f"Error loading dossier: {e}")
            return None
    
    # Additional helper methods would be implemented here...
    def _determine_next_phase(self, dossier: RAGDossier) -> str:
        """Determine the next phase to process"""
        if not dossier.iterations:
            return 'timeline'
        
        # Cycle through phases
        last_phase = dossier.iterations[-1].phase
        current_index = self.phases.index(last_phase)
        next_index = (current_index + 1) % len(self.phases)
        return self.phases[next_index]
    
    def _get_input_tags(self, dossier: RAGDossier, phase: str) -> List[str]:
        """Get input tags for the current phase"""
        if not dossier.iterations:
            # First iteration - use article title and basic keywords
            article = self._get_article(dossier.article_id)
            if article:
                title_words = article.get('title', '').split()[:5]
                return title_words
            return ['news', 'analysis']
        
        # Use output tags from previous iteration
        last_iteration = dossier.iterations[-1]
        return last_iteration.output_tags[:10]  # Limit to 10 tags
    
    def _can_process_iteration(self, dossier: RAGDossier) -> bool:
        """Check if enough time has passed for next iteration"""
        if not dossier.iterations:
            return True
        
        last_iteration_time = datetime.fromisoformat(dossier.iterations[-1].timestamp)
        time_since_last = datetime.now() - last_iteration_time
        return time_since_last.total_seconds() >= self.min_iteration_gap_seconds
    
    def _update_dossier_data(self, dossier: RAGDossier, phase: str, result: Dict):
        """Update dossier data based on phase results"""
        if phase == 'timeline':
            dossier.final_timeline = result.get('timeline_data', {})
            dossier.historical_depth_years = min(50, dossier.historical_depth_years + 5)
        elif phase == 'context':
            dossier.final_context = result.get('context_data', {})
        elif phase == 'analysis':
            dossier.final_analysis = result.get('analysis_data', {})
        elif phase == 'synthesis':
            dossier.final_synthesis = result.get('synthesis_data', {})
        
        # Update totals
        dossier.total_articles_analyzed += result.get('new_articles', 0)
        dossier.total_entities_found += result.get('new_entities', 0)
    
    # Placeholder methods for tag generation and plateau calculation
    def _generate_timeline_tags(self, timeline_result: Dict, input_tags: List[str]) -> List[str]:
        """Generate tags from timeline results"""
        # Implementation would extract key entities, dates, and themes
        return input_tags + ['timeline', 'historical']
    
    def _generate_context_tags(self, context_result: Dict, input_tags: List[str]) -> List[str]:
        """Generate tags from context results"""
        return input_tags + ['context', 'related']
    
    def _generate_analysis_tags(self, analysis_result: Dict, input_tags: List[str]) -> List[str]:
        """Generate tags from analysis results"""
        return input_tags + ['analysis', 'deep']
    
    def _generate_synthesis_tags(self, synthesis_result: Dict, input_tags: List[str]) -> List[str]:
        """Generate tags from synthesis results"""
        return input_tags + ['synthesis', 'complete']
    
    def _calculate_timeline_plateau_score(self, dossier: RAGDossier, timeline_result: Dict) -> float:
        """Calculate plateau score for timeline phase"""
        # Implementation would compare with previous timeline results
        return 0.5  # Placeholder
    
    def _calculate_context_plateau_score(self, dossier: RAGDossier, context_result: Dict) -> float:
        """Calculate plateau score for context phase"""
        return 0.5  # Placeholder
    
    def _calculate_analysis_plateau_score(self, dossier: RAGDossier, analysis_result: Dict) -> float:
        """Calculate plateau score for analysis phase"""
        return 0.5  # Placeholder
    
    def _calculate_synthesis_plateau_score(self, dossier: RAGDossier, synthesis_result: Dict) -> float:
        """Calculate plateau score for synthesis phase"""
        return 0.5  # Placeholder
    
    def _extract_entities_from_timeline(self, timeline_result: Dict) -> List[str]:
        """Extract entities from timeline results"""
        return []  # Placeholder
    
    def _extract_timeline_insights(self, timeline_result: Dict) -> List[str]:
        """Extract insights from timeline results"""
        return []  # Placeholder
    
    def _extract_context_insights(self, context_result: Dict) -> List[str]:
        """Extract insights from context results"""
        return []  # Placeholder
    
    def _extract_analysis_insights(self, analysis_result: Dict) -> List[str]:
        """Extract insights from analysis results"""
        return []  # Placeholder
    
    def _extract_synthesis_insights(self, synthesis_result: Dict) -> List[str]:
        """Extract insights from synthesis results"""
        return []  # Placeholder
    
    def _synthesize_dossier_data(self, dossier: RAGDossier) -> Dict:
        """Synthesize all dossier data into final result"""
        return {
            'timeline': dossier.final_timeline,
            'context': dossier.final_context,
            'analysis': dossier.final_analysis,
            'total_iterations': dossier.total_iterations,
            'articles_analyzed': dossier.total_articles_analyzed,
            'entities_found': dossier.total_entities_found
        }
