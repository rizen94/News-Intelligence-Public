import { Box, Typography, Container } from '@mui/material';
import React from 'react';

import StorylineAlerts from '../../components/StorylineAlerts/StorylineAlerts';

const StorylineAlertsPage = () => {
  return (
    <Container maxWidth='lg' sx={{ py: 4 }}>
      <Box mb={4}>
        <Typography variant='h4' component='h1' gutterBottom>
          Storyline Alerts
        </Typography>
        <Typography variant='body1' color='text.secondary'>
          Stay informed about significant updates to your tracked storylines.
          Alerts are generated when new high-quality articles are added to story
          threads.
        </Typography>
      </Box>

      <StorylineAlerts />
    </Container>
  );
};

export default StorylineAlertsPage;
