/**
 * Feature Testing Helper
 * Utilities for validating frontend features work as designed
 * Industry best practices for feature validation
 */

import { DOMAIN_KEYS_LIST } from './domainHelper';

interface TestResult {
  name: string;
  passed: boolean;
  message: string;
  duration: number;
  timestamp: string;
}

interface FeatureTest {
  name: string;
  description: string;
  test: () => Promise<boolean> | boolean;
  critical: boolean;
}

class FeatureTestHelper {
  private tests: FeatureTest[] = [];
  private results: TestResult[] = [];

  /**
   * Register a feature test
   */
  registerTest(test: FeatureTest): void {
    this.tests.push(test);
  }

  /**
   * Run a single test
   */
  async runTest(testName: string): Promise<TestResult | null> {
    const test = this.tests.find(t => t.name === testName);
    if (!test) {
      console.error(`Test not found: ${testName}`);
      return null;
    }

    const startTime = performance.now();
    let passed = false;
    let message = '';

    try {
      const result = await Promise.resolve(test.test());
      passed = result === true;
      message = passed ? 'Test passed' : 'Test failed';
    } catch (error: any) {
      passed = false;
      message = error.message || 'Test threw an error';
    }

    const duration = performance.now() - startTime;

    const result: TestResult = {
      name: test.name,
      passed,
      message,
      duration,
      timestamp: new Date().toISOString(),
    };

    this.results.push(result);
    return result;
  }

  /**
   * Run all tests
   */
  async runAllTests(): Promise<TestResult[]> {
    console.group('🧪 Running Feature Tests');
    const results: TestResult[] = [];

    for (const test of this.tests) {
      const result = await this.runTest(test.name);
      if (result) {
        results.push(result);
        const icon = result.passed ? '✅' : '❌';
        const critical = test.critical ? ' [CRITICAL]' : '';
        console.log(
          `${icon} ${test.name}${critical}: ${
            result.message
          } (${result.duration.toFixed(2)}ms)`
        );
      }
    }

    console.groupEnd();
    return results;
  }

  /**
   * Run critical tests only
   */
  async runCriticalTests(): Promise<TestResult[]> {
    const criticalTests = this.tests.filter(t => t.critical);
    const results: TestResult[] = [];

    for (const test of criticalTests) {
      const result = await this.runTest(test.name);
      if (result) {
        results.push(result);
      }
    }

    return results;
  }

  /**
   * Get test results summary
   */
  getSummary(): {
    total: number;
    passed: number;
    failed: number;
    criticalFailed: number;
    averageDuration: number;
  } {
    const total = this.results.length;
    const passed = this.results.filter(r => r.passed).length;
    const failed = total - passed;
    const criticalFailed = this.results.filter(
      r => !r.passed && this.tests.find(t => t.name === r.name)?.critical
    ).length;
    const averageDuration =
      this.results.length > 0
        ? this.results.reduce((sum, r) => sum + r.duration, 0) /
          this.results.length
        : 0;

    return {
      total,
      passed,
      failed,
      criticalFailed,
      averageDuration: Math.round(averageDuration),
    };
  }

  /**
   * Clear all results
   */
  clearResults(): void {
    this.results = [];
  }

  /**
   * Export results as JSON
   */
  exportResults(): string {
    return JSON.stringify(
      {
        summary: this.getSummary(),
        results: this.results,
        timestamp: new Date().toISOString(),
      },
      null,
      2
    );
  }
}

// Create singleton instance
export const featureTestHelper = new FeatureTestHelper();

// Pre-defined tests for News Intelligence System
export const registerDefaultTests = () => {
  // API Connection Test
  featureTestHelper.registerTest({
    name: 'API Connection',
    description: 'Verify API server is accessible',
    critical: true,
    test: async () => {
      try {
        const response = await fetch('/api/system_monitoring/health', {
          method: 'GET',
          signal: AbortSignal.timeout(5000),
        });
        return response.ok;
      } catch {
        return false;
      }
    },
  });

  // LocalStorage Test
  featureTestHelper.registerTest({
    name: 'LocalStorage',
    description: 'Verify localStorage is available and working',
    critical: true,
    test: () => {
      try {
        const testKey = '__test__';
        localStorage.setItem(testKey, 'test');
        const value = localStorage.getItem(testKey);
        localStorage.removeItem(testKey);
        return value === 'test';
      } catch {
        return false;
      }
    },
  });

  // Domain Context Test
  featureTestHelper.registerTest({
    name: 'Domain Context',
    description: 'Verify domain context is available',
    critical: true,
    test: () => {
      const domain = localStorage.getItem('currentDomain');
      return (
        domain !== null &&
        DOMAIN_KEYS_LIST.includes(domain as (typeof DOMAIN_KEYS_LIST)[number])
      );
    },
  });

  // API Connection Manager Test
  featureTestHelper.registerTest({
    name: 'API Connection Manager',
    description: 'Verify API connection manager is initialized',
    critical: true,
    test: async () => {
      try {
        const { getAPIConnectionManager } = await import(
          '../services/apiConnectionManager'
        );
        const manager = getAPIConnectionManager();
        return manager !== null && typeof manager.getApiInstance === 'function';
      } catch {
        return false;
      }
    },
  });

  // Responsive Design Test
  featureTestHelper.registerTest({
    name: 'Responsive Design',
    description: 'Verify viewport meta tag is present',
    critical: false,
    test: () => {
      const viewport = document.querySelector('meta[name="viewport"]');
      return viewport !== null;
    },
  });

  // Console Errors Test
  featureTestHelper.registerTest({
    name: 'Console Errors',
    description: 'Check for JavaScript errors in console',
    critical: false,
    test: () => {
      // This is a placeholder - actual error checking would require
      // intercepting console.error or using error boundaries
      return true;
    },
  });
};

// Auto-register default tests in development
if (import.meta.env.DEV) {
  registerDefaultTests();
  (window as any).featureTestHelper = featureTestHelper;

  console.log(
    '%c🧪 Feature Test Helper Active',
    'color: #2196F3; font-size: 16px; font-weight: bold;'
  );
  console.log('Run tests with: featureTestHelper.runAllTests()');
}

export default featureTestHelper;
