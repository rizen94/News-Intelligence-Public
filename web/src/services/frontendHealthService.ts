/**
 * Frontend Health Service
 * Provides health check endpoints and status for the frontend.
 * Uses the same API base URL as the rest of the app (apiConfig) so monitoring
 * and data loading always reflect the same connection.
 */

import { getCurrentApiUrl } from '../config/apiConfig';

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  timestamp: string;
  api_connected: boolean;
  api_response_time_ms?: number;
  errors?: string[];
}

function getHealthCheckUrl(): string {
  const base = getCurrentApiUrl();
  if (!base || base === '') {
    return '/api/system_monitoring/health';
  }
  return `${base.replace(/\/$/, '')}/api/system_monitoring/health`;
}

class FrontendHealthService {
  private healthStatus: HealthStatus | null = null;
  private checkInterval: ReturnType<typeof setInterval> | null = null;

  /**
   * Check frontend health by testing API connection.
   * Uses same base URL as app (localStorage + env) so status matches data loading.
   */
  async checkHealth(): Promise<HealthStatus> {
    const startTime = performance.now();
    const errors: string[] = [];
    let api_connected = false;
    let api_response_time_ms: number | undefined;
    const healthUrl = getHealthCheckUrl();

    try {
      const response = await fetch(healthUrl, {
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
   * Report health status to API (same base URL as app).
   */
  async reportHealthToAPI(): Promise<void> {
    try {
      const health = this.getHealthStatus();
      if (!health) {
        return;
      }

      const base = getCurrentApiUrl();
      const url = !base || base === ''
        ? '/api/system_monitoring/route_supervisor/check_now'
        : `${base.replace(/\/$/, '')}/api/system_monitoring/route_supervisor/check_now`;
      await fetch(url, {
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

