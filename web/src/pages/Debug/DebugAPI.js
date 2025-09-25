import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Alert,
  CircularProgress,
  Paper,
  Divider,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import newsSystemService from '../../services/newsSystemService';

const DebugAPI = () => {
  const [articlesResult, setArticlesResult] = useState(null);
  const [storylinesResult, setStorylinesResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const testArticlesAPI = async() => {
    setLoading(true);
    setError(null);
    try {
      console.log('Testing Articles API...');
      const result = await newsSystemService.getArticles({ limit: 2, page: 1 });
      console.log('Articles API Result:', result);
      setArticlesResult(result);
    } catch (err) {
      console.error('Articles API Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const testStorylinesAPI = async() => {
    setLoading(true);
    setError(null);
    try {
      console.log('Testing Storylines API...');
      const result = await newsSystemService.getActiveStories();
      console.log('Storylines API Result:', result);
      setStorylinesResult(result);
    } catch (err) {
      console.error('Storylines API Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const testDirectAPI = async() => {
    setLoading(true);
    setError(null);
    try {
      console.log('Testing Direct API calls...');

      // Test direct fetch
      const articlesResponse = await fetch('http://localhost:8000/api/articles/?per_page=2&page=1');
      const articlesData = await articlesResponse.json();
      console.log('Direct Articles API:', articlesData);

      const storylinesResponse = await fetch('http://localhost:8000/api/story-management/stories');
      const storylinesData = await storylinesResponse.json();
      console.log('Direct Storylines API:', storylinesData);

      setArticlesResult({ success: true, data: articlesData });
      setStorylinesResult({ success: true, data: storylinesData });
    } catch (err) {
      console.error('Direct API Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        API Debug Page
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Button
          variant="contained"
          onClick={testArticlesAPI}
          disabled={loading}
        >
          Test Articles API
        </Button>
        <Button
          variant="contained"
          onClick={testStorylinesAPI}
          disabled={loading}
        >
          Test Storylines API
        </Button>
        <Button
          variant="outlined"
          onClick={testDirectAPI}
          disabled={loading}
        >
          Test Direct API
        </Button>
      </Box>

      {loading && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <CircularProgress size={20} />
          <Typography>Testing API...</Typography>
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 2 }}>
        <Paper sx={{ p: 2, flex: 1 }}>
          <Typography variant="h6" gutterBottom>
            Articles API Result
          </Typography>
          <pre style={{ fontSize: '12px', overflow: 'auto', maxHeight: '300px' }}>
            {JSON.stringify(articlesResult, null, 2)}
          </pre>
        </Paper>

        <Paper sx={{ p: 2, flex: 1 }}>
          <Typography variant="h6" gutterBottom>
            Storylines API Result
          </Typography>
          <pre style={{ fontSize: '12px', overflow: 'auto', maxHeight: '300px' }}>
            {JSON.stringify(storylinesResult, null, 2)}
          </pre>
        </Paper>
      </Box>
    </Box>
  );
};

export default DebugAPI;
