/**
 * Single-article reader for intake / recent_article links (`/{domain}/articles/:id`).
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Breadcrumb } from '../../components/PaginationBar';
import { withDomainQuery } from '../../hooks/useV2Domain';
import { articlesApi } from '../../../services/api/articles';
import {
  fetchReaderArticleIntelligence,
  type ReaderArticleIntelligence,
} from '../../services/readerApi';
import { ArticleIntelligencePanel } from '../../components/ReaderIntelligenceSurface';
import {
  articleSummaryIsRedundant,
  prepareArticleReaderText,
  sanitizeSnippet,
  stripReaderMdMarkers,
} from '../../../utils/sanitizeSnippet';
import { isValidDomain } from '../../../utils/domainHelper';

const THIN_ARTICLE_CHARS = 360;

type ArticleRow = {
  id?: number;
  title?: string;
  summary?: string;
  content?: string;
  url?: string;
  source_name?: string;
  source?: string;
  source_domain?: string;
  published_at?: string | null;
  created_at?: string | null;
};

function ReaderMarkdown({ source }: { source: string }) {
  const text = sanitizeSnippet(source || '', '').trim();
  if (!text) return null;
  return (
    <div className='v2-reader-md'>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

export default function ArticleReaderPage() {
  const { domain: domainParam, articleId } = useParams<{
    domain: string;
    articleId: string;
  }>();
  const domain =
    domainParam && isValidDomain(domainParam) ? domainParam : 'politics';
  const [article, setArticle] = useState<ArticleRow | null>(null);
  const [spine, setSpine] = useState<ReaderArticleIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enriching, setEnriching] = useState(false);
  const [enrichNote, setEnrichNote] = useState<string | null>(null);
  const enrichTried = useRef(false);

  useEffect(() => {
    if (!articleId) return;
    let cancelled = false;
    setError(null);
    setArticle(null);
    setSpine(null);
    articlesApi
      .getArticle(articleId, domain)
      .then((res: { success?: boolean; data?: ArticleRow; error?: string }) => {
        if (cancelled) return;
        if (res?.success === false || !res?.data) {
          setError(res?.error || 'Article not found');
          return;
        }
        setArticle(res.data);
      })
      .catch(err => {
        if (!cancelled) setError(err?.message || 'Failed to load article');
      });
    return () => {
      cancelled = true;
    };
  }, [articleId, domain]);

  useEffect(() => {
    if (!articleId) return;
    let cancelled = false;
    fetchReaderArticleIntelligence(articleId, domain)
      .then(data => {
        if (!cancelled) setSpine(data);
      })
      .catch(() => {
        if (!cancelled) setSpine(null);
      });
    return () => {
      cancelled = true;
    };
  }, [articleId, domain]);

  useEffect(() => {
    enrichTried.current = false;
    setEnrichNote(null);
  }, [articleId, domain]);

  useEffect(() => {
    if (!article?.id || !article.url || enrichTried.current) return;
    const rawLen = Math.max(
      (article.content || '').length,
      (article.summary || '').length
    );
    if (rawLen >= THIN_ARTICLE_CHARS) return;
    enrichTried.current = true;
    let cancelled = false;
    setEnriching(true);
    articlesApi
      .fetchFullContent(article.id, domain)
      .then((res: { success?: boolean; data?: { content?: string }; message?: string }) => {
        if (cancelled) return;
        const next = (res?.data?.content || '').trim();
        if (next.length > rawLen + 40) {
          setArticle(prev => (prev ? { ...prev, content: next } : prev));
          setEnrichNote(null);
        } else if (!res?.success) {
          setEnrichNote(
            res?.message || 'Only the RSS excerpt is stored; open the source for full text.'
          );
        } else {
          setEnrichNote(
            'This item is a short feed excerpt (common for paywalled publishers).'
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEnrichNote('Only the RSS excerpt is available here.');
        }
      })
      .finally(() => {
        if (!cancelled) setEnriching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [article, domain]);

  const title = stripReaderMdMarkers(article?.title || '').trim() || 'Untitled';
  const summary = prepareArticleReaderText(article?.summary || '', title);
  const body = prepareArticleReaderText(article?.content || '', title);
  const when =
    article?.published_at || article?.created_at || null;
  const sourceLabel =
    article?.source_name || article?.source || article?.source_domain;
  const hasLongBody =
    Boolean(body) &&
    body.length > Math.max(summary.length, 80) + 60 &&
    body !== summary;
  const showSummary =
    Boolean(summary) &&
    !articleSummaryIsRedundant(summary, body, title) &&
    (hasLongBody || summary.length >= THIN_ARTICLE_CHARS);
  const excerpt =
    !hasLongBody && (summary || body)
      ? summary || body
      : showSummary
        ? summary
        : '';
  const mainBody = hasLongBody ? body : showSummary ? '' : '';
  const isThinExcerpt = Boolean(excerpt) && excerpt.length < THIN_ARTICLE_CHARS;

  return (
    <div>
      <Breadcrumb
        crumbs={[
          { label: 'Home', to: withDomainQuery('/', domain) },
          { label: 'News', to: withDomainQuery('/news', domain) },
          { label: domain.toUpperCase() },
          { label: title.slice(0, 48) + (title.length > 48 ? '…' : '') },
        ]}
      />

      <article className='v2-reader-body' style={{ maxWidth: '42rem' }}>
        <p className='v2-section-label'>
          {domain.toUpperCase()} · Article
        </p>
        <h1>{title}</h1>
        <div className='v2-hero-rule' />
        <div className='v2-story-meta' style={{ marginBottom: '1.25rem' }}>
          {when ? <span>{when.slice(0, 10)}</span> : null}
          {when && sourceLabel ? (
            <span className='v2-meta-sep' aria-hidden='true'>
              {' '}
              ·{' '}
            </span>
          ) : null}
          {sourceLabel ? <span>{sourceLabel}</span> : null}
        </div>

        {error ? <p className='v2-empty' style={{ color: 'crimson' }}>{error}</p> : null}
        {!article && !error ? <p className='v2-empty'>Loading…</p> : null}

        {enriching ? (
          <p className='v2-empty' style={{ marginBottom: '1rem' }}>
            Loading full article text…
          </p>
        ) : null}

        {excerpt ? (
          <section style={{ marginBottom: '1.25rem' }}>
            <h2 className='v2-section-label'>
              {isThinExcerpt ? 'Feed excerpt' : 'Summary'}
            </h2>
            {isThinExcerpt ? (
              <blockquote className='v2-pull-quote'>{excerpt}</blockquote>
            ) : (
              <ReaderMarkdown source={excerpt} />
            )}
            {isThinExcerpt && enrichNote ? (
              <p
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--v2-ink-muted)',
                  marginTop: '0.75rem',
                }}
              >
                {enrichNote}
              </p>
            ) : null}
          </section>
        ) : null}

        {mainBody ? (
          <section>
            <h2 className='v2-section-label'>Full text</h2>
            <ReaderMarkdown source={mainBody} />
          </section>
        ) : null}

        {!excerpt && !mainBody && article && !error && !enriching ? (
          <p className='v2-empty'>No body stored for this article yet.</p>
        ) : null}

        {article?.url ? (
          <p style={{ marginTop: '1.5rem' }}>
            <a href={article.url} target='_blank' rel='noopener noreferrer'>
              Read original source →
            </a>
          </p>
        ) : null}

        {article && !error ? (
          <section style={{ marginTop: '2rem' }}>
            <hr className='v2-section-rule' />
            <h2 className='v2-section-label'>Intelligence spine</h2>
            <ArticleIntelligencePanel data={spine} domain={domain} />
          </section>
        ) : null}
      </article>
    </div>
  );
}