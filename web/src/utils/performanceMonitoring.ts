/**
 * Performance Monitoring Utilities for News Intelligence System v3.0
 * Real-time performance tracking and alerting
 */

// Performance metrics interface
interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
  tags?: Record<string, string>;
}

// Performance thresholds
interface PerformanceThresholds {
  apiResponseTime: number; // ms
  pageLoadTime: number; // ms
  memoryUsage: number; // MB
  errorRate: number; // percentage
}

// Performance monitoring class
class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private thresholds: PerformanceThresholds;
  private observers: Set<(metric: PerformanceMetric) => void> = new Set();
  private isEnabled: boolean = true;

  constructor(thresholds: PerformanceThresholds) {
    this.thresholds = thresholds;
    this.startMonitoring();
  }

  // Add a performance metric
  addMetric(name: string, value: number, tags?: Record<string, string>): void {
    if (!this.isEnabled) return;

    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      tags,
    };

    this.metrics.push(metric);
    this.checkThresholds(metric);
    this.notifyObservers(metric);

    // Keep only last 1000 metrics to prevent memory leaks
    if (this.metrics.length > 1000) {
      this.metrics = this.metrics.slice(-1000);
    }
  }

  // Get metrics by name
  getMetrics(name: string, timeRange?: { start: number; end: number }): PerformanceMetric[] {
    let filtered = this.metrics.filter(m => m.name === name);
    
    if (timeRange) {
      filtered = filtered.filter(m => 
        m.timestamp >= timeRange.start && m.timestamp <= timeRange.end
      );
    }

    return filtered;
  }

  // Get average metric value
  getAverageMetric(name: string, timeRange?: { start: number; end: number }): number {
    const metrics = this.getMetrics(name, timeRange);
    if (metrics.length === 0) return 0;

    const sum = metrics.reduce((acc, metric) => acc + metric.value, 0);
    return sum / metrics.length;
  }

  // Get metric statistics
  getMetricStats(name: string, timeRange?: { start: number; end: number }) {
    const metrics = this.getMetrics(name, timeRange);
    if (metrics.length === 0) return null;

    const values = metrics.map(m => m.value);
    const sorted = values.sort((a, b) => a - b);

    return {
      count: metrics.length,
      min: sorted[0],
      max: sorted[sorted.length - 1],
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      p50: sorted[Math.floor(sorted.length * 0.5)],
      p95: sorted[Math.floor(sorted.length * 0.95)],
      p99: sorted[Math.floor(sorted.length * 0.99)],
    };
  }

  // Check if metric exceeds thresholds
  private checkThresholds(metric: PerformanceMetric): void {
    const threshold = this.getThreshold(metric.name);
    if (threshold && metric.value > threshold) {
      this.alertThresholdExceeded(metric, threshold);
    }
  }

  // Get threshold for metric
  private getThreshold(metricName: string): number | null {
    switch (metricName) {
      case 'api_response_time':
        return this.thresholds.apiResponseTime;
      case 'page_load_time':
        return this.thresholds.pageLoadTime;
      case 'memory_usage':
        return this.thresholds.memoryUsage;
      case 'error_rate':
        return this.thresholds.errorRate;
      default:
        return null;
    }
  }

  // Alert when threshold is exceeded
  private alertThresholdExceeded(metric: PerformanceMetric, threshold: number): void {
    console.warn(`Performance Alert: ${metric.name} exceeded threshold`, {
      value: metric.value,
      threshold,
      tags: metric.tags,
    });

    // Dispatch custom event for external handling
    window.dispatchEvent(new CustomEvent('performanceAlert', {
      detail: { metric, threshold }
    }));
  }

  // Notify observers
  private notifyObservers(metric: PerformanceMetric): void {
    this.observers.forEach(observer => observer(metric));
  }

  // Subscribe to metrics
  subscribe(observer: (metric: PerformanceMetric) => void): () => void {
    this.observers.add(observer);
    return () => this.observers.delete(observer);
  }

  // Start monitoring
  private startMonitoring(): void {
    // Monitor page load time
    if (typeof window !== 'undefined') {
      window.addEventListener('load', () => {
        const loadTime = performance.now();
        this.addMetric('page_load_time', loadTime);
      });

      // Monitor memory usage (if available)
      if ('memory' in performance) {
        setInterval(() => {
          const memory = (performance as any).memory;
          const usedMB = memory.usedJSHeapSize / 1024 / 1024;
          this.addMetric('memory_usage', usedMB);
        }, 30000); // Every 30 seconds
      }

      // Monitor API response times
      this.monitorAPICalls();
    }
  }

  // Monitor API calls
  private monitorAPICalls(): void {
    const originalFetch = window.fetch;
    
    window.fetch = async (...args) => {
      const startTime = performance.now();
      
      try {
        const response = await originalFetch(...args);
        const endTime = performance.now();
        const responseTime = endTime - startTime;
        
        this.addMetric('api_response_time', responseTime, {
          url: args[0] as string,
          status: response.status.toString(),
        });
        
        return response;
      } catch (error) {
        const endTime = performance.now();
        const responseTime = endTime - startTime;
        
        this.addMetric('api_response_time', responseTime, {
          url: args[0] as string,
          error: 'true',
        });
        
        throw error;
      }
    };
  }

  // Enable/disable monitoring
  setEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
  }

  // Clear all metrics
  clearMetrics(): void {
    this.metrics = [];
  }

  // Export metrics for external analysis
  exportMetrics(): PerformanceMetric[] {
    return [...this.metrics];
  }
}

