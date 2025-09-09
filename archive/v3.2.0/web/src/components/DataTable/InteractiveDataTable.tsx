import React, { useState, useMemo } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TablePagination,
  TableSortLabel,
  TextField,
  Box,
  Chip,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Button,
  Typography,
  Checkbox,
  TableRowProps
} from '@mui/material';
import {
  FilterList,
  Search,
  MoreVert,
  Visibility,
  Edit,
  Delete,
  BookmarkBorder,
  Bookmark,
  Share,
  Analytics,
  Timeline
} from '@mui/icons-material';

export interface Column {
  id: string;
  label: string;
  minWidth?: number;
  align?: 'right' | 'left' | 'center';
  sortable?: boolean;
  filterable?: boolean;
  render?: (value: any, row: any) => React.ReactNode;
}

export interface DataTableProps {
  columns: Column[];
  data: any[];
  loading?: boolean;
  onRowClick?: (row: any) => void;
  onRowAction?: (action: string, row: any) => void;
  onSort?: (field: string, direction: 'asc' | 'desc') => void;
  onFilter?: (filters: Record<string, any>) => void;
  onPageChange?: (page: number, rowsPerPage: number) => void;
  totalCount?: number;
  page?: number;
  rowsPerPage?: number;
  selectable?: boolean;
  selectedRows?: any[];
  onSelectionChange?: (selectedRows: any[]) => void;
  actions?: Array<{
    label: string;
    icon: React.ReactNode;
    onClick: (row: any) => void;
    disabled?: (row: any) => boolean;
  }>;
}

