import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  FilterList as FilterIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';

const CollectionRulesManager = ({ onRefresh }) => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [priorityLevels, setPriorityLevels] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    rule_name: '',
    rule_type: 'content_filter',
    rule_conditions: {},
    priority_level_id: null,
    action: 'collect'
  });

  useEffect(() => {
    fetchRules();
    fetchPriorityLevels();
  }, []);

  const fetchRules = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/prioritization/collection-rules');
      const data = await response.json();
      
      if (data.success) {
        setRules(data.data);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to fetch collection rules');
    } finally {
      setLoading(false);
    }
  };

  const fetchPriorityLevels = async () => {
    try {
      const response = await fetch('/api/prioritization/priority-levels');
      const data = await response.json();
      
      if (data.success) {
        setPriorityLevels(data.data);
      }
    } catch (err) {
      console.error('Failed to fetch priority levels:', err);
    }
  };

  const handleOpenDialog = (rule = null) => {
    if (rule) {
      setEditingRule(rule);
      setFormData({
        rule_name: rule.rule_name,
        rule_type: rule.rule_type,
        rule_conditions: rule.rule_conditions || {},
        priority_level_id: rule.priority_level_id,
        action: rule.action
      });
    } else {
      setEditingRule(null);
      setFormData({
        rule_name: '',
        rule_type: 'content_filter',
        rule_conditions: {},
        priority_level_id: null,
        action: 'collect'
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingRule(null);
    setFormData({
      rule_name: '',
      rule_type: 'content_filter',
      rule_conditions: {},
      priority_level_id: null,
      action: 'collect'
    });
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleConditionsChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      rule_conditions: {
        ...prev.rule_conditions,
        [field]: value
      }
    }));
  };

  const handleSubmit = async () => {
    try {
      const response = await fetch('/api/prioritization/collection-rules', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });
      
      const data = await response.json();
      
      if (data.success) {
        handleCloseDialog();
        fetchRules();
        onRefresh();
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to save collection rule');
    }
  };

  const handleToggleRule = async (ruleId, currentStatus) => {
    try {
      // Note: We'll need to add an endpoint to toggle rule status
      // For now, we'll just show a message
      alert('Toggle functionality will be implemented with additional API endpoints');
    } catch (err) {
      setError('Failed to toggle rule status');
    }
  };

  const getActionColor = (action) => {
    switch (action) {
      case 'collect':
        return 'success';
      case 'avoid':
        return 'error';
      case 'boost':
        return 'info';
      case 'suppress':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getRuleTypeIcon = (ruleType) => {
    switch (ruleType) {
      case 'content_filter':
        return '🔍';
      case 'source_filter':
        return '📰';
      case 'category_filter':
        return '🏷️';
      case 'priority_filter':
        return '⭐';
      default:
        return '⚙️';
    }
  };

  const renderConditionsForm = () => {
    switch (formData.rule_type) {
      case 'content_filter':
        return (
          <TextField
            fullWidth
            label="Keywords (comma-separated)"
            value={formData.rule_conditions.keywords?.join(', ') || ''}
            onChange={(e) => handleConditionsChange('keywords', e.target.value.split(',').map(k => k.trim()).filter(k => k))}
            helperText="Enter keywords to filter content by"
          />
        );
      case 'source_filter':
        return (
          <TextField
            fullWidth
            label="Sources (comma-separated)"
            value={formData.rule_conditions.sources?.join(', ') || ''}
            onChange={(e) => handleConditionsChange('sources', e.target.value.split(',').map(k => k.trim()).filter(k => k))}
            helperText="Enter source names to filter by"
          />
        );
      case 'category_filter':
        return (
          <TextField
            fullWidth
            label="Categories (comma-separated)"
            value={formData.rule_conditions.categories?.join(', ') || ''}
            onChange={(e) => handleConditionsChange('categories', e.target.value.split(',').map(k => k.trim()).filter(k => k))}
            helperText="Enter categories to filter by"
          />
        );
      default:
        return (
          <TextField
            fullWidth
            label="Conditions (JSON)"
            value={JSON.stringify(formData.rule_conditions, null, 2)}
            onChange={(e) => {
              try {
                handleConditionsChange('custom', JSON.parse(e.target.value));
              } catch (err) {
                // Invalid JSON, ignore
              }
            }}
            multiline
            rows={3}
            helperText="Enter JSON conditions for custom rule types"
          />
        );
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">
          Collection Rules ({rules.length})
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          New Collection Rule
        </Button>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Rules List */}
      <Grid container spacing={3}>
        {rules.map((rule) => (
          <Grid item xs={12} md={6} key={rule.id}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h6">
                      {getRuleTypeIcon(rule.rule_type)} {rule.rule_name}
                    </Typography>
                  </Box>
                  <Chip
                    label={rule.action}
                    size="small"
                    color={getActionColor(rule.action)}
                  />
                </Box>
                
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Type: {rule.rule_type.replace('_', ' ')}
                </Typography>
                
                {rule.rule_conditions && Object.keys(rule.rule_conditions).length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                      Conditions:
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {Object.entries(rule.rule_conditions).map(([key, value]) => (
                        <Chip
                          key={key}
                          label={`${key}: ${Array.isArray(value) ? value.join(', ') : value}`}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                )}
                
                <Box sx={{ mb: 2 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={rule.is_active}
                        onChange={() => handleToggleRule(rule.id, rule.is_active)}
                        size="small"
                      />
                    }
                    label="Active"
                  />
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" color="text.secondary">
                    Created: {new Date(rule.created_at).toLocaleDateString()}
                  </Typography>
                  
                  <Box>
                    <IconButton
                      size="small"
                      onClick={() => handleOpenDialog(rule)}
                      title="Edit Rule"
                    >
                      <EditIcon />
                    </IconButton>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingRule ? 'Edit Collection Rule' : 'Create New Collection Rule'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Rule Name"
                value={formData.rule_name}
                onChange={(e) => handleInputChange('rule_name', e.target.value)}
                required
                helperText="Descriptive name for this collection rule"
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Rule Type</InputLabel>
                <Select
                  value={formData.rule_type}
                  label="Rule Type"
                  onChange={(e) => handleInputChange('rule_type', e.target.value)}
                >
                  <MenuItem value="content_filter">Content Filter</MenuItem>
                  <MenuItem value="source_filter">Source Filter</MenuItem>
                  <MenuItem value="category_filter">Category Filter</MenuItem>
                  <MenuItem value="priority_filter">Priority Filter</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Action</InputLabel>
                <Select
                  value={formData.action}
                  label="Action"
                  onChange={(e) => handleInputChange('action', e.target.value)}
                >
                  <MenuItem value="collect">Collect</MenuItem>
                  <MenuItem value="avoid">Avoid</MenuItem>
                  <MenuItem value="boost">Boost</MenuItem>
                  <MenuItem value="suppress">Suppress</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              {renderConditionsForm()}
            </Grid>
            
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Priority Level</InputLabel>
                <Select
                  value={formData.priority_level_id || ''}
                  label="Priority Level"
                  onChange={(e) => handleInputChange('priority_level_id', e.target.value)}
                >
                  <MenuItem value="">None</MenuItem>
                  {priorityLevels.map((level) => (
                    <MenuItem key={level.id} value={level.id}>
                      {level.name.charAt(0).toUpperCase() + level.name.slice(1)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingRule ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CollectionRulesManager;
