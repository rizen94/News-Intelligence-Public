/**
 * Utility functions for article-related calculations and formatting
 */

/**
 * Calculate reading time in minutes based on word count
 * Average reading speed: 200-250 words per minute
 * @param {string|number} content - Article content or word count
 * @returns {number} Reading time in minutes (rounded up)
 */
export const calculateReadingTime = content => {
  if (!content) return 0;

  let wordCount;
  if (typeof content === 'number') {
    wordCount = content;
  } else if (typeof content === 'string') {
    // Remove HTML tags and calculate word count
    const text = content.replace(/<[^>]*>/g, '').trim();
    wordCount = text.split(/\s+/).filter(word => word.length > 0).length;
  } else {
    return 0;
  }

  // Average reading speed: 225 words per minute
  const wordsPerMinute = 225;
  const readingTime = Math.ceil(wordCount / wordsPerMinute);
  return Math.max(1, readingTime); // Minimum 1 minute
};

/**
 * Format reading time as a human-readable string
 * @param {number} minutes - Reading time in minutes
 * @returns {string} Formatted reading time (e.g., "3 min read")
 */
export const formatReadingTime = minutes => {
  if (!minutes || minutes < 1) return '1 min read';
  if (minutes === 1) return '1 min read';
  return `${minutes} min read`;
};

/**
 * Get reading time from article (calculate if not present)
 * @param {object} article - Article object
 * @returns {number} Reading time in minutes
 */
export const getArticleReadingTime = article => {
  if (article.reading_time) {
    return article.reading_time;
  }
  if (article.word_count) {
    return calculateReadingTime(article.word_count);
  }
  if (article.content) {
    return calculateReadingTime(article.content);
  }
  return 0;
};

/**
 * Format date for display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date
 */
export const formatArticleDate = dateString => {
  if (!dateString) return 'No date';
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24)
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch (error) {
    return 'Invalid date';
  }
};
