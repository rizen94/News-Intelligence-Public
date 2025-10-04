import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  CircularProgress,
  Alert,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';

const SimpleStorylineReport = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [storyline, setStoryline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadStoryline = async() => {
      try {
        setLoading(true);
        const response = await fetch(`/api/storylines/${id}/report`);
        const data = await response.json();

        if (data.success) {
          setStoryline(data.data.storyline);
        } else {
          setError('Failed to load storyline');
        }
      } catch (err) {
        setError('Error loading storyline');
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      loadStoryline();
    }
  }, [id]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>Loading Storyline Report...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/storylines')}>
          Back to Storylines
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/storylines')}>
          Back to Storylines
        </Button>
        <Typography variant="h4">Storyline Report</Typography>
      </Box>

      {storyline && (
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              {storyline.title}
            </Typography>
            <Typography variant="body1" paragraph>
              {storyline.description}
            </Typography>
            <Typography variant="h6" gutterBottom>
              Master Summary
            </Typography>
            <Typography variant="body2" paragraph>
              {storyline.master_summary || 'No summary available'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Status: {storyline.status} | Articles: {storyline.article_count}
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default SimpleStorylineReport;
