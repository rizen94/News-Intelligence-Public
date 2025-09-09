"""
Predictive Scaling Service for News Intelligence System v3.0
Machine learning-based load prediction and proactive scaling
"""

import asyncio
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor
import json

logger = logging.getLogger(__name__)

@dataclass
class LoadPrediction:
    """Load prediction result"""
    predicted_cpu: float
    predicted_memory: float
    predicted_queue_length: int
    confidence: float
    prediction_horizon: int  # minutes ahead
    recommended_parallel_tasks: int
    scaling_action: str  # 'scale_up', 'scale_down', 'maintain'
    urgency: str  # 'low', 'medium', 'high', 'critical'

@dataclass
class HistoricalDataPoint:
    """Historical data point for training"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    queue_length: int
    parallel_tasks: int
    articles_processed: int
    processing_time: float
    error_rate: float

class PredictiveScalingService:
    """Predictive scaling service with ML-based load prediction"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.model_weights = None
        self.feature_scaler = None
        self.prediction_history = []
        self.model_accuracy = 0.0
        self.last_training_time = None
        
        # Model parameters
        self.feature_window = 60  # minutes of historical data
        self.prediction_horizon = 15  # minutes ahead
        self.min_training_samples = 100
        self.retrain_interval_hours = 24
        
        # Scaling thresholds
        self.scaling_thresholds = {
            'cpu_high': 80.0,
            'cpu_low': 30.0,
            'memory_high': 85.0,
            'memory_low': 40.0,
            'queue_high': 50,
            'queue_low': 10
        }
    
    async def predict_load(self, current_metrics: Dict[str, Any]) -> LoadPrediction:
        """Predict future load based on current metrics and historical data"""
        try:
            # Get historical data
            historical_data = await self._get_historical_data()
            
            if len(historical_data) < self.min_training_samples:
                # Not enough data for prediction, use simple heuristics
                return self._simple_load_prediction(current_metrics)
            
            # Train/retrain model if needed
            if self._should_retrain():
                await self._train_model(historical_data)
            
            # Extract features
            features = self._extract_features(current_metrics, historical_data)
            
            # Make prediction
            prediction = await self._make_prediction(features, current_metrics)
            
            # Store prediction for accuracy tracking
            self.prediction_history.append({
                'timestamp': datetime.now(timezone.utc),
                'prediction': prediction,
                'actual_metrics': current_metrics
            })
            
            # Keep only recent predictions
            if len(self.prediction_history) > 1000:
                self.prediction_history = self.prediction_history[-500:]
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error in load prediction: {e}")
            return self._simple_load_prediction(current_metrics)
    
    async def _get_historical_data(self) -> List[HistoricalDataPoint]:
        """Get historical system metrics for training"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get historical data from monitoring tables
            cursor.execute("""
                SELECT 
                    created_at as timestamp,
                    cpu_percent,
                    memory_percent,
                    queue_length,
                    parallel_tasks,
                    articles_processed,
                    processing_time,
                    error_rate
                FROM system_metrics 
                WHERE created_at > NOW() - INTERVAL '%s minutes'
                ORDER BY created_at
            """, (self.feature_window,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            historical_data = []
            for row in results:
                historical_data.append(HistoricalDataPoint(
                    timestamp=row['timestamp'],
                    cpu_percent=float(row['cpu_percent']),
                    memory_percent=float(row['memory_percent']),
                    queue_length=int(row['queue_length']),
                    parallel_tasks=int(row['parallel_tasks']),
                    articles_processed=int(row['articles_processed']),
                    processing_time=float(row['processing_time']),
                    error_rate=float(row['error_rate'])
                ))
            
            return historical_data
            
        except Exception as e:
            logger.warning(f"Error getting historical data: {e}")
            return []
    
    def _should_retrain(self) -> bool:
        """Check if model should be retrained"""
        if self.last_training_time is None:
            return True
        
        time_since_training = (datetime.now(timezone.utc) - self.last_training_time).total_seconds() / 3600
        return time_since_training >= self.retrain_interval_hours
    
    async def _train_model(self, historical_data: List[HistoricalDataPoint]):
        """Train the predictive model using historical data"""
        try:
            if len(historical_data) < self.min_training_samples:
                logger.warning("Not enough historical data for training")
                return
            
            # Prepare training data
            X, y = self._prepare_training_data(historical_data)
            
            # Simple linear regression model (in production, use scikit-learn)
            self.model_weights = self._train_linear_regression(X, y)
            
            # Calculate model accuracy
            self.model_accuracy = self._calculate_model_accuracy(X, y)
            
            self.last_training_time = datetime.now(timezone.utc)
            logger.info(f"Model trained with {len(historical_data)} samples, accuracy: {self.model_accuracy:.3f}")
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
    
    def _prepare_training_data(self, historical_data: List[HistoricalDataPoint]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data for the model"""
        # Extract features and targets
        features = []
        targets = []
        
        for i in range(len(historical_data) - self.prediction_horizon):
            # Current features
            current = historical_data[i]
            feature_vector = [
                current.cpu_percent,
                current.memory_percent,
                current.queue_length,
                current.parallel_tasks,
                current.articles_processed,
                current.processing_time,
                current.error_rate
            ]
            
            # Add trend features (difference from previous point)
            if i > 0:
                prev = historical_data[i - 1]
                feature_vector.extend([
                    current.cpu_percent - prev.cpu_percent,
                    current.memory_percent - prev.memory_percent,
                    current.queue_length - prev.queue_length,
                    current.articles_processed - prev.articles_processed
                ])
            else:
                feature_vector.extend([0, 0, 0, 0])
            
            # Add time-based features
            hour = current.timestamp.hour
            day_of_week = current.timestamp.weekday()
            feature_vector.extend([
                np.sin(2 * np.pi * hour / 24),  # Hour of day (cyclical)
                np.cos(2 * np.pi * hour / 24),
                np.sin(2 * np.pi * day_of_week / 7),  # Day of week (cyclical)
                np.cos(2 * np.pi * day_of_week / 7)
            ])
            
            features.append(feature_vector)
            
            # Target: future CPU and memory (15 minutes ahead)
            future = historical_data[i + self.prediction_horizon]
            targets.append([future.cpu_percent, future.memory_percent, future.queue_length])
        
        return np.array(features), np.array(targets)
    
    def _train_linear_regression(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Train a simple linear regression model"""
        # Add bias term
        X_with_bias = np.column_stack([np.ones(X.shape[0]), X])
        
        # Normal equation: weights = (X^T * X)^-1 * X^T * y
        try:
            weights = np.linalg.solve(X_with_bias.T @ X_with_bias, X_with_bias.T @ y)
            return weights
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse if matrix is singular
            weights = np.linalg.pinv(X_with_bias) @ y
            return weights
    
    def _calculate_model_accuracy(self, X: np.ndarray, y: np.ndarray) -> float:
        """Calculate model accuracy using R-squared"""
        if self.model_weights is None:
            return 0.0
        
        X_with_bias = np.column_stack([np.ones(X.shape[0]), X])
        y_pred = X_with_bias @ self.model_weights
        
        # Calculate R-squared
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y, axis=0)) ** 2)
        
        if ss_tot == 0:
            return 0.0
        
        r_squared = 1 - (ss_res / ss_tot)
        return np.mean(r_squared)
    
    def _extract_features(self, current_metrics: Dict[str, Any], historical_data: List[HistoricalDataPoint]) -> np.ndarray:
        """Extract features for prediction"""
        # Current metrics
        feature_vector = [
            current_metrics.get('cpu_percent', 0.0),
            current_metrics.get('memory_percent', 0.0),
            current_metrics.get('queue_length', 0),
            current_metrics.get('parallel_tasks', 1),
            current_metrics.get('articles_processed', 0),
            current_metrics.get('processing_time', 0.0),
            current_metrics.get('error_rate', 0.0)
        ]
        
        # Trend features (if we have historical data)
        if len(historical_data) >= 2:
            current = historical_data[-1]
            prev = historical_data[-2]
            feature_vector.extend([
                current.cpu_percent - prev.cpu_percent,
                current.memory_percent - prev.memory_percent,
                current.queue_length - prev.queue_length,
                current.articles_processed - prev.articles_processed
            ])
        else:
            feature_vector.extend([0, 0, 0, 0])
        
        # Time-based features
        now = datetime.now(timezone.utc)
        hour = now.hour
        day_of_week = now.weekday()
        feature_vector.extend([
            np.sin(2 * np.pi * hour / 24),
            np.cos(2 * np.pi * hour / 24),
            np.sin(2 * np.pi * day_of_week / 7),
            np.cos(2 * np.pi * day_of_week / 7)
        ])
        
        return np.array(feature_vector)
    
    async def _make_prediction(self, features: np.ndarray, current_metrics: Dict[str, Any]) -> LoadPrediction:
        """Make load prediction using trained model"""
        try:
            if self.model_weights is None:
                return self._simple_load_prediction(current_metrics)
            
            # Add bias term
            features_with_bias = np.concatenate([[1], features])
            
            # Make prediction
            prediction = features_with_bias @ self.model_weights
            
            predicted_cpu = max(0, min(100, prediction[0]))
            predicted_memory = max(0, min(100, prediction[1]))
            predicted_queue_length = max(0, int(prediction[2]))
            
            # Calculate confidence based on model accuracy and data recency
            confidence = self.model_accuracy * 0.8  # Base confidence from model accuracy
            
            # Determine recommended scaling action
            recommended_parallel_tasks, scaling_action, urgency = self._determine_scaling_action(
                predicted_cpu, predicted_memory, predicted_queue_length, current_metrics
            )
            
            return LoadPrediction(
                predicted_cpu=predicted_cpu,
                predicted_memory=predicted_memory,
                predicted_queue_length=predicted_queue_length,
                confidence=confidence,
                prediction_horizon=self.prediction_horizon,
                recommended_parallel_tasks=recommended_parallel_tasks,
                scaling_action=scaling_action,
                urgency=urgency
            )
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return self._simple_load_prediction(current_metrics)
    
    def _simple_load_prediction(self, current_metrics: Dict[str, Any]) -> LoadPrediction:
        """Simple heuristic-based load prediction when ML model is not available"""
        cpu = current_metrics.get('cpu_percent', 50.0)
        memory = current_metrics.get('memory_percent', 50.0)
        queue_length = current_metrics.get('queue_length', 0)
        
        # Simple trend-based prediction
        predicted_cpu = min(100, cpu * 1.1)  # Assume 10% increase
        predicted_memory = min(100, memory * 1.05)  # Assume 5% increase
        predicted_queue_length = max(0, int(queue_length * 1.2))  # Assume 20% increase
        
        recommended_parallel_tasks, scaling_action, urgency = self._determine_scaling_action(
            predicted_cpu, predicted_memory, predicted_queue_length, current_metrics
        )
        
        return LoadPrediction(
            predicted_cpu=predicted_cpu,
            predicted_memory=predicted_memory,
            predicted_queue_length=predicted_queue_length,
            confidence=0.5,  # Lower confidence for heuristic prediction
            prediction_horizon=self.prediction_horizon,
            recommended_parallel_tasks=recommended_parallel_tasks,
            scaling_action=scaling_action,
            urgency=urgency
        )
    
    def _determine_scaling_action(self, predicted_cpu: float, predicted_memory: float, 
                                 predicted_queue_length: int, current_metrics: Dict[str, Any]) -> Tuple[int, str, str]:
        """Determine recommended scaling action based on predictions"""
        current_parallel_tasks = current_metrics.get('parallel_tasks', 5)
        
        # Determine urgency
        urgency = 'low'
        if predicted_cpu > 90 or predicted_memory > 95 or predicted_queue_length > 100:
            urgency = 'critical'
        elif predicted_cpu > 80 or predicted_memory > 85 or predicted_queue_length > 50:
            urgency = 'high'
        elif predicted_cpu > 70 or predicted_memory > 75 or predicted_queue_length > 25:
            urgency = 'medium'
        
        # Determine scaling action
        if predicted_cpu > self.scaling_thresholds['cpu_high'] or predicted_memory > self.scaling_thresholds['memory_high'] or predicted_queue_length > self.scaling_thresholds['queue_high']:
            # Scale down
            recommended_tasks = max(1, current_parallel_tasks - 1)
            scaling_action = 'scale_down'
        elif predicted_cpu < self.scaling_thresholds['cpu_low'] and predicted_memory < self.scaling_thresholds['memory_low'] and predicted_queue_length < self.scaling_thresholds['queue_low']:
            # Scale up
            recommended_tasks = min(10, current_parallel_tasks + 1)
            scaling_action = 'scale_up'
        else:
            # Maintain current level
            recommended_tasks = current_parallel_tasks
            scaling_action = 'maintain'
        
        return recommended_tasks, scaling_action, urgency
    
    async def get_prediction_accuracy(self) -> Dict[str, Any]:
        """Calculate prediction accuracy from historical predictions"""
        if len(self.prediction_history) < 10:
            return {'accuracy': 0.0, 'sample_count': 0}
        
        # Calculate accuracy for recent predictions
        recent_predictions = self.prediction_history[-100:]  # Last 100 predictions
        
        cpu_errors = []
        memory_errors = []
        queue_errors = []
        
        for pred_data in recent_predictions:
            prediction = pred_data['prediction']
            actual = pred_data['actual_metrics']
            
            # Calculate errors (simplified - in production, you'd need actual future values)
            cpu_error = abs(prediction.predicted_cpu - actual.get('cpu_percent', 0))
            memory_error = abs(prediction.predicted_memory - actual.get('memory_percent', 0))
            queue_error = abs(prediction.predicted_queue_length - actual.get('queue_length', 0))
            
            cpu_errors.append(cpu_error)
            memory_errors.append(memory_error)
            queue_errors.append(queue_error)
        
        # Calculate mean absolute errors
        cpu_mae = np.mean(cpu_errors) if cpu_errors else 0
        memory_mae = np.mean(memory_errors) if memory_errors else 0
        queue_mae = np.mean(queue_errors) if queue_errors else 0
        
        # Calculate overall accuracy (lower error = higher accuracy)
        overall_accuracy = max(0, 1 - (cpu_mae + memory_mae + queue_mae) / 300)  # Normalize to 0-1
        
        return {
            'accuracy': overall_accuracy,
            'cpu_mae': cpu_mae,
            'memory_mae': memory_mae,
            'queue_mae': queue_mae,
            'sample_count': len(recent_predictions),
            'model_accuracy': self.model_accuracy
        }
    
    async def get_scaling_recommendations(self, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive scaling recommendations"""
        try:
            prediction = await self.predict_load(current_metrics)
            accuracy = await self.get_prediction_accuracy()
            
            return {
                'prediction': {
                    'predicted_cpu': prediction.predicted_cpu,
                    'predicted_memory': prediction.predicted_memory,
                    'predicted_queue_length': prediction.predicted_queue_length,
                    'confidence': prediction.confidence,
                    'horizon_minutes': prediction.prediction_horizon
                },
                'recommendation': {
                    'parallel_tasks': prediction.recommended_parallel_tasks,
                    'action': prediction.scaling_action,
                    'urgency': prediction.urgency
                },
                'accuracy': accuracy,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting scaling recommendations: {e}")
            return {'error': str(e)}

# Global instance
_predictive_scaling_service = None

def get_predictive_scaling_service() -> PredictiveScalingService:
    """Get global predictive scaling service instance"""
    global _predictive_scaling_service
    if _predictive_scaling_service is None:
        from database.connection import get_db_config
        _predictive_scaling_service = PredictiveScalingService(get_db_config())
    return _predictive_scaling_service


