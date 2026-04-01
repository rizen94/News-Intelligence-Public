import { getCurrentDomain } from '../utils/domainHelper';
import { getAPIConnectionManager } from './apiConnectionManager';
import {
  articlesApi,
  watchlistApi,
  storylinesApi,
  topicsApi,
  rssApi,
  monitoringApi,
  intelligenceApi,
  financeAnalysisApi,
} from './api';
import Logger from '../utils/logger';

// Lazy initialization to avoid circular dependencies
let apiInstance: any = null;
const getApi = () => {
  if (!apiInstance) {
    const connectionManager = getAPIConnectionManager();
    apiInstance = connectionManager.getApiInstance();
  }
  return apiInstance;
};

// Export api getter for backward compatibility
export const api = new Proxy({} as any, {
  get: (target, prop) => {
    return getApi()[prop];
  },
});

export { getAPIConnectionManager };

/**
 * API Service Class — delegates to domain modules (articles, watchlist, storylines, topics, rss, monitoring, intelligence).
 */
class APIService {
  // Articles
  getArticles = articlesApi.getArticles;
  getArticleSources = articlesApi.getArticleSources;
  getArticle = articlesApi.getArticle;
  deleteArticle = articlesApi.deleteArticle;
  deleteArticlesBulk = articlesApi.deleteArticlesBulk;
  analyzeArticles = articlesApi.analyzeArticles;
  getArticleEvents = articlesApi.getArticleEvents;

  // Watchlist
  getWatchlist = watchlistApi.getWatchlist;
  addToWatchlist = watchlistApi.addToWatchlist;
  removeFromWatchlist = watchlistApi.removeFromWatchlist;
  getWatchlistAlerts = watchlistApi.getWatchlistAlerts;
  markAlertRead = watchlistApi.markAlertRead;
  markAllAlertsRead = watchlistApi.markAllAlertsRead;
  getActivityFeed = watchlistApi.getActivityFeed;
  getDormantAlerts = watchlistApi.getDormantAlerts;
  getCoverageGaps = watchlistApi.getCoverageGaps;
  getCrossDomainConnections = watchlistApi.getCrossDomainConnections;

  // RSS Feeds (delegate to rssApi)
  getRSSFeeds = rssApi.getRSSFeeds;
  updateRSSFeeds = rssApi.updateRSSFeeds;
  createRSSFeed = rssApi.createRSSFeed;
  updateRSSFeed = rssApi.updateRSSFeed;
  deleteRSSFeed = rssApi.deleteRSSFeed;
  refreshRSSFeed = rssApi.refreshRSSFeed;
  getRSSCategories = rssApi.getRSSCategories;

  get rssFeeds() {
    return {
      getFeeds: (params?: any, domain?: string) =>
        this.getRSSFeeds(params, domain),
      createFeed: (feedData: any, domain?: string) =>
        this.createRSSFeed(feedData, domain),
      updateFeed: (feedId: number, feedData: any, domain?: string) =>
        this.updateRSSFeed(feedId, feedData, domain),
      deleteFeed: (feedId: number, domain?: string) =>
        this.deleteRSSFeed(feedId, domain),
      refreshFeed: (feedId: number, domain?: string) =>
        this.refreshRSSFeed(feedId, domain),
      getCategories: (domain?: string) => this.getRSSCategories(domain),
    };
  }

  // Storylines
  getStorylines = storylinesApi.getStorylines;
  getStoryline = storylinesApi.getStoryline;
  getStorylineTimeline = storylinesApi.getStorylineTimeline;
  getStorylineAudit = storylinesApi.getStorylineAudit;
  getStorylineNarrative = storylinesApi.getStorylineNarrative;
  enqueueStorylineRefinement = storylinesApi.enqueueStorylineRefinement;
  createStoryline = storylinesApi.createStoryline;
  updateStoryline = storylinesApi.updateStoryline;
  deleteStoryline = storylinesApi.deleteStoryline;
  discoverStorylines = storylinesApi.discoverStorylines;
  getBreakingNews = storylinesApi.getBreakingNews;
  compareStorylines = storylinesApi.compareStorylines;
  getStorylineEvolution = storylinesApi.getStorylineEvolution;
  checkStorylineMerge = storylinesApi.checkStorylineMerge;
  getConsolidationStatus = storylinesApi.getConsolidationStatus;
  runConsolidation = storylinesApi.runConsolidation;
  getStorylineHierarchy = storylinesApi.getStorylineHierarchy;
  getMegaStorylines = storylinesApi.getMegaStorylines;
  mergeStorylines = storylinesApi.mergeStorylines;
  getRelatedStorylines = storylinesApi.getRelatedStorylines;
  getRelatedCrossDomainStorylines =
    storylinesApi.getRelatedCrossDomainStorylines;
  analyzeStoryline = storylinesApi.analyzeStoryline;
  getAvailableArticles = storylinesApi.getAvailableArticles;
  addArticleToStoryline = storylinesApi.addArticleToStoryline;
  removeArticleFromStoryline = storylinesApi.removeArticleFromStoryline;
  getStorylineAutomationSettings = storylinesApi.getStorylineAutomationSettings;
  updateStorylineAutomationSettings =
    storylinesApi.updateStorylineAutomationSettings;
  triggerStorylineDiscovery = storylinesApi.triggerStorylineDiscovery;
  getAutomationSuggestions = storylinesApi.getAutomationSuggestions;
  approveSuggestion = storylinesApi.approveSuggestion;
  rejectSuggestion = storylinesApi.rejectSuggestion;

