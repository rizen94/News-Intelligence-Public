/**
 * API-specific type definitions
 */

export interface APIEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  description: string;
  parameters?: Record<string, any>;
  response: any;
}

export interface APIErrorResponse {
  success: false;
  error: string;
  message: string;
  status_code: number;
  details?: Record<string, any>;
}

export interface APISuccessResponse<T = any> {
  success: true;
  data: T;
  message?: string;
  status_code: number;
}

export type APIResponse<T = any> = APISuccessResponse<T> | APIErrorResponse;

export interface PaginationParams {
  page?: number;
  limit?: number;
  offset?: number;
}

export interface SortParams {
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface FilterParams {
  [key: string]: any;
}

export interface QueryParams extends PaginationParams, SortParams, FilterParams {}

export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'error';
  message: string;
  timestamp: string;
  version: string;
  uptime: number;
  services: {
    database: 'healthy' | 'degraded' | 'error';
    redis: 'healthy' | 'degraded' | 'error';
    api: 'healthy' | 'degraded' | 'error';
  };
}
