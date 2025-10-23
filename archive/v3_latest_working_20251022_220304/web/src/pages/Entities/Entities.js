import {
  Search,
  Refresh,
  Person as PersonIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  Button,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  LinearProgress,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import { useNewsSystem } from '../../contexts/NewsSystemContext';

export default function Entities() {
  const { state, actions } = useNewsSystem();
  const { entities } = state;
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('PERSON');

  useEffect(() => {
    actions.fetchEntities(selectedType);
  }, [selectedType]);

  const handleSearch = () => {
    // Filter entities based on search query
  };

  const handleRefresh = () => {
    actions.fetchEntities(selectedType);
  };

  const getEntityIcon = (type) => {
    switch (type) {
    case 'PERSON': return <PersonIcon fontSize="small" />;
    case 'ORG': return <BusinessIcon fontSize="small" />;
    case 'GPE': return <LocationIcon fontSize="small" />;
    default: return <PersonIcon fontSize="small" />;
    }
  };

  const getEntityColor = (type) => {
    switch (type) {
    case 'PERSON': return 'primary';
    case 'ORG': return 'secondary';
    case 'GPE': return 'success';
    default: return 'default';
    }
  };

  const filteredEntities = entities.list.filter(entity => {
    if (searchQuery && !entity.text.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <Box>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 3 }}>
        Extracted Entities
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Search Entities"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                InputProps={{
                  startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Entity Type</InputLabel>
                <Select
                  value={selectedType}
                  label="Entity Type"
                  onChange={(e) => setSelectedType(e.target.value)}
                >
                  <MenuItem value="PERSON">People</MenuItem>
                  <MenuItem value="ORG">Organizations</MenuItem>
                  <MenuItem value="GPE">Locations</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={handleRefresh}
                fullWidth
              >
                Refresh
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        {filteredEntities.map((entity, index) => (
          <Grid item xs={12} sm={6} md={4} key={index}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  {getEntityIcon(entity.type)}
                  <Typography variant="h6" component="div">
                    {entity.text}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Chip
                    label={entity.type}
                    color={getEntityColor(entity.type)}
                    size="small"
                  />
                  <Typography variant="body2" color="text.secondary">
                    Frequency: {entity.frequency}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
