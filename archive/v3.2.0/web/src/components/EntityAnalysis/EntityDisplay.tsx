import React from 'react';
import { Box, Typography, Chip, Grid, Paper } from '@mui/material';
import { Person, LocationOn, Business, Event, Tag } from '@mui/icons-material';

interface Entity {
  text: string;
  type: string;
  confidence: number;
  start: number;
  end: number;
}

interface EntityDisplayProps {
  entities?: Entity[];
  maxDisplay?: number;
  showConfidence?: boolean;
}

const EntityDisplay: React.FC<EntityDisplayProps> = ({
  entities = [],
  maxDisplay = 10,
  showConfidence = true,
}) => {
  const getEntityIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'person':
        return <Person />;
      case 'location':
      case 'place':
        return <LocationOn />;
      case 'organization':
      case 'org':
        return <Business />;
      case 'date':
      case 'time':
        return <Event />;
      default:
        return <Tag />;
    }
  };

  const getEntityColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'person':
        return 'primary';
      case 'location':
      case 'place':
        return 'success';
      case 'organization':
      case 'org':
        return 'info';
      case 'date':
      case 'time':
        return 'warning';
      default:
        return 'default';
    }
  };

  const groupedEntities = entities.reduce((acc, entity) => {
    if (!acc[entity.type]) {
      acc[entity.type] = [];
    }
    acc[entity.type].push(entity);
    return acc;
  }, {} as { [key: string]: Entity[] });

  const displayEntities = entities.slice(0, maxDisplay);

  if (entities.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 2 }}>
        <Typography variant="body2" color="textSecondary">
          No entities found
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Quick view of all entities */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Detected Entities ({entities.length})
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {displayEntities.map((entity, index) => (
            <Chip
              key={index}
              icon={getEntityIcon(entity.type)}
              label={entity.text}
              color={getEntityColor(entity.type)}
              size="small"
              variant="outlined"
            />
          ))}
          {entities.length > maxDisplay && (
            <Chip
              label={`+${entities.length - maxDisplay} more`}
              size="small"
              variant="outlined"
              color="default"
            />
          )}
        </Box>
      </Box>

      {/* Grouped view by type */}
      <Grid container spacing={2}>
        {Object.entries(groupedEntities).map(([type, typeEntities]) => (
          <Grid item xs={12} sm={6} md={4} key={type}>
            <Paper sx={{ p: 2, height: '100%' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                {getEntityIcon(type)}
                <Typography variant="subtitle2" sx={{ textTransform: 'capitalize' }}>
                  {type} ({typeEntities.length})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {typeEntities.slice(0, 5).map((entity, index) => (
                  <Chip
                    key={index}
                    label={entity.text}
                    color={getEntityColor(type)}
                    size="small"
                    variant="outlined"
                  />
                ))}
                {typeEntities.length > 5 && (
                  <Chip
                    label={`+${typeEntities.length - 5}`}
                    size="small"
                    variant="outlined"
                    color="default"
                  />
                )}
              </Box>
              {showConfidence && typeEntities.length > 0 && (
                <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
                  Avg. confidence: {(typeEntities.reduce((sum, e) => sum + e.confidence, 0) / typeEntities.length * 100).toFixed(1)}%
                </Typography>
              )}
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default EntityDisplay;