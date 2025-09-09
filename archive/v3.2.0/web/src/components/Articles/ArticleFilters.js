// News Intelligence System v3.1.0 - Article Filters Component
// Advanced filtering and sorting for articles

import React, { useState } from 'react';
import {
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
  Typography,
  Slider,
  FormControlLabel,
  Switch,
  Grid
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  FilterList as FilterIcon,
  Clear as ClearIcon,
  Search as SearchIcon
} from '@mui/icons-material';

const ArticleFilters = ({ 
  filters, 
  onFiltersChange, 
  onSearch, 
  onClear,
  loading = false 
}) => {
  const [localFilters, setLocalFilters] = useState(filters);

  const handleFilterChange = (key, value) => {
    const newFilters = { ...localFilters, [key]: value };
    setLocalFilters(newFilters);
    onFiltersChange(newFilters);
  };

  const handleSearch = () => {
    onSearch(localFilters);
  };

  const handleClear = () => {
    const clearedFilters = {
      search: '',
      category: '',
      source: '',
      dateFrom: '',
      dateTo: '',
      sentiment: '',
      sortBy: 'published_at',
      sortOrder: 'desc',
      minQuality: 0,
      maxQuality: 100,
      hasSummary: false
    };
    setLocalFilters(clearedFilters);
    onClear(clearedFilters);
  };

  const getActiveFiltersCount = () => {
    let count = 0;
    if (localFilters.search) count++;
    if (localFilters.category) count++;
    if (localFilters.source) count++;
    if (localFilters.dateFrom) count++;
    if (localFilters.dateTo) count++;
    if (localFilters.sentiment) count++;
    if (localFilters.minQuality > 0 || localFilters.maxQuality < 100) count++;
    if (localFilters.hasSummary) count++;
    return count;
  };

  return (
    <Box sx={{ mb: 3 }}>
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FilterIcon />
            <Typography variant="h6">Filters & Search</Typography>
            {getActiveFiltersCount() > 0 && (
              <Chip 
                label={`${getActiveFiltersCount()} active`} 
                size="small" 
                color="primary" 
              />
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            {/* Search */}
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Search articles"
                value={localFilters.search || ''}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                InputProps={{
                  startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                }}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
            </Grid>

            {/* Category */}
            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Category</InputLabel>
                <Select
                  value={localFilters.category || ''}
                  onChange={(e) => handleFilterChange('category', e.target.value)}
                  label="Category"
                >
                  <MenuItem value="">All Categories</MenuItem>
                  <MenuItem value="technology">Technology</MenuItem>
                  <MenuItem value="politics">Politics</MenuItem>
                  <MenuItem value="business">Business</MenuItem>
                  <MenuItem value="science">Science</MenuItem>
                  <MenuItem value="health">Health</MenuItem>
                  <MenuItem value="sports">Sports</MenuItem>
                  <MenuItem value="entertainment">Entertainment</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Source */}
            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Source</InputLabel>
                <Select
                  value={localFilters.source || ''}
                  onChange={(e) => handleFilterChange('source', e.target.value)}
                  label="Source"
                >
                  <MenuItem value="">All Sources</MenuItem>
                  <MenuItem value="BBC News">BBC News</MenuItem>
                  <MenuItem value="Reuters">Reuters</MenuItem>
                  <MenuItem value="TechCrunch">TechCrunch</MenuItem>
                  <MenuItem value="CNN">CNN</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Sentiment */}
            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Sentiment</InputLabel>
                <Select
                  value={localFilters.sentiment || ''}
                  onChange={(e) => handleFilterChange('sentiment', e.target.value)}
                  label="Sentiment"
                >
                  <MenuItem value="">All Sentiments</MenuItem>
                  <MenuItem value="positive">Positive</MenuItem>
                  <MenuItem value="negative">Negative</MenuItem>
                  <MenuItem value="neutral">Neutral</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Sort */}
            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={localFilters.sortBy || 'published_at'}
                  onChange={(e) => handleFilterChange('sortBy', e.target.value)}
                  label="Sort By"
                >
                  <MenuItem value="published_at">Date</MenuItem>
                  <MenuItem value="title">Title</MenuItem>
                  <MenuItem value="source">Source</MenuItem>
                  <MenuItem value="sentiment_score">Sentiment</MenuItem>
                  <MenuItem value="quality_score">Quality</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Date Range */}
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <TextField
                  label="From Date"
                  type="date"
                  value={localFilters.dateFrom || ''}
                  onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ flex: 1 }}
                />
                <TextField
                  label="To Date"
                  type="date"
                  value={localFilters.dateTo || ''}
                  onChange={(e) => handleFilterChange('dateTo', e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ flex: 1 }}
                />
              </Box>
            </Grid>

            {/* Quality Score */}
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="body2" gutterBottom>
                  Quality Score: {localFilters.minQuality} - {localFilters.maxQuality}
                </Typography>
                <Slider
                  value={[localFilters.minQuality || 0, localFilters.maxQuality || 100]}
                  onChange={(e, newValue) => {
                    handleFilterChange('minQuality', newValue[0]);
                    handleFilterChange('maxQuality', newValue[1]);
                  }}
                  valueLabelDisplay="auto"
                  min={0}
                  max={100}
                  step={5}
                />
              </Box>
            </Grid>

            {/* Additional Options */}
            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={localFilters.hasSummary || false}
                      onChange={(e) => handleFilterChange('hasSummary', e.target.checked)}
                    />
                  }
                  label="Has Summary"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={localFilters.sortOrder === 'asc'}
                      onChange={(e) => handleFilterChange('sortOrder', e.target.checked ? 'asc' : 'desc')}
                    />
                  }
                  label="Ascending Order"
                />
              </Box>
            </Grid>

            {/* Action Buttons */}
            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                <Button
                  variant="outlined"
                  startIcon={<ClearIcon />}
                  onClick={handleClear}
                >
                  Clear All
                </Button>
                <Button
                  variant="contained"
                  startIcon={<SearchIcon />}
                  onClick={handleSearch}
                  disabled={loading}
                >
                  Apply Filters
                </Button>
              </Box>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default ArticleFilters;

