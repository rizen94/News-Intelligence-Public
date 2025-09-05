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
  Slider,
  FormControlLabel,
  Switch
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';

const UserRulesManager = ({ onRefresh }) => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [priorityLevels, setPriorityLevels] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    profile_name: 'default',
    rule_type: 'keyword',
    rule_value: '',
    priority_level: 'medium',
    action: 'track',
    weight: 1.0
  });

  useEffect(() => {
    fetchRules();
    fetchPriorityLevels();
  }, []);

  const fetchRules = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/prioritization/user-rules');
      const data = await response.json();
      
      if (data.success) {
        setRules(data.data);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to fetch user rules');
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
        profile_name: rule.profile_name || 'default',
        rule_type: rule.rule_type,
        rule_value: rule.rule_value,
        priority_level: rule.priority_level || 'medium',
        action: rule.action,
        weight: rule.weight || 1.0
      });
    } else {
      setEditingRule(null);
      setFormData({
        profile_name: 'default',
        rule_type: 'keyword',
        rule_value: '',
        priority_level: 'medium',
        action: 'track',
        weight: 1.0
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingRule(null);
    setFormData({
      profile_name: 'default',
      rule_type: 'keyword',
      rule_value: '',
      priority_level: 'medium',
      action: 'track',
      weight: 1.0
    });
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async () => {
    try {
      const response = await fetch('/api/prioritization/user-rules', {
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
      setError('Failed to save user rule');
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (window.confirm('Are you sure you want to delete this rule?')) {
      try {
        const response = await fetch(`/api/prioritization/user-rules/${ruleId}`, {
          method: 'DELETE',
        });
        
        if (response.ok) {
          fetchRules();
          onRefresh();
        } else {
          setError('Failed to delete rule');
        }
      } catch (err) {
        setError('Failed to delete rule');
      }
    }
  };

  const getActionColor = (action) => {
    switch (action) {
      case 'boost':
        return 'success';
      case 'suppress':
        return 'error';
      case 'avoid':
        return 'warning';
      case 'track':
        return 'info';
      default:
        return 'default';
    }
  };

  const getRuleTypeIcon = (ruleType) => {
    switch (ruleType) {
      case 'keyword':
        return '🔍';
      case 'source':
        return '📰';
      case 'category':
        return '🏷️';
      case 'topic':
        return '📚';
      default:
        return '⚙️';
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
          User Interest Rules ({rules.length})
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          New Rule
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
                      {getRuleTypeIcon(rule.rule_type)} {rule.rule_type}
                    </Typography>
                  </Box>
                  <Chip
                    label={rule.action}
                    size="small"
                    color={getActionColor(rule.action)}
                  />
                </Box>
                
                <Typography variant="body1" sx={{ mb: 2, fontWeight: 'bold' }}>
                  {rule.rule_value}
                </Typography>
                
                <Box sx={{ mb: 2 }}>
                  <Chip
                    label={rule.priority_level}
                    size="small"
                    variant="outlined"
                    sx={{ mr: 1 }}
                  />
                  <Chip
                    label={`Weight: ${rule.weight}`}
                    size="small"
                    variant="outlined"
                  />
                </Box>
                
                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Profile: {rule.profile_name}
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" color="text.secondary">
                    ID: {rule.id}
                  </Typography>
                  
                  <Box>
                    <IconButton
                      size="small"
                      onClick={() => handleOpenDialog(rule)}
                      title="Edit Rule"
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteRule(rule.id)}
                      title="Delete Rule"
                      color="error"
                    >
                      <DeleteIcon />
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
          {editingRule ? 'Edit User Interest Rule' : 'Create New User Interest Rule'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Profile Name"
                value={formData.profile_name}
                onChange={(e) => handleInputChange('profile_name', e.target.value)}
                helperText="User profile to apply this rule to"
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
                  <MenuItem value="keyword">Keyword</MenuItem>
                  <MenuItem value="source">Source</MenuItem>
                  <MenuItem value="category">Category</MenuItem>
                  <MenuItem value="topic">Topic</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Rule Value"
                value={formData.rule_value}
                onChange={(e) => handleInputChange('rule_value', e.target.value)}
                required
                helperText={`Enter the ${formData.rule_type} value to match`}
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Priority Level</InputLabel>
                <Select
                  value={formData.priority_level}
                  label="Priority Level"
                  onChange={(e) => handleInputChange('priority_level', e.target.value)}
                >
                  {priorityLevels.map((level) => (
                    <MenuItem key={level.name} value={level.name}>
                      {level.name.charAt(0).toUpperCase() + level.name.slice(1)}
                    </MenuItem>
                  ))}
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
                  <MenuItem value="track">Track</MenuItem>
                  <MenuItem value="boost">Boost</MenuItem>
                  <MenuItem value="suppress">Suppress</MenuItem>
                  <MenuItem value="avoid">Avoid</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <Typography gutterBottom>
                Rule Weight: {formData.weight}
              </Typography>
              <Slider
                value={formData.weight}
                onChange={(e, value) => handleInputChange('weight', value)}
                min={0.1}
                max={2.0}
                step={0.1}
                marks={[
                  { value: 0.1, label: '0.1' },
                  { value: 1.0, label: '1.0' },
                  { value: 2.0, label: '2.0' }
                ]}
                valueLabelDisplay="auto"
              />
              <Typography variant="caption" color="text.secondary">
                Higher weight means stronger influence on content priority
              </Typography>
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

export default UserRulesManager;
