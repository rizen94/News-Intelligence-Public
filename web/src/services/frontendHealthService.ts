/**
 * Frontend Health Service
 * Provides health check endpoints and status for the frontend
 */

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  timestamp: string;
  api_connected: boolean;
  api_response_time_ms?: number;
  errors?: string[];
}

class FrontendHealthService {
  private healthStatus: HealthStatus | null = null;
  private checkInterval: ReturnType<typeof setInterval> | null = null;
  private apiBaseUrl: string;

  constructor() {
    // Get API base URL from config or environment
    this.apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  }

  /**
   * Check frontend health by testing API connection
   */
  async checkHealth(): Promise<HealthStatus> {
    const startTime = performance.now();
    const errors: string[] = [];
    let api_connected = false;
    let api_response_time_ms: number | undefined;

    try {
      // Test API connection
      const response = await fetch(`${this.apiBaseUrl}/api/v4/system_monitoring/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000), // 5 second timeout
      });

      api_response_time_ms = performance.now() - startTime;
      api_connected = response.ok;

      if (!response.ok) {
        errors.push(`API returned status ${response.status}`);
      }
    } catch (error: any) {
      api_response_time_ms = performance.now() - startTime;
      api_connected = false;

      if (error.name === 'TimeoutError') {
        errors.push('API connection timeout');
      } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
        errors.push('Cannot connect to API server');
      } else {
        errors.push(error.message || 'Unknown error');
      }
    }

    // Determine overall status
    let status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
    if (api_connected && errors.length === 0) {
      if (api_response_time_ms && api_response_time_ms > 2000) {
        status = 'degraded';
      } else {
        status = 'healthy';
      }
    } else if (errors.length > 0) {
      status = 'unhealthy';
    } else {
      status = 'unknown';
    }

    this.healthStatus = {
      status,
      timestamp: new Date().toISOString(),
      api_connected,
      api_response_time_ms,
      errors: errors.length > 0 ? errors : undefined,
    };

    return this.healthStatus;
  }

  /**
   * Start continuous health monitoring
   */
  startMonitoring(intervalMs: number = 30000): void {
    if (this.checkInterval) {
      this.stopMonitoring();
    }

    // Initial check
    this.checkHealth();

    // Set up interval
    this.checkInterval = setInterval(() => {
      this.checkHealth();
    }, intervalMs);
  }

  /**
   * Stop health monitoring
   */
  stopMonitoring(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  /**
   * Get current health status
   */
  getHealthStatus(): HealthStatus | null {
    return this.healthStatus;
  }

  /**
   * Report health status to API
   */
  async reportHealthToAPI(): Promise<void> {
    try {
      const health = this.getHealthStatus();
      if (!health) {
        return;
      }

      // Report to route supervisor
      await fetch(`${this.apiBaseUrl}/api/v4/system_monitoring/route_supervisor/check_now`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
    } catch (error) {
      console.warn('Failed to report health to API:', error);
    }
  }
}

// Export singleton instance
export const frontendHealthService = new FrontendHealthService();

// NOTE: Auto-monitoring disabled - let App.tsx control when to start monitoring
// This prevents automatic health checks that can cause false "disconnected" states
// if (typeof window !== 'undefined') {
//   frontendHealthService.startMonitoring(30000); // Check every 30 seconds
// }