  // Intelligence
  getRAGContext = intelligenceApi.getRAGContext;
  queryRAG = intelligenceApi.queryRAG;
  getStorylineQuality = intelligenceApi.getStorylineQuality;
  getBatchQuality = intelligenceApi.getBatchQuality;
  getAnomalies = intelligenceApi.getAnomalies;
  watchAnomaly = intelligenceApi.watchAnomaly;
  getStorylineImpact = intelligenceApi.getStorylineImpact;
  getTrendingImpact = intelligenceApi.getTrendingImpact;
  getIntelligenceDashboard = intelligenceApi.getIntelligenceDashboard;
  getEventStorylineClaimConsistency =
    intelligenceApi.getEventStorylineClaimConsistency;
  getParticipantPositionDeltas = intelligenceApi.getParticipantPositionDeltas;
  getCausalChains = intelligenceApi.getCausalChains;
  getNarrativeDivergenceMap = intelligenceApi.getNarrativeDivergenceMap;
  runWatchlistThemeBridge = intelligenceApi.runWatchlistThemeBridge;
  runDocumentIntelligenceIntegration =
    intelligenceApi.runDocumentIntelligenceIntegration;
  getDomainEvents = intelligenceApi.getDomainEvents;
  synthesizeStoryline = intelligenceApi.synthesizeStoryline;
  getSynthesizedContent = intelligenceApi.getSynthesizedContent;
  bulkSynthesizeStorylines = intelligenceApi.bulkSynthesizeStorylines;
  checkSynthesisTaskStatus = intelligenceApi.checkSynthesisTaskStatus;
  getRecentDigests = intelligenceApi.getRecentDigests;
  generateWeeklyDigest = intelligenceApi.generateWeeklyDigest;
  generateDailyBriefing = intelligenceApi.generateDailyBriefing;
  getBriefingFeed = intelligenceApi.getBriefingFeed;
  getReport = intelligenceApi.getReport;
  submitContentFeedback = intelligenceApi.submitContentFeedback;
  getTopicCloud = intelligenceApi.getTopicCloud;
  getStoryDossier = intelligenceApi.getStoryDossier;

  // Topics
  getTopics = topicsApi.getTopics;
  getTopicCategoriesStats = topicsApi.getTopicCategoriesStats;
  getCategoryStats = topicsApi.getTopicCategoriesStats;
  getTopic = topicsApi.getTopic;
  updateTopic = topicsApi.updateTopic;
  getTopicWordCloud = topicsApi.getTopicWordCloud;
  getWordCloud = topicsApi.getWordCloud;
  getBigPicture = topicsApi.getBigPicture;
  getBannedTopics = topicsApi.getBannedTopics;
  banTopic = topicsApi.banTopic;
  unbanTopic = topicsApi.unbanTopic;
  getArticleTopics = topicsApi.getArticleTopics;
  getTopicBigPicture = topicsApi.getTopicBigPicture;
  getTrendingTopics = topicsApi.getTrendingTopics;
  getTopicArticles = topicsApi.getTopicArticles;
  getTopicSummary = topicsApi.getTopicSummary;
  getMergeSuggestions = topicsApi.getMergeSuggestions;
  mergeClusters = topicsApi.mergeClusters;
  clusterTopics = topicsApi.clusterTopics;
  clusterArticles = topicsApi.clusterTopics;
  convertTopicToStoryline = topicsApi.convertTopicToStoryline;
  mergeTopics = topicsApi.mergeTopics;
  getManagedTopics = topicsApi.getManagedTopics;
  getTopicsNeedingReview = topicsApi.getTopicsNeedingReview;
  getManagedTopic = topicsApi.getManagedTopic;
  getManagedTopicArticles = topicsApi.getManagedTopicArticles;
  processArticleTopics = topicsApi.processArticleTopics;
  submitTopicFeedback = topicsApi.submitTopicFeedback;

