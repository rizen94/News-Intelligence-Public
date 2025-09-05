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
  RadioGroup,
  FormControlLabel,
  Radio,
  Box,
  Typography,
  Chip,
  Divider,
} from '@mui/material';
import {
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { useNotifications } from '../Notifications/NotificationSystem';
import newsSystemService from '../../services/newsSystemService';

const AddToStorylineDialog = ({ open, onClose, article, onSuccess }) => {
  const [storylines, setStorylines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedOption, setSelectedOption] = useState('existing');
  const [selectedStorylineId, setSelectedStorylineId] = useState('');
  const [newStoryline, setNewStoryline] = useState({
    title: '',
    description: '',
    category: '',
    priority: 'medium'
  });
  const [relevanceScore, setRelevanceScore] = useState(0.8);
  const { showSuccess, showError, showLoading } = useNotifications();

  useEffect(() => {
    if (open && article) {
      fetchStorylines();
    }
  }, [open, article]);

  const fetchStorylines = async () => {
    try {
      setLoading(true);
      const response = await newsSystemService.getActiveStories();
      
      if (response.success) {
        setStorylines(response.data || []);
      } else {
        throw new Error(response.message || 'Failed to fetch storylines');
      }
    } catch (error) {
      console.error('Error fetching storylines:', error);
      showError('Failed to load storylines');
    } finally {
      setLoading(false);
    }
  };

  const handleAddToExistingStoryline = async () => {
    try {
      showLoading('Adding article to storyline...');
      
      const response = await newsSystemService.addArticleToStoryline(selectedStorylineId, article.id, {
        relevance_score: relevanceScore,
        added_at: new Date().toISOString()
      });
      
      if (response.success) {
        showSuccess('Article added to storyline successfully');
        onSuccess && onSuccess();
        onClose();
      } else {
        throw new Error(response.message || 'Failed to add article to storyline');
      }
    } catch (error) {
      console.error('Error adding article to storyline:', error);
      showError('Failed to add article to storyline');
    }
  };

  const handleCreateNewStoryline = async () => {
    try {
      showLoading('Creating new storyline...');
      
      const storylineData = {
        ...newStoryline,
        targets: extractKeywordsFromArticle(article),
        quality_filters: ['reliable_sources', 'verified_information']
      };
      
      const response = await newsSystemService.createStoryExpectation(storylineData);
      
      if (response.success) {
        // Now add the article to the new storyline
        const addResponse = await newsSystemService.addArticleToStoryline(response.data.id, article.id, {
          relevance_score: relevanceScore,
          added_at: new Date().toISOString()
        });
        
        if (addResponse.success) {
          showSuccess('New storyline created and article added successfully');
          onSuccess && onSuccess();
          onClose();
        } else {
          throw new Error('Failed to add article to new storyline');
        }
      } else {
        throw new Error(response.message || 'Failed to create storyline');
      }
    } catch (error) {
      console.error('Error creating storyline:', error);
      showError('Failed to create storyline');
    }
  };

  const extractKeywordsFromArticle = (article) => {
    // Extract keywords from article title, summary, and topics
    const keywords = [];
    
    if (article.title) {
      keywords.push(...article.title.toLowerCase().split(' ').filter(word => word.length > 3));
    }
    
    if (article.topics_extracted) {
      keywords.push(...article.topics_extracted);
    }
    
    if (article.entities_extracted) {
      keywords.push(...article.entities_extracted);
    }
    
    // Remove duplicates and return top 10
    return [...new Set(keywords)].slice(0, 10);
  };

  const handleSubmit = () => {
    if (selectedOption === 'existing') {
      if (!selectedStorylineId) {
        showError('Please select a storyline');
        return;
      }
      handleAddToExistingStoryline();
    } else {
      if (!newStoryline.title || !newStoryline.description) {
        showError('Please fill in all required fields');
        return;
      }
      handleCreateNewStoryline();
    }
  };

  const handleClose = () => {
    setSelectedOption('existing');
    setSelectedStorylineId('');
    setNewStoryline({
      title: '',
      description: '',
      category: '',
      priority: 'medium'
    });
    setRelevanceScore(0.8);
    onClose();
  };

  if (!article) return null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TimelineIcon />
          Add Article to Storyline
        </Box>
      </DialogTitle>
      
      <DialogContent>
        {/* Article Preview */}
        <Box sx={{ mb: 3, p: 2, backgroundColor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="h6" gutterBottom>
            {article.title}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {article.source} • {new Date(article.published_date).toLocaleDateString()}
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {article.summary || article.content?.substring(0, 200) + '...'}
          </Typography>
          {article.topics_extracted && article.topics_extracted.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {(article.topics_extracted || []).slice(0, 5).map((topic, index) => (
                <Chip key={index} label={topic} size="small" variant="outlined" />
              ))}
            </Box>
          )}
        </Box>

        <Divider sx={{ mb: 3 }} />

        {/* Add to Existing or Create New */}
        <FormControl component="fieldset" sx={{ mb: 3 }}>
          <RadioGroup
            value={selectedOption}
            onChange={(e) => setSelectedOption(e.target.value)}
          >
            <FormControlLabel 
              value="existing" 
              control={<Radio />} 
              label="Add to existing storyline" 
            />
            <FormControlLabel 
              value="new" 
              control={<Radio />} 
              label="Create new storyline" 
            />
          </RadioGroup>
        </FormControl>

        {/* Existing Storylines */}
        {selectedOption === 'existing' && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select Storyline
            </Typography>
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Storyline</InputLabel>
              <Select
                value={selectedStorylineId}
                onChange={(e) => setSelectedStorylineId(e.target.value)}
                label="Storyline"
              >
                {(storylines || []).map((storyline) => (
                  <MenuItem key={storyline.story_id} value={storyline.story_id}>
                    <Box>
                      <Typography variant="subtitle1">
                        {storyline.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {storyline.description?.substring(0, 50)}...
                      </Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        )}

        {/* Create New Storyline */}
        {selectedOption === 'new' && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Create New Storyline
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                fullWidth
                label="Title"
                value={newStoryline.title}
                onChange={(e) => setNewStoryline({...newStoryline, title: e.target.value})}
                placeholder="e.g., Ukraine-Russia Conflict"
              />
              <TextField
                fullWidth
                label="Description"
                multiline
                rows={3}
                value={newStoryline.description}
                onChange={(e) => setNewStoryline({...newStoryline, description: e.target.value})}
                placeholder="Describe what this storyline will track..."
              />
              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControl sx={{ minWidth: 120 }}>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={newStoryline.category}
                    onChange={(e) => setNewStoryline({...newStoryline, category: e.target.value})}
                    label="Category"
                  >
                    <MenuItem value="Global Events">Global Events</MenuItem>
                    <MenuItem value="Business">Business</MenuItem>
                    <MenuItem value="Politics">Politics</MenuItem>
                    <MenuItem value="Technology">Technology</MenuItem>
                  </Select>
                </FormControl>
                <FormControl sx={{ minWidth: 120 }}>
                  <InputLabel>Priority</InputLabel>
                  <Select
                    value={newStoryline.priority}
                    onChange={(e) => setNewStoryline({...newStoryline, priority: e.target.value})}
                    label="Priority"
                  >
                    <MenuItem value="low">Low</MenuItem>
                    <MenuItem value="medium">Medium</MenuItem>
                    <MenuItem value="high">High</MenuItem>
                  </Select>
                </FormControl>
              </Box>
            </Box>
          </Box>
        )}

        {/* Relevance Score */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Relevance Score
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            How relevant is this article to the storyline? (0.0 - 1.0)
          </Typography>
          <TextField
            type="number"
            inputProps={{ min: 0, max: 1, step: 0.1 }}
            value={relevanceScore}
            onChange={(e) => setRelevanceScore(parseFloat(e.target.value))}
            sx={{ width: 120 }}
          />
        </Box>

        {/* Extracted Keywords Preview */}
        {extractKeywordsFromArticle(article).length > 0 && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="h6" gutterBottom>
              Extracted Keywords
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              These keywords will be used to find related articles:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {(extractKeywordsFromArticle(article) || []).map((keyword, index) => (
                <Chip key={index} label={keyword} size="small" variant="outlined" />
              ))}
            </Box>
          </Box>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained"
          disabled={loading}
        >
          {selectedOption === 'existing' ? 'Add to Storyline' : 'Create & Add'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AddToStorylineDialog;
