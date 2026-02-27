import { api } from './api';
import type { RuntimeConfigResponse, RuntimeConfigUpdateRequest } from '@/types/api';

export async function getRuntimeConfig(): Promise<RuntimeConfigResponse> {
  return api.get<RuntimeConfigResponse>('/api/v1/config/runtime');
}

export async function updateRuntimeConfig(
  request: RuntimeConfigUpdateRequest
): Promise<RuntimeConfigResponse> {
  return api.put<RuntimeConfigResponse>('/api/v1/config/runtime', request);
}
