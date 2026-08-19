/**
 * Daily report — morning read of current events for one domain.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import { PageShell, LoadingState } from '@/components/ui';
import { intelligenceApi } from '@/services/api/intelligence';
import { formatDomainLabel } from '@/utils/domainHelper';
import { statusLabel } from '@/utils/statusLabel';

type DailyItem = {
  episode_id?: number;
  story_id?: number;
  title: string;
  lede?: string | null;
  latest_event?: string | null;
  episode_state?: string | null;
  new_event_count?: number;
  due_date?: string;
};

type DailyPayload = {
  date: string;
  framing?: string;
  time_of_day?: string;
  counts?: Record<string, number>;
  moved_today?: DailyItem[];
  new_today?: DailyItem[];
  published?: DailyItem[];
  quiet_watch?: DailyItem[];
};

function Section({
  title,
  empty,
  children,
}: {
  title: string;
  empty?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant='h6' fontWeight={700} sx={{ mb: 1 }}>
        {title}
      </Typography>
      {empty ? (
        <Typography variant='body2' color='text.secondary'>
          Nothing in this section today.
        </Typography>
      ) : (
        children
      )}
    </Box>
  );
}

export default function DailyPage() {
  const { domain } = useParams<{ domain: string }>();
  const dk = domain || 'politics';
  const navigate = useNavigate();
  const [data, setData] = useState<DailyPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await intelligenceApi.getDaily(dk);
        if (cancelled) return;
        if (!res?.success) {
          setError(res?.message || res?.error || 'Could not load daily report');
          setData(null);
        } else {
          setData(res.data as DailyPayload);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message || 'Could not load daily report');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dk]);

  if (loading) {
    return <LoadingState message='Loading today’s report…' />;
  }

  return (
    <PageShell
      title='Daily report'
      subtitle={
        data?.framing ||
        `What moved in ${formatDomainLabel(dk) || dk}${data?.date ? ` · ${data.date}` : ''}`
      }
      breadcrumbs={[
        { label: 'Home', to: `/${dk}` },
        { label: formatDomainLabel(dk) || dk, to: `/${dk}` },
        { label: 'Daily' },
      ]}
    >
      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {data?.counts && (
        <Stack direction='row' spacing={1} flexWrap='wrap' useFlexGap sx={{ mb: 3 }}>
          <Chip size='small' label={`${data.counts.events ?? 0} events`} />
          <Chip size='small' label={`${data.counts.moved ?? 0} episodes moved`} />
          <Chip size='small' label={`${data.counts.published ?? 0} stories`} />
        </Stack>
      )}

      <Section title='Published today' empty={!data?.published?.length}>
        <Stack spacing={1}>
          {(data?.published || []).map(item => (
            <Card key={item.story_id} variant='outlined'>
              <CardActionArea
                onClick={() => navigate(`/${dk}/editor/stories/${item.story_id}`)}
              >
                <CardContent>
                  <Typography fontWeight={600}>{item.title}</Typography>
                  {item.lede && (
                    <Typography variant='body2' color='text.secondary' sx={{ mt: 0.5 }}>
                      {item.lede}
                    </Typography>
                  )}
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      </Section>

      <Section title='What moved' empty={!data?.moved_today?.length}>
        <Stack spacing={1}>
          {(data?.moved_today || []).map(item => (
            <Card key={item.episode_id} variant='outlined'>
              <CardActionArea
                onClick={() => navigate(`/${dk}/storylines/${item.episode_id}`)}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                    <Typography fontWeight={600}>{item.title}</Typography>
                    {item.episode_state && (
                      <Chip size='small' label={statusLabel(item.episode_state)} />
                    )}
                  </Box>
                  <Typography variant='body2' color='text.secondary'>
                    {item.latest_event || 'New developments'}
                    {item.new_event_count
                      ? ` · ${item.new_event_count} event${item.new_event_count === 1 ? '' : 's'}`
                      : ''}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      </Section>

      <Section title='New episodes' empty={!data?.new_today?.length}>
        <Stack spacing={1}>
          {(data?.new_today || []).map(item => (
            <Card key={item.episode_id} variant='outlined'>
              <CardActionArea
                onClick={() => navigate(`/${dk}/storylines/${item.episode_id}`)}
              >
                <CardContent>
                  <Typography fontWeight={600}>{item.title}</Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      </Section>

      <Section title='Quiet but watch' empty={!data?.quiet_watch?.length}>
        <Stack spacing={1}>
          {(data?.quiet_watch || []).map(item => (
            <Card key={`${item.episode_id}-${item.title}`} variant='outlined'>
              <CardActionArea
                onClick={() =>
                  item.episode_id
                    ? navigate(`/${dk}/storylines/${item.episode_id}`)
                    : undefined
                }
              >
                <CardContent>
                  <Typography fontWeight={600}>{item.title}</Typography>
                  <Typography variant='body2' color='text.secondary'>
                    {statusLabel(item.episode_state)}
                    {item.due_date ? ` · due ${item.due_date}` : ''}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      </Section>
    </PageShell>
  );
}