  // Monitoring & deduplication
  getHealth = monitoringApi.getHealth;
  getMonitoringDashboard = monitoringApi.getMonitoringDashboard;
  getMonitoringOverview = monitoringApi.getMonitoringOverview;
  getPipelineStatus = monitoringApi.getPipelineStatus;
  getDatabaseStats = monitoringApi.getDatabaseStats;
  getDevices = monitoringApi.getDevices;
  getHealthFeeds = monitoringApi.getHealthFeeds;
  getOrchestratorDashboard = monitoringApi.getOrchestratorDashboard;
  getSourcesCollected = monitoringApi.getSourcesCollected;
  getProcessRunSummary = monitoringApi.getProcessRunSummary;
  getAutomationStatus = monitoringApi.getAutomationStatus;
  getBacklogStatus = monitoringApi.getBacklogStatus;
  getProcessingProgress = monitoringApi.getProcessingProgress;
  getDocumentSourcesHealth = monitoringApi.getDocumentSourcesHealth;
  getDatabaseConnections = monitoringApi.getDatabaseConnections;
  triggerPhase = monitoringApi.triggerPhase;
  triggerPipeline = monitoringApi.triggerPipeline;
  getSystemHealth = monitoringApi.getSystemHealth;
  getSystemMetrics = monitoringApi.getSystemMetrics;
  getDatabaseMetrics = monitoringApi.getDatabaseMetrics;
  getLogStatistics = monitoringApi.getLogStatistics;
  getRealtimeLogs = monitoringApi.getRealtimeLogs;
  getAPIStatus = monitoringApi.getAPIStatus;
  getSqlExplorerEnabled = monitoringApi.getSqlExplorerEnabled;
  getSqlExplorerSchema = monitoringApi.getSqlExplorerSchema;
  postSqlExplorerQuery = monitoringApi.postSqlExplorerQuery;
  getDuplicateStats = monitoringApi.getDuplicateStats;
  detectDuplicates = monitoringApi.detectDuplicates;
  getURLDuplicates = monitoringApi.getURLDuplicates;
  getContentDuplicates = monitoringApi.getContentDuplicates;
  getSimilarArticles = monitoringApi.getSimilarArticles;
  autoMergeDuplicates = monitoringApi.autoMergeDuplicates;
  preventDuplicates = monitoringApi.preventDuplicates;
  analyzeSimilarity = monitoringApi.analyzeSimilarity;
  getDeduplicationStats = monitoringApi.getDeduplicationStats;
  getMLQueueStatus = monitoringApi.getMLQueueStatus;
  getAllMLProcessingStatus = monitoringApi.getAllMLProcessingStatus;
  getMLTimingStats = monitoringApi.getMLTimingStats;
  queueArticleForMLProcessing = monitoringApi.queueArticleForMLProcessing;
  getFeedbackLoopStatus = monitoringApi.getFeedbackLoopStatus;
  startFeedbackLoop = monitoringApi.startFeedbackLoop;
  stopFeedbackLoop = monitoringApi.stopFeedbackLoop;
  runAIAnalysis = monitoringApi.runAIAnalysis;
  getMarketTrends = monitoringApi.getMarketTrends;
  getMarketPatterns = monitoringApi.getMarketPatterns;
  getCorporateAnnouncements = monitoringApi.getCorporateAnnouncements;
  getFinanceDataSources = monitoringApi.getFinanceDataSources;
  getFinanceMarketData = monitoringApi.getFinanceMarketData;
  getGoldData = monitoringApi.getGoldData;
  triggerGoldFetch = monitoringApi.triggerGoldFetch;
  triggerFredFetch = monitoringApi.triggerFredFetch;

  // Finance Analysis (orchestrator)
  submitFinanceAnalysis = financeAnalysisApi.submitAnalysis;
  getFinanceTaskStatus = financeAnalysisApi.getTaskStatus;
  getFinanceTaskResult = financeAnalysisApi.getTaskResult;
  getFinanceTaskLedger = financeAnalysisApi.getTaskLedger;
  listFinanceTasks = financeAnalysisApi.listTasks;
  getFinanceEvidenceIndex = financeAnalysisApi.getEvidenceIndex;
  getFinanceSourceStatus = financeAnalysisApi.getSourceStatus;
  triggerFinanceRefresh = financeAnalysisApi.triggerRefresh;
  getFinanceRefreshSchedule = financeAnalysisApi.getRefreshSchedule;
  getFinanceVerificationHistory = financeAnalysisApi.getVerificationHistory;
  listFinanceResearchTopics = financeAnalysisApi.listResearchTopics;
  getFinanceResearchTopic = financeAnalysisApi.getResearchTopic;
  createFinanceResearchTopic = financeAnalysisApi.createResearchTopic;
  refineFinanceResearchTopic = financeAnalysisApi.refineResearchTopic;
  updateFinanceResearchTopicFromTask =
    financeAnalysisApi.updateResearchTopicFromTask;

  // Story expectations (alias for storylines)
  async getActiveStories(domain?: string) {
    return storylinesApi.getStorylines(
      { status: 'active', limit: 100 },
      domain
    );
  }

  async createStoryExpectation(data: any, domain?: string) {
    return storylinesApi.createStoryline(data, domain);
  }
}

let apiServiceInstance: APIService | null = null;

const getApiService = (): APIService => {
  if (!apiServiceInstance) {
    try {
      apiServiceInstance = new APIService();
    } catch (error) {
      Logger.apiError('Failed to create APIService instance', error as Error);
      apiServiceInstance = new APIService();
    }
  }
  return apiServiceInstance;
};

const apiService = getApiService();

export default apiService;
export { apiService, getApiService };
