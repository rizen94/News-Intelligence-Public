/**
 * Dedicated published news_story reader (final product surface).
 */
import React, { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { Alert, Button, Stack } from '@mui/material';
import { PageShell, UiCard, LoadingState } from '@/components/ui';
import { editorialApi } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';
import NewsStoryReader, { type NewsStoryLike } from '@/components/Editorial/NewsStoryReader';

export default function NewsStoryPage() {
  const { storyId, domain } = useParams<{ storyId: string; domain: string }>();
  const id = Number(storyId);
  const dk = domain || 'politics';
  const [story, setStory] = useState<NewsStoryLike | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await editorialApi.getStory(id);
        const data = unwrapData<NewsStoryLike>(res);
        if (!cancelled) setStory(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load story');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading && !story) return <LoadingState />;
  if (!story) {
    return (
      <PageShell title='News story'>
        <Alert severity='error'>{error || 'Not found'}</Alert>
      </PageShell>
    );
  }

  return (
    <PageShell
      title={String(story.title || `Story ${id}`)}
      subtitle={
        story.status === 'published'
          ? 'Published news story'
          : `Draft manuscript · status=${story.status}`
      }
      breadcrumbs={[
        { label: 'Editor', to: `/${dk}/editor` },
        { label: `Story ${id}` },
      ]}
    >
      {error ? (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}
      <Stack direction='row' spacing={1} sx={{ mb: 2 }}>
        {story.package_id ? (
          <Button
            component={RouterLink}
            to={`/${dk}/editor/packages/${story.package_id}`}
            size='small'
            variant='outlined'
          >
            Open package #{String(story.package_id)}
          </Button>
        ) : null}
        <Button component={RouterLink} to={`/${dk}/editor`} size='small'>
          Editor home
        </Button>
      </Stack>
      <UiCard>
        <NewsStoryReader story={story} variant='full' />
      </UiCard>
    </PageShell>
  );
}
