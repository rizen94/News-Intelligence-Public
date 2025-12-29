import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  Switch,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Stack,
  Slider,
  FormControlLabel,
  FormHelperText,
  Divider,
} from '@mui/material';
import {
  Close as CloseIcon,
  Settings as SettingsIcon,
  AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';
import apiService from '../services/apiService';
import { useDomainRoute } from '../hooks/useDomainRoute';

const StorylineAutomationDialog = ({
  open,
  onClose,
  storylineId,
  onSettingsUpdated,
}) => {
  const { domain } = useDomainRoute();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [settings, setSettings] = useState({
    automation_enabled: false,
    automation_mode: 'disabled',
    search_keywords: [],
    search_entities: [],
    search_exclude_keywords: [],
    frequency_hours: 24,
    min_relevance_score: 0.6,
    min_quality_score: 0.5,
    min_semantic_score: 0.55,
    max_articles_per_run: 20,
    date_range_days: 30,
  });

  const [keywordInput, setKeywordInput] = useState('');
  const [entityInput, setEntityInput] = useState('');
  const [excludeInput, setExcludeInput] = useState('');

  useEffect(() => {
    if (open && storylineId) {
      loadSettings();
    }
  }, [open, storylineId]);

  const loadSettings = async() => {
    try {
      setLoading(true);
      setError(null);
      // eslint-disable-next-line no-undef
      const response = await apiService.getAutomationSettings(storylineId, domain);

      if (response.success) {
        const data = response.data;
        setSettings({
          automation_enabled: data.automation_enabled || false,
          automation_mode: data.automation_mode || 'disabled',
          search_keywords: data.search_keywords || [],
          search_entities: data.search_entities || [],
          search_exclude_keywords: data.search_exclude_keywords || [],
          frequency_hours: data.frequency_hours || 24,
          ...(data.settings || {}),
          min_relevance_score: data.settings?.min_relevance_score || 0.6,
          min_quality_score: data.settings?.min_quality_score || 0.5,
          min_semantic_score: data.settings?.min_semantic_score || 0.55,
          max_articles_per_run: data.settings?.max_articles_per_run || 20,
          date_range_days: data.settings?.date_range_days || 30,
        });
      } else {
        setError(response.error || 'Failed to load settings');
      }
    } catch (err) {
      console.error('Error loading settings:', err);
      setError('Failed to load automation settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async() => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const updateData = {
        automation_enabled: settings.automation_enabled,
        automation_mode: settings.automation_mode,
        search_keywords: settings.search_keywords,
        search_entities: settings.search_entities,
        search_exclude_keywords: settings.search_exclude_keywords,
        frequency_hours: settings.frequency_hours,
        settings: {
          min_relevance_score: settings.min_relevance_score,
          min_quality_score: settings.min_quality_score,
          max_articles_per_run: settings.max_articles_per_run,
          date_range_days: settings.date_range_days,
        },
      };

      // eslint-disable-next-line no-undef
      const response = await apiService.updateAutomationSettings(storylineId, updateData, domain);

      if (response && response.success) {
        setSuccess('Automation settings updated successfully');
        if (onSettingsUpdated) {
          onSettingsUpdated();
        }
        setTimeout(() => {
          onClose();
        }, 1000);
      } else {
        const errorMsg = response?.error || response?.message || 'Failed to update settings';
        console.error('Save failed:', response);
        setError(errorMsg);
      }
    } catch (err) {
      console.error('Error saving settings:', err);
      setError(`Failed to save automation settings: ${err.message || err.toString()}`);
    } finally {
      setSaving(false);
    }
  };

  const addKeyword = () => {
    if (keywordInput.trim()) {
      setSettings({
        ...settings,
        search_keywords: [...settings.search_keywords, keywordInput.trim()],
      });
      setKeywordInput('');
    }
  };

  const removeKeyword = (keyword) => {
    setSettings({
      ...settings,
      search_keywords: settings.search_keywords.filter(k => k !== keyword),
    });
  };

  const addEntity = () => {
    if (entityInput.trim()) {
      setSettings({
        ...settings,
        search_entities: [...settings.search_entities, entityInput.trim()],
      });
      setEntityInput('');
    }
  };

  const removeEntity = (entity) => {
    setSettings({
      ...settings,
      search_entities: settings.search_entities.filter(e => e !== entity),
    });
  };

  const addExcludeKeyword = () => {
    if (excludeInput.trim()) {
      setSettings({
        ...settings,
        search_exclude_keywords: [...settings.search_exclude_keywords, excludeInput.trim()],
      });
      setExcludeInput('');
    }
  };

  const removeExcludeKeyword = (keyword) => {
    setSettings({
      ...settings,
      search_exclude_keywords: settings.search_exclude_keywords.filter(k => k !== keyword),
    });
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth='md'
      fullWidth
      PaperProps={{
        sx: { minHeight: '600px' },
      }}
    >
      <DialogTitle>
        <Box display='flex' justifyContent='space-between' alignItems='center'>
          <Box display='flex' alignItems='center' gap={1}>
            <AutoAwesomeIcon color='primary' />
            <Typography variant='h6'>Automation Settings</Typography>
          </Box>
          <IconButton onClick={onClose} size='small'>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {loading && (
          <Box display='flex' justifyContent='center' p={3}>
            <CircularProgress />
          </Box>
        )}

        {!loading && (
          <>
            {error && (
              <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {success && (
              <Alert severity='success' sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
                {success}
              </Alert>
            )}

            {settings.automation_enabled && settings.automation_mode === 'disabled' && (
              <Alert severity='warning' sx={{ mb: 2 }}>
                Automation is enabled but mode is set to 'disabled'. Please select a different mode.
              </Alert>
            )}

            {/* Enable Automation */}
            <Box sx={{ mb: 3 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.automation_enabled}
                    onChange={(e) =>
                      setSettings({ ...settings, automation_enabled: e.target.checked })
                    }
                  />
                }
                label={
                  <Box>
                    <Typography variant='subtitle1'>Enable Automation</Typography>
                    <Typography variant='caption' color='text.secondary'>
                      Automatically discover and suggest relevant articles
                    </Typography>
                  </Box>
                }
              />
            </Box>

            {settings.automation_enabled && (
              <>
                <Divider sx={{ my: 2 }} />

                {/* Automation Mode */}
                <FormControl fullWidth sx={{ mb: 3 }}>
                  <InputLabel>Automation Mode</InputLabel>
                  <Select
                    value={settings.automation_mode}
                    label='Automation Mode'
                    onChange={(e) => {
                      const newMode = e.target.value;
                      setSettings({ ...settings, automation_mode: newMode });
                      // Auto-disable if mode is 'disabled'
                      if (newMode === 'disabled') {
                        setSettings((prev) => ({ ...prev, automation_enabled: false }));
                      }
                    }}
                  >
                    <MenuItem value='disabled'>Disabled</MenuItem>
                    <MenuItem value='manual'>Manual (Suggestions Only)</MenuItem>
                    <MenuItem value='auto_approve'>Auto-Approve (High Confidence)</MenuItem>
                    <MenuItem value='review_queue'>Review Queue (Full Control)</MenuItem>
                  </Select>
                  <FormHelperText>
                    {settings.automation_mode === 'disabled' &&
                      'Automation is disabled. Articles must be added manually.'}
                    {settings.automation_mode === 'manual' &&
                      'Articles are suggested for review before adding'}
                    {settings.automation_mode === 'auto_approve' &&
                      'High-confidence articles are auto-added, others require review'}
                    {settings.automation_mode === 'review_queue' &&
                      'All articles go to review queue for manual approval'}
                  </FormHelperText>
                </FormControl>

                {/* Search Keywords */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant='subtitle2' gutterBottom>
                    Search Keywords
                  </Typography>
                  <Box display='flex' gap={1} mb={1}>
                    <TextField
                      fullWidth
                      size='small'
                      placeholder='Add keyword (e.g., "Ukraine", "conflict")'
                      value={keywordInput}
                      onChange={(e) => setKeywordInput(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addKeyword();
                        }
                      }}
                    />
                    <Button variant='outlined' onClick={addKeyword}>
                      Add
                    </Button>
                  </Box>
                  <Stack direction='row' spacing={1} flexWrap='wrap' gap={1}>
                    {settings.search_keywords.map((keyword) => (
                      <Chip
                        key={keyword}
                        label={keyword}
                        onDelete={() => removeKeyword(keyword)}
                        size='small'
                      />
                    ))}
                  </Stack>
                </Box>

                {/* Search Entities */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant='subtitle2' gutterBottom>
                    Search Entities (People, Organizations, Locations)
                  </Typography>
                  <Box display='flex' gap={1} mb={1}>
                    <TextField
                      fullWidth
                      size='small'
                      placeholder='Add entity (e.g., "Volodymyr Zelensky", "Russia")'
                      value={entityInput}
                      onChange={(e) => setEntityInput(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addEntity();
                        }
                      }}
                    />
                    <Button variant='outlined' onClick={addEntity}>
                      Add
                    </Button>
                  </Box>
                  <Stack direction='row' spacing={1} flexWrap='wrap' gap={1}>
                    {settings.search_entities.map((entity) => (
                      <Chip
                        key={entity}
                        label={entity}
                        onDelete={() => removeEntity(entity)}
                        size='small'
                        color='primary'
                      />
                    ))}
                  </Stack>
                </Box>

                {/* Exclude Keywords */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant='subtitle2' gutterBottom>
                    Exclude Keywords
                  </Typography>
                  <Box display='flex' gap={1} mb={1}>
                    <TextField
                      fullWidth
                      size='small'
                      placeholder='Add keyword to exclude (e.g., "advertisement")'
                      value={excludeInput}
                      onChange={(e) => setExcludeInput(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addExcludeKeyword();
                        }
                      }}
                    />
                    <Button variant='outlined' onClick={addExcludeKeyword}>
                      Add
                    </Button>
                  </Box>
                  <Stack direction='row' spacing={1} flexWrap='wrap' gap={1}>
                    {settings.search_exclude_keywords.map((keyword) => (
                      <Chip
                        key={keyword}
                        label={keyword}
                        onDelete={() => removeExcludeKeyword(keyword)}
                        size='small'
                        color='error'
                      />
                    ))}
                  </Stack>
                </Box>

                <Divider sx={{ my: 2 }} />

                {/* Thresholds */}
                <Typography variant='subtitle1' gutterBottom>
                  Thresholds & Limits
                </Typography>

                <Box sx={{ mb: 2 }}>
                  <Typography gutterBottom>
                    Minimum Combined Score: {settings.min_relevance_score.toFixed(2)}
                  </Typography>
                  <Typography variant='caption' color='text.secondary' sx={{ mb: 1, display: 'block' }}>
                    Combined score = (Relevance × 0.4) + (Quality × 0.3) + (Semantic × 0.3)
                  </Typography>
                  <Slider
                    value={settings.min_relevance_score}
                    onChange={(e, newValue) =>
                      setSettings({ ...settings, min_relevance_score: newValue })
                    }
                    min={0}
                    max={1}
                    step={0.05}
                    marks
                  />
                  <FormHelperText>
                    Articles must meet this combined score threshold to be suggested (default: 0.60)
                  </FormHelperText>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography gutterBottom>
                    Minimum Quality Score: {settings.min_quality_score.toFixed(2)}
                  </Typography>
                  <Slider
                    value={settings.min_quality_score}
                    onChange={(e, newValue) =>
                      setSettings({ ...settings, min_quality_score: newValue })
                    }
                    min={0}
                    max={1}
                    step={0.05}
                    marks
                  />
                </Box>

                <Box sx={{ mb: 2 }}>
                  <TextField
                    fullWidth
                    type='number'
                    label='Max Articles Per Run'
                    value={settings.max_articles_per_run}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val) && val > 0 && val <= 100) {
                        setSettings({
                          ...settings,
                          max_articles_per_run: val,
                        });
                      }
                    }}
                    inputProps={{ min: 1, max: 100 }}
                    helperText='Maximum number of articles to discover per automation run (1-100)'
                  />
                </Box>

                <Box sx={{ mb: 2 }}>
                  <TextField
                    fullWidth
                    type='number'
                    label='Date Range (days)'
                    value={settings.date_range_days}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val) && val > 0 && val <= 365) {
                        setSettings({
                          ...settings,
                          date_range_days: val,
                        });
                      }
                    }}
                    inputProps={{ min: 1, max: 365 }}
                    helperText='How far back to search for articles (1-365 days)'
                  />
                </Box>

                <Box sx={{ mb: 2 }}>
                  <TextField
                    fullWidth
                    type='number'
                    label='Frequency (hours)'
                    value={settings.frequency_hours}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val) && val > 0 && val <= 168) {
                        setSettings({
                          ...settings,
                          frequency_hours: val,
                        });
                      }
                    }}
                    inputProps={{ min: 1, max: 168 }}
                    helperText='How often to automatically run discovery (1-168 hours, 168 = weekly)'
                  />
                </Box>
              </>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleSave}
          variant='contained'
          disabled={saving || loading}
        >
          {saving ? <CircularProgress size={20} /> : 'Save Settings'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default StorylineAutomationDialog;

