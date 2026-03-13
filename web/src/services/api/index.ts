/**
 * API domain modules — load only what you need.
 */
export { articlesApi } from './articles';
export { watchlistApi } from './watchlist';
export { storylinesApi } from './storylines';
export { topicsApi } from './topics';
export { rssApi } from './rss';
export { monitoringApi } from './monitoring';
export { intelligenceApi } from './intelligence';
export { financeAnalysisApi } from './financeAnalysis';
export { contextCentricApi } from './contextCentric';
export type {
  EntityProfile,
  Context,
  TrackedEvent,
  EventChronicle,
  ExtractedClaim,
  PatternDiscovery,
  ContextCentricStatus,
  ContextCentricQuality,
} from './contextCentric';
export { getApi, getCurrentDomain } from './client';
