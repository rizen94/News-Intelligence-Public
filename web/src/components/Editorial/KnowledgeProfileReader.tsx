/**
 * Reader for knowledge_profile — is/is-not ledger + cited report body.
 */
import React, { useMemo } from 'react';
import { Box, Chip, Divider, Link, Stack, Typography } from '@mui/material';
import NewsStoryReader, {
  type NewsStoryLike,
  type StoryCitation,
} from '@/components/Editorial/NewsStoryReader';

export type KnowledgeAssertion = {
  text?: string | null;
  verdict?: string | null;
  evidence_grade?: string | null;
  member_row_id?: number | null;
  source_refs?: {
    source_url?: string | null;
    quote?: string | null;
  } | null;
};

export type KnowledgeProfileLike = {
  id?: number;
  title?: string | null;
  status?: string | null;
  body_md?: string | null;
  domain_key?: string | null;
  package_id?: number | null;
  published_at?: string | null;
  is_assertions?: KnowledgeAssertion[] | null;
  is_not_assertions?: KnowledgeAssertion[] | null;
  open_questions?: KnowledgeAssertion[] | null;
  citations?: StoryCitation[] | null;
};

type Props = {
  profile: KnowledgeProfileLike;
  variant?: 'compact' | 'full';
};

function AssertionList({
  title,
  items,
}: {
  title: string;
  items: KnowledgeAssertion[];
}) {
  if (!items.length) {
    return (
      <Box sx={{ mb: 2 }}>
        <Typography variant='subtitle2' sx={{ mb: 0.5 }}>
          {title}
        </Typography>
        <Typography variant='body2' color='text.secondary'>
          None yet.
        </Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant='subtitle2' sx={{ mb: 1 }}>
        {title}
      </Typography>
      <Stack spacing={1.25} component='ol' sx={{ m: 0, pl: 2.5 }}>
        {items.map((a, i) => {
          const url = (a.source_refs?.source_url || '').trim();
          return (
            <Box component='li' key={`${a.member_row_id || i}-${a.text?.slice(0, 40)}`}>
              <Typography variant='body2'>{a.text}</Typography>
              <Stack direction='row' spacing={1} flexWrap='wrap' sx={{ mt: 0.35 }}>
                {a.verdict ? <Chip size='small' label={String(a.verdict)} /> : null}
                {a.evidence_grade ? (
                  <Chip size='small' variant='outlined' label={String(a.evidence_grade)} />
                ) : null}
                {url ? (
                  <Link href={url} target='_blank' rel='noopener noreferrer' variant='caption'>
                    source
                  </Link>
                ) : null}
              </Stack>
            </Box>
          );
        })}
      </Stack>
    </Box>
  );
}

export default function KnowledgeProfileReader({ profile, variant = 'full' }: Props) {
  const isA = (profile.is_assertions || []).filter(a => a?.text);
  const isNot = (profile.is_not_assertions || []).filter(a => a?.text);
  const openQ = (profile.open_questions || []).filter(a => a?.text);

  const storyLike: NewsStoryLike = useMemo(
    () => ({
      id: profile.id,
      title: profile.title,
      body_md: profile.body_md,
      status: profile.status,
      published_at: profile.published_at,
      domain_keys: profile.domain_key ? [profile.domain_key] : [],
      citations: profile.citations || [],
      package_id: profile.package_id,
    }),
    [profile]
  );

  return (
    <Box>
      <AssertionList title='What it is (supported)' items={isA} />
      <AssertionList title='What it is not (disproved)' items={isNot} />
      <AssertionList title='Open questions' items={openQ} />
      <Divider sx={{ my: 2 }} />
      <Typography variant='overline' color='text.secondary' sx={{ letterSpacing: 1 }}>
        Cited report
      </Typography>
      {(profile.body_md || '').trim() ? (
        <Box sx={{ mt: 1 }}>
          <NewsStoryReader story={storyLike} variant={variant} />
        </Box>
      ) : (
        <Typography variant='body2' color='text.secondary' sx={{ mt: 1 }}>
          No report body yet — run a Research pass merge or regenerate.
        </Typography>
      )}
    </Box>
  );
}
