import { useState, useEffect } from 'react';
import {
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import { apiService } from '../services/apiService';

const StorylineManagementTest = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [storylines, setStorylines] = useState([]);

  const loadStorylines = async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getStorylines();
      if (response.success) {
        setStorylines(response.data.storylines || []);
        setSuccess(
          `Loaded ${response.data.storylines?.length || 0} storylines`,
        );
      } else {
        setError('Failed to load storylines');
      }
    } catch (err) {
      console.error('Error loading storylines:', err);
      setError('Failed to load storylines');
    } finally {
      setLoading(false);
    }
  };

  const createTestStoryline = async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.createStoryline({
        title: 'Test Storyline from Frontend',
        description: 'Testing API integration from React frontend',
      });
      if (response.success) {
        setSuccess('Storyline created successfully!');
        await loadStorylines(); // Reload the list
      } else {
        setError(response.message || 'Failed to create storyline');
      }
    } catch (err) {
      console.error('Error creating storyline:', err);
      setError('Failed to create storyline');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStorylines();
  }, []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h4' gutterBottom>
        Storyline Management API Test
      </Typography>

      {error && (
        <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert
          severity='success'
          sx={{ mb: 2 }}
          onClose={() => setSuccess(null)}
        >
          {success}
        </Alert>
      )}

      <Box sx={{ mb: 3 }}>
        <Button
          variant='contained'
          onClick={loadStorylines}
          disabled={loading}
          sx={{ mr: 2 }}
        >
          {loading ? <CircularProgress size={20} /> : 'Load Storylines'}
        </Button>
        <Button
          variant='outlined'
          onClick={createTestStoryline}
          disabled={loading}
        >
          Create Test Storyline
        </Button>
      </Box>

      <Typography variant='h6' gutterBottom>
        Current Storylines ({storylines.length})
      </Typography>

      {storylines.length === 0 ? (
        <Typography color='text.secondary'>No storylines found</Typography>
      ) : (
        <Box>
          {storylines.map(storyline => (
            <Box
              key={storyline.id}
              sx={{
                mb: 1,
                p: 2,
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
              }}
            >
              <Typography variant='h6'>
                {storyline.title || 'Untitled'}
              </Typography>
              <Typography variant='body2' color='text.secondary'>
                ID: {storyline.id} | Articles: {storyline.article_count || 0}
              </Typography>
              {storyline.description && (
                <Typography variant='body2' sx={{ mt: 1 }}>
                  {storyline.description}
                </Typography>
              )}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
};

export default StorylineManagementTest;