const InteractiveDataTable: React.FC<DataTableProps> = ({
  columns,
  data,
  loading = false,
  onRowClick,
  onRowAction,
  onSort,
  onFilter,
  onPageChange,
  totalCount = 0,
  page = 0,
  rowsPerPage = 10,
  selectable = false,
  selectedRows = [],
  onSelectionChange,
  actions = []
}) => {
  const [sortField, setSortField] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filters, setFilters] = useState<Record<string, any>>({});
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedRow, setSelectedRow] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const handleSort = (field: string) => {
    const isAsc = sortField === field && sortDirection === 'asc';
    const newDirection = isAsc ? 'desc' : 'asc';
    setSortField(field);
    setSortDirection(newDirection);
    onSort?.(field, newDirection);
  };

  const handleFilter = (field: string, value: any) => {
    const newFilters = { ...filters, [field]: value };
    setFilters(newFilters);
    onFilter?.(newFilters);
  };

  const handleSearch = (value: string) => {
    setSearchTerm(value);
    handleFilter('search', value);
  };

  const handleRowClick = (row: any) => {
    onRowClick?.(row);
  };

  const handleRowAction = (action: string, row: any) => {
    onRowAction?.(action, row);
    setAnchorEl(null);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, row: any) => {
    setAnchorEl(event.currentTarget);
    setSelectedRow(row);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedRow(null);
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      onSelectionChange?.(data);
    } else {
      onSelectionChange?.([]);
    }
  };

  const handleSelectRow = (row: any, checked: boolean) => {
    if (checked) {
      onSelectionChange?.([...selectedRows, row]);
    } else {
      onSelectionChange?.(selectedRows.filter(r => r.id !== row.id));
    }
  };

  const isSelected = (row: any) => selectedRows.some(r => r.id === row.id);

  const filteredData = useMemo(() => {
    if (!searchTerm) return data;
    return data.filter(row =>
      Object.values(row).some(value =>
        String(value).toLowerCase().includes(searchTerm.toLowerCase())
      )
    );
  }, [data, searchTerm]);

  const renderCellContent = (column: Column, row: any) => {
    const value = row[column.id];
    
    if (column.render) {
      return column.render(value, row);
    }

    // Default rendering based on data type
    if (typeof value === 'boolean') {
      return (
        <Chip
          label={value ? 'Yes' : 'No'}
          color={value ? 'success' : 'default'}
          size="small"
        />
      );
    }

    if (typeof value === 'string' && value.includes('http')) {
      return (
        <Typography
          variant="body2"
          color="primary"
          sx={{ cursor: 'pointer', textDecoration: 'underline' }}
          onClick={() => window.open(value, '_blank')}
        >
          {value.length > 50 ? `${value.substring(0, 50)}...` : value}
        </Typography>
      );
    }

    if (typeof value === 'string' && value.length > 100) {
      return (
        <Tooltip title={value}>
          <Typography variant="body2">
            {value.substring(0, 100)}...
          </Typography>
        </Tooltip>
      );
    }

    return <Typography variant="body2">{String(value)}</Typography>;
  };

  return (
    <Paper sx={{ width: '100%', overflow: 'hidden' }}>
      {/* Search and Filter Bar */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
          <TextField
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            size="small"
            InputProps={{
              startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />
            }}
            sx={{ minWidth: 200 }}
          />
          
          {columns
            .filter(col => col.filterable)
            .map(column => (
              <FormControl key={column.id} size="small" sx={{ minWidth: 120 }}>
                <InputLabel>{column.label}</InputLabel>
                <Select
                  value={filters[column.id] || ''}
                  onChange={(e) => handleFilter(column.id, e.target.value)}
                  label={column.label}
                >
                  <MenuItem value="">All</MenuItem>
                  {Array.from(new Set(data.map(row => row[column.id])))
                    .filter(value => value !== null && value !== undefined)
                    .map(value => (
                      <MenuItem key={String(value)} value={String(value)}>
                        {String(value)}
                      </MenuItem>
                    ))}
                </Select>
              </FormControl>
            ))}
        </Box>

        {/* Selection Actions */}
        {selectable && selectedRows.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              {selectedRows.length} selected
            </Typography>
            <Button size="small" startIcon={<BookmarkBorder />}>
              Bookmark
            </Button>
            <Button size="small" startIcon={<Analytics />}>
              Analyze
            </Button>
            <Button size="small" startIcon={<Timeline />}>
              Add to Storyline
            </Button>
          </Box>
        )}
      </Box>

      {/* Table */}
      <TableContainer sx={{ maxHeight: 600 }}>
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              {selectable && (
                <TableCell padding="checkbox">
                  <Checkbox
                    indeterminate={selectedRows.length > 0 && selectedRows.length < data.length}
                    checked={data.length > 0 && selectedRows.length === data.length}
                    onChange={handleSelectAll}
                  />
                </TableCell>
              )}
              
              {columns.map(column => (
                <TableCell
                  key={column.id}
                  align={column.align}
                  style={{ minWidth: column.minWidth }}
                >
                  {column.sortable ? (
                    <TableSortLabel
                      active={sortField === column.id}
                      direction={sortField === column.id ? sortDirection : 'asc'}
                      onClick={() => handleSort(column.id)}
                    >
                      {column.label}
                    </TableSortLabel>
                  ) : (
                    column.label
                  )}
                </TableCell>
              ))}
              
              {actions.length > 0 && (
                <TableCell align="center" style={{ minWidth: 100 }}>
                  Actions
                </TableCell>
              )}
            </TableRow>
          </TableHead>
          
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={columns.length + (selectable ? 1 : 0) + (actions.length > 0 ? 1 : 0)}>
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <Typography>Loading...</Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : filteredData.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length + (selectable ? 1 : 0) + (actions.length > 0 ? 1 : 0)}>
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <Typography color="text.secondary">No data available</Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              filteredData.map((row, index) => (
                <TableRow
                  key={row.id || index}
                  hover
                  onClick={() => handleRowClick(row)}
                  sx={{ cursor: onRowClick ? 'pointer' : 'default' }}
                >
                  {selectable && (
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={isSelected(row)}
                        onChange={(e) => handleSelectRow(row, e.target.checked)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </TableCell>
                  )}
                  
                  {columns.map(column => (
                    <TableCell key={column.id} align={column.align}>
                      {renderCellContent(column, row)}
                    </TableCell>
                  ))}
                  
                  {actions.length > 0 && (
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleMenuOpen(e, row);
                        }}
                      >
                        <MoreVert />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      <TablePagination
        rowsPerPageOptions={[5, 10, 25, 50]}
        component="div"
        count={totalCount || filteredData.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={(event, newPage) => onPageChange?.(newPage, rowsPerPage)}
        onRowsPerPageChange={(event) => onPageChange?.(0, parseInt(event.target.value, 10))}
      />

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        {actions.map((action, index) => (
          <MenuItem
            key={index}
            onClick={() => handleRowAction(action.label, selectedRow)}
            disabled={action.disabled?.(selectedRow)}
          >
            {action.icon}
            <Typography sx={{ ml: 1 }}>{action.label}</Typography>
          </MenuItem>
        ))}
      </Menu>
    </Paper>
  );
};

export default InteractiveDataTable;