// Default thresholds
const defaultThresholds: PerformanceThresholds = {
  apiResponseTime: 2000, // 2 seconds
  pageLoadTime: 3000, // 3 seconds
  memoryUsage: 100, // 100 MB
  errorRate: 5, // 5%
};

// Create global instance
export const performanceMonitor = new PerformanceMonitor(defaultThresholds);

// Utility functions
export const trackAPICall = async <T>(
  apiCall: () => Promise<T>,
  name: string,
  tags?: Record<string, string>
): Promise<T> => {
  const startTime = performance.now();
  
  try {
    const result = await apiCall();
    const endTime = performance.now();
    const responseTime = endTime - startTime;
    
    performanceMonitor.addMetric('api_response_time', responseTime, {
      name,
      success: 'true',
      ...tags,
    });
    
    return result;
  } catch (error) {
    const endTime = performance.now();
    const responseTime = endTime - startTime;
    
    performanceMonitor.addMetric('api_response_time', responseTime, {
      name,
      success: 'false',
      error: error instanceof Error ? error.message : 'Unknown error',
      ...tags,
    });
    
    throw error;
  }
};

export const trackUserAction = (action: string, duration?: number, tags?: Record<string, string>): void => {
  performanceMonitor.addMetric('user_action', duration || 0, {
    action,
    ...tags,
  });
};

export const trackError = (error: Error, context?: string, tags?: Record<string, string>): void => {
  performanceMonitor.addMetric('error', 1, {
    error: error.message,
    context: context || 'unknown',
    ...tags,
  });
};

// React hook for performance monitoring
export const usePerformanceMonitoring = () => {
  const [metrics, setMetrics] = React.useState<PerformanceMetric[]>([]);

  React.useEffect(() => {
    const unsubscribe = performanceMonitor.subscribe((metric) => {
      setMetrics(prev => [...prev.slice(-100), metric]); // Keep last 100 metrics
    });

    return unsubscribe;
  }, []);

  return {
    metrics,
    addMetric: performanceMonitor.addMetric.bind(performanceMonitor),
    getMetrics: performanceMonitor.getMetrics.bind(performanceMonitor),
    getAverageMetric: performanceMonitor.getAverageMetric.bind(performanceMonitor),
    getMetricStats: performanceMonitor.getMetricStats.bind(performanceMonitor),
  };
};

export default performanceMonitor;


