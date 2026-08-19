/**
 * Reader surface for a published (or draft) news_story — markdown prose with
 * [@mN] markers resolved to numbered source footnotes.
 */
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Box, Link, Stack, Typography, Divider, Chip } from '@mui/material';

export type StoryCitation = {
  id?: number;
  package_member_id?: number | null;
  citation_marker?: string | null;
  source_table?: string | null;
  source_url?: string | null;
  quote?: string | null;
};

export type NewsStoryLike = {
  id?: number;
  package_id?: number | null;
  title?: string | null;
  lede?: string | null;
  body_md?: string | null;
  status?: string | null;
  presentation_kind?: string | null;
  published_at?: string | null;
  domain_keys?: string[] | null;
  citations?: StoryCitation[];
};

const MARKER_RE = /\[@m(\d+)\]/g;

function stripHtml(s: string): string {
  return s
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url.slice(0, 48);
  }
}

export function prepareCitedMarkdown(
  bodyMd: string,
  citations: StoryCitation[]
): { markdown: string; sources: Array<{ n: number; marker: string; cite: StoryCitation }> } {
  const byMarker = new Map<string, StoryCitation>();
  for (const c of citations) {
    const m = (c.citation_marker || '').trim();
    if (m) byMarker.set(m, c);
    if (c.package_member_id != null) {
      byMarker.set(`[@m${c.package_member_id}]`, c);
    }
  }

  const sources: Array<{ n: number; marker: string; cite: StoryCitation }> = [];
  const seen = new Map<string, number>();

  const markdown = (bodyMd || '').replace(MARKER_RE, (_full, id: string) => {
    const marker = `[@m${id}]`;
    let n = seen.get(marker);
    if (n == null) {
      n = sources.length + 1;
      seen.set(marker, n);
      sources.push({
        n,
        marker,
        cite: byMarker.get(marker) || {
          citation_marker: marker,
          package_member_id: Number(id),
        },
      });
    }
    return ` [[${n}]](#story-src-${n})`;
  });

  return { markdown, sources };
}

type Props = {
  story: NewsStoryLike;
  /** Compact = embedded in package page; full = dedicated story page */
  variant?: 'compact' | 'full';
};

export default function NewsStoryReader({ story, variant = 'full' }: Props) {
  const citations = story.citations || [];
  const { markdown, sources } = useMemo(
    () => prepareCitedMarkdown(story.body_md || '', citations),
    [story.body_md, citations]
  );

  return (
    <Box
      component='article'
      sx={{
        maxWidth: variant === 'full' ? 720 : '100%',
        mx: variant === 'full' ? 'auto' : 0,
      }}
    >
      <Stack direction='row' spacing={1} alignItems='center' flexWrap='wrap' sx={{ mb: 1.5 }}>
        {story.status ? (
          <Chip
            size='small'
            color={story.status === 'published' ? 'success' : 'default'}
            label={String(story.status)}
          />
        ) : null}
        {story.presentation_kind && story.presentation_kind !== 'unset' ? (
          <Chip size='small' variant='outlined' label={String(story.presentation_kind)} />
        ) : null}
        {Array.isArray(story.domain_keys) && story.domain_keys.length
          ? story.domain_keys.map(d => (
              <Chip key={d} size='small' variant='outlined' label={d} />
            ))
          : null}
        {story.published_at ? (
          <Typography variant='caption' color='text.secondary'>
            {new Date(String(story.published_at)).toLocaleString()}
          </Typography>
        ) : null}
      </Stack>

      <Typography
        component='h1'
        variant={variant === 'full' ? 'h3' : 'h5'}
        sx={{ fontWeight: 650, letterSpacing: '-0.02em', lineHeight: 1.2, mb: 1 }}
      >
        {story.title || 'Untitled story'}
      </Typography>

      {story.lede ? (
        <Typography
          variant='subtitle1'
          color='text.secondary'
          sx={{ mb: 2, fontSize: '1.05rem', lineHeight: 1.45 }}
        >
          {story.lede}
        </Typography>
      ) : null}

      <Box
        className='news-story-body'
        sx={{
          '& p': { mb: 1.75, fontSize: '1.05rem', lineHeight: 1.65 },
          '& h2': { mt: 3, mb: 1.25, fontSize: '1.35rem', fontWeight: 650 },
          '& h3': { mt: 2.5, mb: 1, fontSize: '1.15rem', fontWeight: 600 },
          '& ul, & ol': { pl: 2.5, mb: 1.75 },
          '& li': { mb: 0.5, lineHeight: 1.55 },
          '& a': { color: 'primary.main' },
        }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </Box>

      {sources.length > 0 ? (
        <Box sx={{ mt: 4 }}>
          <Divider sx={{ mb: 2 }} />
          <Typography variant='overline' color='text.secondary' sx={{ letterSpacing: 1 }}>
            Sources
          </Typography>
          <Stack component='ol' spacing={1.5} sx={{ m: 0, pl: 2.5, mt: 1 }}>
            {sources.map(s => {
              const url = (s.cite.source_url || '').trim();
              const quote = stripHtml(String(s.cite.quote || '')).slice(0, 220);
              return (
                <Box component='li' key={s.n} id={`story-src-${s.n}`} sx={{ pl: 0.5 }}>
                  <Typography variant='body2' sx={{ fontWeight: 600 }}>
                    {url ? (
                      <Link href={url} target='_blank' rel='noopener noreferrer'>
                        {hostname(url)}
                      </Link>
                    ) : (
                      s.cite.source_table || s.marker
                    )}
                  </Typography>
                  {quote ? (
                    <Typography
                      variant='body2'
                      color='text.secondary'
                      sx={{ fontStyle: 'italic', mt: 0.25 }}
                    >
                      “{quote}
                      {quote.length >= 220 ? '…' : ''}”
                    </Typography>
                  ) : null}
                </Box>
              );
            })}
          </Stack>
        </Box>
      ) : null}
    </Box>
  );
}
