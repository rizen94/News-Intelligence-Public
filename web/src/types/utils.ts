/**
 * Utility type definitions
 */

// ============================================================================
// Generic Utility Types
// ============================================================================

export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type Required<T, K extends keyof T> = T & { [P in K]-?: T[P] };

export type PartialExcept<T, K extends keyof T> = Partial<T> & Pick<T, K>;

export type NonNullable<T> = T extends null | undefined ? never : T;

export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type DeepRequired<T> = {
  [P in keyof T]-?: T[P] extends object ? DeepRequired<T[P]> : T[P];
};

// ============================================================================
// Function Types
// ============================================================================

export type AsyncFunction<T = any, R = any> = (...args: T[]) => Promise<R>;

export type EventHandler<T = any> = (event: T) => void;

export type ChangeHandler<T = any> = (value: T) => void;

export type ClickHandler = (event: React.MouseEvent) => void;

export type SubmitHandler = (event: React.FormEvent) => void;

export type KeyboardHandler = (event: React.KeyboardEvent) => void;

export type FocusHandler = (event: React.FocusEvent) => void;

export type BlurHandler = (event: React.FocusEvent) => void;

// ============================================================================
// State Management Types
// ============================================================================

export interface StateAction<T = any> {
  type: string;
  payload?: T;
  meta?: Record<string, any>;
}

export type StateReducer<T, A = StateAction> = (state: T, action: A) => T;

export interface StateSlice<T = any> {
  state: T;
  actions: Record<string, (...args: any[]) => void>;
  selectors: Record<string, (state: T) => any>;
}

// ============================================================================
// API Types
// ============================================================================

export interface RequestConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  url: string;
  data?: any;
  params?: Record<string, any>;
  headers?: Record<string, string>;
  timeout?: number;
}

export interface ResponseConfig<T = any> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
  config: RequestConfig;
}

export interface ErrorConfig {
  message: string;
  status?: number;
  data?: any;
  config?: RequestConfig;
}

// ============================================================================
// Validation Types
// ============================================================================

export interface ValidationRule<T = any> {
  required?: boolean;
  min?: number;
  max?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: RegExp;
  custom?: (value: T) => boolean | string;
  message?: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
}

export interface FormValidation<T = any> {
  rules: Record<keyof T, ValidationRule<T[keyof T]>[]>;
  validate: (data: T) => ValidationResult;
  validateField: (field: keyof T, value: T[keyof T]) => string | null;
}

// ============================================================================
// Date and Time Types
// ============================================================================

export type DateInput = string | number | Date;

export interface DateRange {
  start: DateInput;
  end: DateInput;
}

export interface TimeRange {
  start: string; // HH:mm format
  end: string;   // HH:mm format
}

export interface DateTimeRange {
  start: DateInput;
  end: DateInput;
  timezone?: string;
}

// ============================================================================
// File Types
// ============================================================================

export interface FileUpload {
  file: File;
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

export interface FileUploadProgress {
  file: FileUpload;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  error?: string;
}

export interface FileValidation {
  allowedTypes: string[];
  maxSize: number; // in bytes
  maxFiles?: number;
}

// ============================================================================
// Search and Filter Types
// ============================================================================

export interface SearchConfig {
  query: string;
  fields: string[];
  operator: 'AND' | 'OR';
  caseSensitive?: boolean;
  fuzzy?: boolean;
}

export interface FilterConfig {
  field: string;
  operator: 'equals' | 'contains' | 'startsWith' | 'endsWith' | 'gt' | 'lt' | 'gte' | 'lte' | 'in' | 'notIn';
  value: any;
}

export interface SortConfig {
  field: string;
  direction: 'asc' | 'desc';
}

export interface PaginationConfig {
  page: number;
  limit: number;
  offset?: number;
}

export interface QueryConfig {
  search?: SearchConfig;
  filters?: FilterConfig[];
  sort?: SortConfig[];
  pagination?: PaginationConfig;
}

// ============================================================================
// Event Types
// ============================================================================

export interface CustomEvent<T = any> {
  type: string;
  payload: T;
  timestamp: number;
  source?: string;
}

export interface EventListener<T = any> {
  (event: CustomEvent<T>): void;
}

export interface EventEmitter {
  on: <T = any>(event: string, listener: EventListener<T>) => void;
  off: <T = any>(event: string, listener: EventListener<T>) => void;
  emit: <T = any>(event: string, payload: T) => void;
}

// ============================================================================
// Performance Types
// ============================================================================

export interface PerformanceMetric {
  name: string;
  value: number;
  unit: string;
  timestamp: number;
  metadata?: Record<string, any>;
}

export interface PerformanceObserver {
  observe: (metric: PerformanceMetric) => void;
  disconnect: () => void;
}

// ============================================================================
// Storage Types
// ============================================================================

export interface StorageItem<T = any> {
  key: string;
  value: T;
  expires?: number;
  created: number;
}

export interface StorageConfig {
  prefix?: string;
  expiration?: number; // in milliseconds
  encryption?: boolean;
}

// ============================================================================
// Theme Types
// ============================================================================

export interface ThemeColors {
  primary: string;
  secondary: string;
  success: string;
  warning: string;
  error: string;
  info: string;
  background: string;
  surface: string;
  text: string;
  textSecondary: string;
  border: string;
  divider: string;
}

export interface ThemeSpacing {
  xs: number;
  sm: number;
  md: number;
  lg: number;
  xl: number;
}

export interface ThemeTypography {
  fontFamily: string;
  fontSize: {
    xs: number;
    sm: number;
    md: number;
    lg: number;
    xl: number;
  };
  fontWeight: {
    light: number;
    normal: number;
    medium: number;
    bold: number;
  };
  lineHeight: {
    tight: number;
    normal: number;
    relaxed: number;
  };
}

export interface ThemeConfig {
  mode: 'light' | 'dark';
  colors: ThemeColors;
  spacing: ThemeSpacing;
  typography: ThemeTypography;
  breakpoints: {
    xs: number;
    sm: number;
    md: number;
    lg: number;
    xl: number;
  };
}

// ============================================================================
// Export all utility types
// ============================================================================

export * from './api';
export * from './components';
