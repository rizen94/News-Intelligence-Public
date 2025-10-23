import {
  Search,
  Article as Article,
  GroupWork as ClusterIcon,
  Person as PersonIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  Grid,
  Chip,
  LinearProgress,
} from '@mui/material';
import React, { useState } from 'react';

import { useNewsSystem } from '../../contexts/NewsSystemContext';

export default function Search() {
  const { state, actions } = useNewsSystem();
  const { search } = state;
  const [query, setQuery] = useState('');

  const handleSearch = () => {
    if (query.trim()) {
      actions.performSearch(query);
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 3 }}>
        Search
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={10}>
              <TextField
                fullWidth
                label="Search across articles, clusters, and entities"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                InputProps={{
                  startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                variant="contained"
                onClick={handleSearch}
                fullWidth
                startIcon={<Search />}
                disabled={!query.trim()}
              >
                Search
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {search.loading && (
        <Box sx={{ mb: 2 }}>
          <LinearProgress />
        </Box>
      )}

      {search.results.length > 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Search Results for: "{query}"
          </Typography>

          <Grid container spacing={3}>
            {search.results.map((result, index) => (
              <Grid item xs={12} key={index}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      {result.type === 'article' && <Article />}
                      {result.type === 'cluster' && <ClusterIcon />}
                      {result.type === 'entity' && <PersonIcon />}
                      <Typography variant="h6">
                        {result.title || result.text}
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {result.content || result.summary}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </Box>
  );
}
