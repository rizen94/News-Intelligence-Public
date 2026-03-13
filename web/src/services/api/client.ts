/**
 * API client helpers — shared by domain modules.
 */
import type { AxiosInstance } from 'axios';
import { getCurrentDomain } from '../../utils/domainHelper';
import { getAPIConnectionManager } from '../apiConnectionManager';

let apiInstance: AxiosInstance | null = null;
export const getApi = (): AxiosInstance => {
  if (!apiInstance) {
    const connectionManager = getAPIConnectionManager();
    apiInstance = connectionManager.getApiInstance();
  }
  return apiInstance;
};
export { getCurrentDomain };
