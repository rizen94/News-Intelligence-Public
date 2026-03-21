/**
 * Edit orchestrator_tags for a context or entity. Tags signal the orchestrator
 * to prioritize this item for deeper story building.
 */
import React, { useState } from 'react';
import {
  Box,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  OutlinedInput,
  SelectChangeEvent,
} from '@mui/material';

export const ORCHESTRATOR_TAG_OPTIONS = [
  { value: 'deep_story', label: 'Deep story' },
  { value: 'breaking', label: 'Breaking' },
  { value: 'investigation', label: 'Investigation' },
  { value: 'background', label: 'Background' },
  { value: 'follow_up', label: 'Follow-up' },
  { value: 'priority', label: 'Priority' },
] as const;

interface OrchestratorTagsEditorProps {
  tags: string[];
  onSave: (tags: string[]) => Promise<void>;
  disabled?: boolean;
}

export default function OrchestratorTagsEditor({
  tags,
  onSave,
  disabled,
}: OrchestratorTagsEditorProps) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async (e: SelectChangeEvent<string>) => {
    const value = e.target.value;
    if (!value || tags.includes(value)) return;
    setError(null);
    setSaving(true);
    try {
      await onSave([...tags, value]);
    } catch (err) {
      setError((err as Error)?.message ?? 'Failed to update tags');
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (tag: string) => {
    setError(null);
    setSaving(true);
    try {
      await onSave(tags.filter(t => t !== tag));
    } catch (err) {
      setError((err as Error)?.message ?? 'Failed to update tags');
    } finally {
      setSaving(false);
    }
  };

  const existingSet = new Set(tags);
  const availableOptions = ORCHESTRATOR_TAG_OPTIONS.filter(
    o => !existingSet.has(o.value)
  );

  return (
    <Box>
      <Typography variant='subtitle2' color='text.secondary' gutterBottom>
        Orchestrator tags
      </Typography>
      <Typography
        variant='caption'
        color='text.secondary'
        display='block'
        sx={{ mb: 1 }}
      >
        Tag for the orchestrator to prioritize when building deeper stories.
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 1,
          mb: 1,
        }}
      >
        {tags.map(tag => (
          <Chip
            key={tag}
            label={
              ORCHESTRATOR_TAG_OPTIONS.find(o => o.value === tag)?.label ?? tag
            }
            size='small'
            onDelete={disabled || saving ? undefined : () => handleRemove(tag)}
            color='primary'
            variant='outlined'
          />
        ))}
        {availableOptions.length > 0 && (
          <FormControl
            size='small'
            sx={{ minWidth: 140 }}
            disabled={disabled || saving}
          >
            <InputLabel id='orchestrator-tag-add-label'>Add tag</InputLabel>
            <Select
              labelId='orchestrator-tag-add-label'
              value=''
              label='Add tag'
              onChange={handleAdd}
              input={<OutlinedInput label='Add tag' />}
            >
              {availableOptions.map(o => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>
      {error && (
        <Typography variant='caption' color='error'>
          {error}
        </Typography>
      )}
    </Box>
  );
}
