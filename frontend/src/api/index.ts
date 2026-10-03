import { getClientId } from '../lib/clientId';
import { createApiClient } from './client';

export { ApiError, isAbortError } from './client';
export type { ApiClient } from './client';
export * from './types';

export const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  getClientId,
});
