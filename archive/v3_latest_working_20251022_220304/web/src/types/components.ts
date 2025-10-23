/**
 * Component-specific type definitions
 */

import React, { ReactNode } from 'react';

// ============================================================================
// Base Component Types
// ============================================================================

export interface BaseComponentProps {
  className?: string;
  children?: ReactNode;
  id?: string;
  'data-testid'?: string;
}

export interface ClickableProps extends BaseComponentProps {
  onClick?: (event: React.MouseEvent) => void;
  disabled?: boolean;
}

export interface FormProps extends BaseComponentProps {
  onSubmit?: (event: React.FormEvent) => void;
  onReset?: (event: React.FormEvent) => void;
}

// ============================================================================
// Layout Component Types
// ============================================================================

export interface LayoutProps extends BaseComponentProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  loading?: boolean;
  error?: string | null;
}

export interface CardProps extends BaseComponentProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  elevation?: number;
  variant?: 'elevation' | 'outlined';
}

export interface ModalProps extends BaseComponentProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: 'small' | 'medium' | 'large' | 'fullscreen';
  fullWidth?: boolean;
  maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
}

export interface DialogProps extends ModalProps {
  onConfirm?: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success';
  loading?: boolean;
}

// ============================================================================
// Data Display Component Types
// ============================================================================

export interface TableProps<T = any> extends BaseComponentProps {
  data: T[];
  columns: TableColumn<T>[];
  loading?: boolean;
  error?: string | null;
  pagination?: PaginationProps;
  sorting?: SortingProps;
  filtering?: FilteringProps;
  selection?: SelectionProps<T>;
  onRowClick?: (row: T) => void;
  onRowDoubleClick?: (row: T) => void;
}

export interface TableColumn<T = any> {
  key: string;
  title: string;
  dataIndex: keyof T;
  render?: (value: any, record: T, index: number) => ReactNode;
  sortable?: boolean;
  filterable?: boolean;
  width?: number | string;
  align?: 'left' | 'center' | 'right';
  fixed?: 'left' | 'right';
}

export interface PaginationProps {
  current: number;
  pageSize: number;
  total: number;
  showSizeChanger?: boolean;
  showQuickJumper?: boolean;
  showTotal?: (total: number, range: [number, number]) => ReactNode;
  onChange?: (page: number, pageSize: number) => void;
}

export interface SortingProps {
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (sortBy: string, sortOrder: 'asc' | 'desc') => void;
}

export interface FilteringProps {
  filters?: Record<string, any>;
  onFilter?: (filters: Record<string, any>) => void;
  filterOptions?: Record<string, FilterOption[]>;
}

export interface FilterOption {
  label: string;
  value: any;
  count?: number;
}

export interface SelectionProps<T = any> {
  selectedKeys?: string[];
  onSelectionChange?: (selectedKeys: string[], selectedRows: T[]) => void;
  rowSelection?: boolean;
  getRowKey?: (record: T) => string;
}

// ============================================================================
// Form Component Types
// ============================================================================

export interface FormFieldProps extends BaseComponentProps {
  name: string;
  label?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string | null;
  helperText?: string;
  value?: any;
  onChange?: (value: any) => void;
  onBlur?: (event: React.FocusEvent) => void;
  onFocus?: (event: React.FocusEvent) => void;
}

export interface InputProps extends FormFieldProps {
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url';
  multiline?: boolean;
  rows?: number;
  maxLength?: number;
  minLength?: number;
  pattern?: string;
}

export interface SelectProps extends FormFieldProps {
  options: SelectOption[];
  multiple?: boolean;
  searchable?: boolean;
  clearable?: boolean;
  loading?: boolean;
}

export interface SelectOption {
  label: string;
  value: any;
  disabled?: boolean;
  group?: string;
}

export interface CheckboxProps extends FormFieldProps {
  checked?: boolean;
  indeterminate?: boolean;
  label?: string;
}

export interface RadioProps extends FormFieldProps {
  options: RadioOption[];
  direction?: 'horizontal' | 'vertical';
}

export interface RadioOption {
  label: string;
  value: any;
  disabled?: boolean;
}

export interface DatePickerProps extends FormFieldProps {
  format?: string;
  minDate?: Date;
  maxDate?: Date;
  showTime?: boolean;
  timeFormat?: string;
}

// ============================================================================
// Navigation Component Types
// ============================================================================

export interface NavigationProps extends BaseComponentProps {
  items: NavigationItem[];
  activeKey?: string;
  onSelect?: (key: string) => void;
  mode?: 'horizontal' | 'vertical' | 'inline';
  theme?: 'light' | 'dark';
}

export interface NavigationItem {
  key: string;
  label: string;
  icon?: ReactNode;
  path?: string;
  children?: NavigationItem[];
  disabled?: boolean;
  badge?: number | string;
}

export interface BreadcrumbProps extends BaseComponentProps {
  items: BreadcrumbItem[];
  separator?: ReactNode;
  maxItems?: number;
}

export interface BreadcrumbItem {
  label: string;
  path?: string;
  icon?: ReactNode;
}

// ============================================================================
// Feedback Component Types
// ============================================================================

export interface AlertProps extends BaseComponentProps {
  type: 'success' | 'info' | 'warning' | 'error';
  title?: string;
  message: string;
  closable?: boolean;
  showIcon?: boolean;
  action?: ReactNode;
  onClose?: () => void;
}

export interface LoadingProps extends BaseComponentProps {
  loading: boolean;
  text?: string;
  size?: 'small' | 'medium' | 'large';
  overlay?: boolean;
}

export interface ProgressProps extends BaseComponentProps {
  percent: number;
  status?: 'success' | 'exception' | 'active' | 'normal';
  strokeColor?: string;
  trailColor?: string;
  strokeWidth?: number;
  showInfo?: boolean;
  format?: (percent: number) => string;
}

// ============================================================================
// Data Visualization Component Types
// ============================================================================

export interface ChartProps extends BaseComponentProps {
  data: any[];
  type: 'line' | 'bar' | 'pie' | 'area' | 'scatter' | 'radar' | 'gauge';
  width?: number | string;
  height?: number | string;
  title?: string;
  subtitle?: string;
  legend?: boolean;
  tooltip?: boolean;
  animation?: boolean;
  responsive?: boolean;
}

export interface MetricCardProps extends BaseComponentProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    type: 'increase' | 'decrease' | 'neutral';
    period?: string;
  };
  icon?: ReactNode;
  color?: string;
  loading?: boolean;
}

// ============================================================================
// Utility Component Types
// ============================================================================

export interface TooltipProps extends BaseComponentProps {
  title: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  trigger?: 'hover' | 'click' | 'focus';
  arrow?: boolean;
  delay?: number;
}

export interface PopoverProps extends BaseComponentProps {
  content: ReactNode;
  title?: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  trigger?: 'hover' | 'click' | 'focus';
  visible?: boolean;
  onVisibleChange?: (visible: boolean) => void;
}

export interface DropdownProps extends BaseComponentProps {
  items: DropdownItem[];
  trigger?: 'hover' | 'click' | 'contextMenu';
  placement?: 'top' | 'bottom' | 'left' | 'right';
  disabled?: boolean;
}

export interface DropdownItem {
  key: string;
  label: string;
  icon?: ReactNode;
  disabled?: boolean;
  danger?: boolean;
  onClick?: () => void;
  children?: DropdownItem[];
}
