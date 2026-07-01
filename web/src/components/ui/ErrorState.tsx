import React from 'react';
import { Alert, Button, Box } from '@mui/material';

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Box sx={{ py: 2 }}>
      <Alert
        severity='error'
        action={
          onRetry ? (
            <Button color='inherit' size='small' onClick={onRetry}>
              Retry
            </Button>
          ) : undefined
        }
      >
        {message}
      </Alert>
    </Box>
  );
}
