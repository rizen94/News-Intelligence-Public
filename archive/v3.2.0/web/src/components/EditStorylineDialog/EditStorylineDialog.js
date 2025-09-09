import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Chip,
  IconButton,
  Grid,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useNotifications } from '../Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';

const EditStorylineDialog = ({ open, onClose, storyline, onSuccess }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    priority_level: 5,
    keywords: [],
    entities: [],
    geographic_regions: [],
    quality_threshold: 0.7,
    max_articles_per_day: 100,
    auto_enhance: true,
    is_active: true
  });
  const [newKeyword, setNewKeyword] = useState('');
  const [newEntity, setNewEntity] = useState('');
  const [newRegion, setNewRegion] = useState('');
  const [loading, setLoading] = useState(false);
  const { showSuccess, showError, showLoading } = useNotifications();

  useEffect(() => {
    if (open && storyline) {
      setFormData({
        name: storyline.name || '',
        description: storyline.description || '',
        priority_level: storyline.priority_level || 5,
        keywords: storyline.keywords || [],
        entities: storyline.entities || [],
        geographic_regions: storyline.geographic_regions || [],
        quality_threshold: storyline.quality_threshold || 0.7,
        max_articles_per_day: storyline.max_articles_per_day || 100,
        auto_enhance: storyline.auto_enhance !== false,
        is_active: storyline.is_active !== false
      });
    }
  }, [open, storyline]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleAddKeyword = () => {
    if (newKeyword.trim() && !formData.keywords.includes(newKeyword.trim())) {
      setFormData(prev => ({
        ...prev,
        keywords: [...prev.keywords, newKeyword.trim()]
      }));
      setNewKeyword('');
    }
  };

  const handleRemoveKeyword = (keyword) => {
    setFormData(prev => ({
      ...prev,
      keywords: prev.keywords.filter(k => k !== keyword)
    }));
  };

  const handleAddEntity = () => {
    if (newEntity.trim() && !formData.entities.includes(newEntity.trim())) {
      setFormData(prev => ({
        ...prev,
        entities: [...prev.entities, newEntity.trim()]
      }));
      setNewEntity('');
    }
  };

  const handleRemoveEntity = (entity) => {
    setFormData(prev => ({
      ...prev,
      entities: prev.entities.filter(e => e !== entity)
    }));
  };

  const handleAddRegion = () => {
    if (newRegion.trim() && !formData.geographic_regions.includes(newRegion.trim())) {
      setFormData(prev => ({
        ...prev,
        geographic_regions: [...prev.geographic_regions, newRegion.trim()]
      }));
      setNewRegion('');
    }
  };

  const handleRemoveRegion = (region) => {
    setFormData(prev => ({
      ...prev,
      geographic_regions: prev.geographic_regions.filter(r => r !== region)
    }));
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      showLoading('Updating storyline...');

      const response = await newsSystemService.updateStoryline(storyline.story_id, formData);
      
      if (response.success) {
        showSuccess('Storyline updated successfully');
        onSuccess && onSuccess();
        onClose();
      } else {
        throw new Error(response.message || 'Failed to update storyline');
      }
    } catch (error) {
      console.error('Error updating storyline:', error);
      showError('Failed to update storyline');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setNewKeyword('');
    setNewEntity('');
    setNewRegion('');
    onClose();
  };

  if (!storyline) return null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Edit Storyline: {storyline.name}
      </DialogTitle>
      
      <DialogContent>
        <Grid container spacing={3} sx={{ mt: 1 }}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Basic Information
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Name"
              value={formData.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              required
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Priority Level</InputLabel>
              <Select
                value={formData.priority_level}
                onChange={(e) => handleInputChange('priority_level', e.target.value)}
                label="Priority Level"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(level => (
                  <MenuItem key={level} value={level}>
                    {level} {level >= 8 ? '(High)' : level >= 5 ? '(Medium)' : '(Low)'}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description"
              multiline
              rows={3}
              value={formData.description}
              onChange={(e) => handleInputChange('description', e.target.value)}
              required
            />
          </Grid>

          {/* Keywords */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Keywords
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                placeholder="Add keyword..."
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
                sx={{ flexGrow: 1 }}
              />
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleAddKeyword}
                disabled={!newKeyword.trim()}
              >
                Add
              </Button>
            </Box>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {formData.keywords.map((keyword, index) => (
                <Chip
                  key={index}
                  label={keyword}
                  onDelete={() => handleRemoveKeyword(keyword)}
                  color="primary"
                  variant="outlined"
                />
              ))}
            </Box>
          </Grid>

          {/* Entities */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Entities
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                placeholder="Add entity..."
                value={newEntity}
                onChange={(e) => setNewEntity(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddEntity()}
                sx={{ flexGrow: 1 }}
              />
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleAddEntity}
                disabled={!newEntity.trim()}
              >
                Add
              </Button>
            </Box>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {formData.entities.map((entity, index) => (
                <Chip
                  key={index}
                  label={entity}
                  onDelete={() => handleRemoveEntity(entity)}
                  color="secondary"
                  variant="outlined"
                />
              ))}
            </Box>
          </Grid>

          {/* Geographic Regions */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Geographic Regions
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                placeholder="Add region..."
                value={newRegion}
                onChange={(e) => setNewRegion(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddRegion()}
                sx={{ flexGrow: 1 }}
              />
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleAddRegion}
                disabled={!newRegion.trim()}
              >
                Add
              </Button>
            </Box>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {formData.geographic_regions.map((region, index) => (
                <Chip
                  key={index}
                  label={region}
                  onDelete={() => handleRemoveRegion(region)}
                  color="info"
                  variant="outlined"
                />
              ))}
            </Box>
          </Grid>

          {/* Settings */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Settings
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Quality Threshold"
              type="number"
              inputProps={{ min: 0, max: 1, step: 0.1 }}
              value={formData.quality_threshold}
              onChange={(e) => handleInputChange('quality_threshold', parseFloat(e.target.value))}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Max Articles Per Day"
              type="number"
              inputProps={{ min: 1, max: 1000 }}
              value={formData.max_articles_per_day}
              onChange={(e) => handleInputChange('max_articles_per_day', parseInt(e.target.value))}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.auto_enhance}
                  onChange={(e) => handleInputChange('auto_enhance', e.target.checked)}
                />
              }
              label="Auto-enhance with RAG"
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={(e) => handleInputChange('is_active', e.target.checked)}
                />
              }
              label="Active"
            />
          </Grid>
        </Grid>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained"
          disabled={loading || !formData.name.trim() || !formData.description.trim()}
        >
          {loading ? 'Updating...' : 'Update Storyline'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditStorylineDialog;
