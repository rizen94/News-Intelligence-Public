import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Button,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  Slider,
  FormControlLabel,
  Checkbox,
  Paper,
  Divider,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ExpandMore,
  Search,
  Clear,
  FilterList,
  DateRange,
  Category,
  Source,
  TrendingUp,
  Close
} from '@mui/icons-material';
// Date picker imports removed for simplicity

export interface SearchFilters {
  query?: string;
  sources?: string[];
  categories?: string[];
  dateFrom?: Date | null;
  dateTo?: Date | null;
  sentimentRange?: [number, number];
  qualityRange?: [number, number];
  readabilityRange?: [number, number];
  hasSummary?: boolean;
  hasAnalysis?: boolean;
  processingStatus?: string[];
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface AdvancedSearchProps {
  onSearch: (filters: SearchFilters) => void;
  onClear: () => void;
  availableSources?: string[];
  availableCategories?: string[];
  loading?: boolean;
  initialFilters?: SearchFilters;
}

const AdvancedSearch: React.FC<AdvancedSearchProps> = ({
  onSearch,
  onClear,
  availableSources = [],
  availableCategories = [],
  loading = false,
  initialFilters = {}
}) => {
  const [filters, setFilters] = useState<SearchFilters>({
    query: '',
    sources: [],
    categories: [],
    dateFrom: null,
    dateTo: null,
    sentimentRange: [-1, 1],
    qualityRange: [0, 1],
    readabilityRange: [0, 1],
    hasSummary: false,
    hasAnalysis: false,
    processingStatus: [],
    sortBy: 'published_at',
    sortOrder: 'desc',
    ...initialFilters
  });

  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    filters: false,
    advanced: false
  });

  const handleFilterChange = (key: keyof SearchFilters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleArrayFilterChange = (key: keyof SearchFilters, value: string, checked: boolean) => {
    setFilters(prev => {
      const currentArray = (prev[key] as string[]) || [];
      if (checked) {
        return { ...prev, [key]: [...currentArray, value] };
      } else {
        return { ...prev, [key]: currentArray.filter(item => item !== value) };
      }
    });
  };

  const handleSearch = () => {
    onSearch(filters);
  };

  const handleClear = () => {
    setFilters({
      query: '',
      sources: [],
      categories: [],
      dateFrom: null,
      dateTo: null,
      sentimentRange: [-1, 1],
      qualityRange: [0, 1],
      readabilityRange: [0, 1],
      hasSummary: false,
      hasAnalysis: false,
      processingStatus: [],
      sortBy: 'published_at',
      sortOrder: 'desc'
    });
    onClear();
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      handleSearch();
    }
  };

  const getActiveFiltersCount = () => {
    let count = 0;
    if (filters.query) count++;
    if (filters.sources && filters.sources.length > 0) count++;
    if (filters.categories && filters.categories.length > 0) count++;
    if (filters.dateFrom || filters.dateTo) count++;
    if (filters.sentimentRange && (filters.sentimentRange[0] !== -1 || filters.sentimentRange[1] !== 1)) count++;
    if (filters.qualityRange && (filters.qualityRange[0] !== 0 || filters.qualityRange[1] !== 1)) count++;
    if (filters.readabilityRange && (filters.readabilityRange[0] !== 0 || filters.readabilityRange[1] !== 1)) count++;
    if (filters.hasSummary) count++;
    if (filters.hasAnalysis) count++;
    if (filters.processingStatus && filters.processingStatus.length > 0) count++;
    return count;
  };

  const activeFiltersCount = getActiveFiltersCount();

  return (
    <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Advanced Search
              {activeFiltersCount > 0 && (
                <Chip
                  label={`${activeFiltersCount} filters`}
                  size="small"
                  color="primary"
                  sx={{ ml: 1 }}
                />
              )}
            </Typography>
            <Box>
              <Button
                variant="outlined"
                startIcon={<Clear />}
                onClick={handleClear}
                size="small"
                sx={{ mr: 1 }}
              >
                Clear
              </Button>
              <Button
                variant="contained"
                startIcon={<Search />}
                onClick={handleSearch}
                disabled={loading}
                size="small"
              >
                {loading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Box>

          {/* Basic Search */}
          <Accordion
            expanded={expandedSections.basic}
            onChange={() => setExpandedSections(prev => ({ ...prev, basic: !prev.basic }))}
          >
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Basic Search</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Search Query"
                    placeholder="Enter keywords, phrases, or search terms..."
                    value={filters.query || ''}
                    onChange={(e) => handleFilterChange('query', e.target.value)}
                    onKeyPress={handleKeyPress}
                    InputProps={{
                      startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Sort By</InputLabel>
                    <Select
                      value={filters.sortBy || 'published_at'}
                      onChange={(e) => handleFilterChange('sortBy', e.target.value)}
                      label="Sort By"
                    >
                      <MenuItem value="published_at">Published Date</MenuItem>
                      <MenuItem value="created_at">Created Date</MenuItem>
                      <MenuItem value="title">Title</MenuItem>
                      <MenuItem value="source">Source</MenuItem>
                      <MenuItem value="quality_score">Quality Score</MenuItem>
                      <MenuItem value="sentiment_score">Sentiment Score</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Sort Order</InputLabel>
                    <Select
                      value={filters.sortOrder || 'desc'}
                      onChange={(e) => handleFilterChange('sortOrder', e.target.value)}
                      label="Sort Order"
                    >
                      <MenuItem value="desc">Newest First</MenuItem>
                      <MenuItem value="asc">Oldest First</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          {/* Filters */}
          <Accordion
            expanded={expandedSections.filters}
            onChange={() => setExpandedSections(prev => ({ ...prev, filters: !prev.filters }))}
          >
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Filters</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={3}>
                {/* Sources */}
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>
                    Sources
                  </Typography>
                  <Paper sx={{ p: 1, maxHeight: 200, overflow: 'auto' }}>
                    {availableSources.map(source => (
                      <FormControlLabel
                        key={source}
                        control={
                          <Checkbox
                            checked={filters.sources?.includes(source) || false}
                            onChange={(e) => handleArrayFilterChange('sources', source, e.target.checked)}
                            size="small"
                          />
                        }
                        label={source}
                      />
                    ))}
                  </Paper>
                </Grid>

                {/* Categories */}
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>
                    Categories
                  </Typography>
                  <Paper sx={{ p: 1, maxHeight: 200, overflow: 'auto' }}>
                    {availableCategories.map(category => (
                      <FormControlLabel
                        key={category}
                        control={
                          <Checkbox
                            checked={filters.categories?.includes(category) || false}
                            onChange={(e) => handleArrayFilterChange('categories', category, e.target.checked)}
                            size="small"
                          />
                        }
                        label={category}
                      />
                    ))}
                  </Paper>
                </Grid>

                {/* Date Range - Simplified */}
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>
                    Date Range
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <TextField
                      label="From Date"
                      type="date"
                      size="small"
                      fullWidth
                      value={filters.dateFrom ? filters.dateFrom.toISOString().split('T')[0] : ''}
                      onChange={(e) => handleFilterChange('dateFrom', e.target.value ? new Date(e.target.value) : null)}
                      InputLabelProps={{ shrink: true }}
                    />
                    <TextField
                      label="To Date"
                      type="date"
                      size="small"
                      fullWidth
                      value={filters.dateTo ? filters.dateTo.toISOString().split('T')[0] : ''}
                      onChange={(e) => handleFilterChange('dateTo', e.target.value ? new Date(e.target.value) : null)}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Box>
                </Grid>

                {/* Processing Status */}
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>
                    Processing Status
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {['pending', 'processing', 'completed', 'error'].map(status => (
                      <Chip
                        key={status}
                        label={status}
                        clickable
                        color={filters.processingStatus?.includes(status) ? 'primary' : 'default'}
                        onClick={() => handleArrayFilterChange('processingStatus', status, !filters.processingStatus?.includes(status))}
                        size="small"
                      />
                    ))}
                  </Box>
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          {/* Advanced Options */}
          <Accordion
            expanded={expandedSections.advanced}
            onChange={() => setExpandedSections(prev => ({ ...prev, advanced: !prev.advanced }))}
          >
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Advanced Options</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={3}>
                {/* Sentiment Range */}
                <Grid item xs={12} sm={4}>
                  <Typography variant="subtitle2" gutterBottom>
                    Sentiment Range: {filters.sentimentRange?.[0]} to {filters.sentimentRange?.[1]}
                  </Typography>
                  <Slider
                    value={filters.sentimentRange || [-1, 1]}
                    onChange={(_, value) => handleFilterChange('sentimentRange', value)}
                    min={-1}
                    max={1}
                    step={0.1}
                    valueLabelDisplay="auto"
                    marks={[
                      { value: -1, label: 'Negative' },
                      { value: 0, label: 'Neutral' },
                      { value: 1, label: 'Positive' }
                    ]}
                  />
                </Grid>

                {/* Quality Range */}
                <Grid item xs={12} sm={4}>
                  <Typography variant="subtitle2" gutterBottom>
                    Quality Range: {Math.round((filters.qualityRange?.[0] || 0) * 100)}% to {Math.round((filters.qualityRange?.[1] || 1) * 100)}%
                  </Typography>
                  <Slider
                    value={filters.qualityRange || [0, 1]}
                    onChange={(_, value) => handleFilterChange('qualityRange', value)}
                    min={0}
                    max={1}
                    step={0.1}
                    valueLabelDisplay="auto"
                    valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
                  />
                </Grid>

                {/* Readability Range */}
                <Grid item xs={12} sm={4}>
                  <Typography variant="subtitle2" gutterBottom>
                    Readability Range: {Math.round((filters.readabilityRange?.[0] || 0) * 100)}% to {Math.round((filters.readabilityRange?.[1] || 1) * 100)}%
                  </Typography>
                  <Slider
                    value={filters.readabilityRange || [0, 1]}
                    onChange={(_, value) => handleFilterChange('readabilityRange', value)}
                    min={0}
                    max={1}
                    step={0.1}
                    valueLabelDisplay="auto"
                    valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
                  />
                </Grid>

                {/* Boolean Filters */}
                <Grid item xs={12}>
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={filters.hasSummary || false}
                          onChange={(e) => handleFilterChange('hasSummary', e.target.checked)}
                        />
                      }
                      label="Has Summary"
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={filters.hasAnalysis || false}
                          onChange={(e) => handleFilterChange('hasAnalysis', e.target.checked)}
                        />
                      }
                      label="Has Analysis"
                    />
                  </Box>
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          {/* Active Filters Display */}
          {activeFiltersCount > 0 && (
            <Box sx={{ mt: 2 }}>
              <Divider sx={{ mb: 2 }} />
              <Typography variant="subtitle2" gutterBottom>
                Active Filters:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {filters.query && (
                  <Chip
                    label={`Query: ${filters.query}`}
                    onDelete={() => handleFilterChange('query', '')}
                    size="small"
                  />
                )}
                {filters.sources?.map(source => (
                  <Chip
                    key={source}
                    label={`Source: ${source}`}
                    onDelete={() => handleArrayFilterChange('sources', source, false)}
                    size="small"
                  />
                ))}
                {filters.categories?.map(category => (
                  <Chip
                    key={category}
                    label={`Category: ${category}`}
                    onDelete={() => handleArrayFilterChange('categories', category, false)}
                    size="small"
                  />
                ))}
                {filters.dateFrom && (
                  <Chip
                    label={`From: ${filters.dateFrom.toLocaleDateString()}`}
                    onDelete={() => handleFilterChange('dateFrom', null)}
                    size="small"
                  />
                )}
                {filters.dateTo && (
                  <Chip
                    label={`To: ${filters.dateTo.toLocaleDateString()}`}
                    onDelete={() => handleFilterChange('dateTo', null)}
                    size="small"
                  />
                )}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>
  );
};

export default AdvancedSearch;
