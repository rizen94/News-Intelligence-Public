import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
} from '@mui/material';
import { storylinesApi } from '../services/api/storylines';

const StorylineCreationDialog = ({ open, onClose, onCreated }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCreate = async() => {
    try {
      setLoading(true);
      setError(null);
      const data = await storylinesApi.createStoryline({ title, description });
      // API returns storyline object directly, or { success: false, error } on failure
      const storyline = data && data.data !== undefined ? data.data : data;
      const isError = data && data.success === false;
      if (storyline && storyline.id != null && !isError) {
        onCreated && onCreated(storyline);
        onClose();
        setTitle('');
        setDescription('');
      } else {
        setError((data && data.error) || 'Failed to create storyline');
      }
    } catch (err) {
      setError(err.message || 'Failed to create storyline');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth='sm'>
      <DialogTitle>Create New Storyline</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin='dense'
          label='Title'
          type='text'
          fullWidth
          value={title}
          onChange={e => setTitle(e.target.value)}
        />
        <TextField
          margin='dense'
          label='Description'
          type='text'
          fullWidth
          multiline
          rows={4}
          value={description}
          onChange={e => setDescription(e.target.value)}
        />
        {error && <div style={{ color: 'red' }}>{error}</div>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button onClick={handleCreate} variant='contained' disabled={loading}>
          {loading ? 'Creating...' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default StorylineCreationDialog;
