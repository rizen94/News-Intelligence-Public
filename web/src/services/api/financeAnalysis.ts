/**
 * Finance Analysis API — orchestrator tasks, evidence, verification, schedule
 */
import { getApi } from './client';
import { getCurrentDomain } from '../../utils/domainHelper';
import Logger from '../../utils/logger';

const financeAnalysisApi = {
  async submitAnalysis(
    query: string,
    options?: { topic?: string; date_range?: { start: string; end: string }; wait?: boolean },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const params = new URLSearchParams({ query });
      if (options?.topic) params.set('topic', options.topic);
      if (options?.date_range?.start) params.set('start_date', options.date_range.start);
      if (options?.date_range?.end) params.set('end_date', options.date_range.end);
      if (options?.wait !== undefined) params.set('wait', String(options.wait));
      const response = await getApi().post(
        `/api/${domainKey}/finance/analyze?${params.toString()}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to submit analysis', error as Error);
      throw error;
    }
  },

  async getTaskTrace(taskId: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/trace/${taskId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get task trace', error as Error);
      throw error;
    }
  },

  async getTaskLedger(taskId: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/tasks/${taskId}/ledger`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get task ledger', error as Error);
      throw error;
    }
  },

  async getTaskStatus(taskId: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/tasks/${taskId}/status`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get task status', error as Error);
      throw error;
    }
  },

  async getTaskResult(taskId: string, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/tasks/${taskId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get task result', error as Error);
      throw error;
    }
  },

  async listTasks(
    filters?: { status?: string; task_type?: string; limit?: number; offset?: number },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const params = new URLSearchParams();
      if (filters?.status) params.set('status', filters.status);
      if (filters?.task_type) params.set('task_type', filters.task_type);
      if (filters?.limit) params.set('limit', String(filters.limit));
      if (filters?.offset) params.set('offset', String(filters.offset));
      const qs = params.toString();
      const response = await getApi().get(
        `/api/${domainKey}/finance/tasks${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to list tasks', error as Error);
      throw error;
    }
  },

  async getEvidenceIndex(
    filters?: { source?: string; limit?: number; offset?: number },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const params = new URLSearchParams();
      if (filters?.source) params.set('source', filters.source);
      if (filters?.limit) params.set('limit', String(filters.limit));
      if (filters?.offset) params.set('offset', String(filters.offset));
      const qs = params.toString();
      const response = await getApi().get(
        `/api/${domainKey}/finance/evidence${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get evidence index', error as Error);
      throw error;
    }
  },

  async getSourceStatus(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/sources/status`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get source status', error as Error);
      throw error;
    }
  },

  async triggerRefresh(
    source: 'gold' | 'edgar' | 'fred',
    params?: Record<string, string>,
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      if (source === 'gold') {
        const response = await getApi().post(
          `/api/${domainKey}/finance/gold/fetch`,
          null,
          { params }
        );
        return response.data;
      }
      if (source === 'edgar') {
        const response = await getApi().post(
          `/api/${domainKey}/finance/edgar/ingest`,
          null,
          { params: params || { filings_per_company: 1 } }
        );
        return response.data;
      }
      if (source === 'fred') {
        const response = await getApi().post(
          `/api/${domainKey}/finance/fetch-fred`,
          null,
          { params: params || {} }
        );
        return response.data;
      }
    } catch (error) {
      Logger.apiError('Failed to trigger refresh', error as Error);
      throw error;
    }
  },

  async getRefreshSchedule(domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/schedule`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get refresh schedule', error as Error);
      throw error;
    }
  },

  async getVerificationHistory(
    filters?: { limit?: number; offset?: number },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const params = new URLSearchParams();
      if (filters?.limit) params.set('limit', String(filters.limit));
      if (filters?.offset) params.set('offset', String(filters.offset));
      const qs = params.toString();
      const response = await getApi().get(
        `/api/${domainKey}/finance/verification${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get verification history', error as Error);
      throw error;
    }
  },

  async listResearchTopics(
    params?: { limit?: number; offset?: number; last_refined_task_id?: string },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const searchParams = new URLSearchParams();
      if (params?.limit) searchParams.set('limit', String(params.limit));
      if (params?.offset) searchParams.set('offset', String(params.offset));
      if (params?.last_refined_task_id) searchParams.set('last_refined_task_id', params.last_refined_task_id);
      const qs = searchParams.toString();
      const response = await getApi().get(
        `/api/${domainKey}/finance/research-topics${qs ? `?${qs}` : ''}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to list research topics', error as Error);
      throw error;
    }
  },

  async getResearchTopic(topicId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().get(
        `/api/${domainKey}/finance/research-topics/${topicId}`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to get research topic', error as Error);
      throw error;
    }
  },

  async createResearchTopic(
    payload: { task_id: string; name: string; query: string; topic?: string; date_range?: { start: string; end: string } },
    domain?: string
  ) {
    const domainKey = domain || getCurrentDomain();
    const url = `/api/${domainKey}/finance/research-topics`;
    const body = {
      task_id: payload.task_id,
      name: payload.name,
      query: payload.query,
      ...(payload.topic && { topic: payload.topic }),
      ...(payload.date_range && { date_range: payload.date_range }),
    };
    try {
      Logger.debug('Create research topic', { url, body: { ...body, query: body.query?.slice(0, 50) } });
      const response = await getApi().post(url, body);
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to create research topic', error as Error);
      throw error;
    }
  },

  async refineResearchTopic(topicId: number, domain?: string) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().post(
        `/api/${domainKey}/finance/research-topics/${topicId}/refine`
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to refine research topic', error as Error);
      throw error;
    }
  },

  async updateResearchTopicFromTask(
    topicId: number,
    payload: { task_id: string; name?: string },
    domain?: string
  ) {
    try {
      const domainKey = domain || getCurrentDomain();
      const response = await getApi().patch(
        `/api/${domainKey}/finance/research-topics/${topicId}`,
        payload
      );
      return response.data;
    } catch (error) {
      Logger.apiError('Failed to update research topic from task', error as Error);
      throw error;
    }
  },
};

export { financeAnalysisApi };
