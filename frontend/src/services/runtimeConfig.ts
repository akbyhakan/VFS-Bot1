import { api } from './api';
import type { RuntimeConfigResponse, RuntimeConfigUpdateRequest } from '@/types/api';

/**
 * Validates that a config key contains a dot (required format: 'category.parameter').
 * Throws an error if the key is invalid, preventing unnecessary 422 round-trips.
 */
export function validateConfigKey(key: string): void {
  if (!key || !key.includes('.')) {
    throw new Error("Config key must be in format 'category.parameter' (must contain a dot)");
  }
}

export async function getRuntimeConfig(): Promise<RuntimeConfigResponse> {
  return api.get<RuntimeConfigResponse>('/api/v1/config/runtime');
}

export async function updateRuntimeConfig(
  request: RuntimeConfigUpdateRequest
): Promise<RuntimeConfigResponse> {
  validateConfigKey(request.key);
  return api.put<RuntimeConfigResponse>('/api/v1/config/runtime', request);
}
