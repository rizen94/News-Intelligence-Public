// V4 Frontend Compatibility Layer
// This module provides compatibility between legacy frontend expectations and v4 data

export const v4Compatibility = {
  // Map v4 article fields to legacy expectations
  mapArticle: article => ({
    ...article,
    published_date: article.published_at,
    source: article.source_domain,
  }),

  // Map v4 storyline fields to legacy expectations
  mapStoryline: storyline => ({
    ...storyline,
    created_date: storyline.created_at,
    updated_date: storyline.updated_at,
  }),

  // Map v4 RSS feed fields to legacy expectations
  mapRSSFeed: feed => ({
    ...feed,
    last_fetch: feed.last_fetched_at,
  }),

  // Map v4 API response structure
  mapAPIResponse: response => ({
    ...response,
    data: {
      ...response.data,
      total_count: response.data?.total || response.data?.total_count,
      feeds: response.data?.feeds || response.data?.items,
      storylines: response.data?.storylines || response.data?.items,
    },
  }),
};

export default v4Compatibility;
