/**
 * API client helpers — shared by domain modules.
 */
import { getCurrentDomain } from '../../utils/domainHelper';
import { getAPIConnectionManager } from '../apiConnectionManager';

let apiInstance: any = null;
export const getApi = () => {
  if (!apiInstance) {
    const connectionManager = getAPIConnectionManager();
    apiInstance = connectionManager.getApiInstance();
  }
  return apiInstance;
};
export { getCurrentDomain };
