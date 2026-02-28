/**
 * Proxy management API service
 */

import { api } from './api';

export interface ProxyStats {
  total: number;
  active: number;
  failed: number;
}

export interface ProxyInfo {
  id: number;
  server: string;
  port: number;
  username: string;
  is_active: boolean;
  failure_count: number;
  last_used: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProxyListResponse {
  proxies: ProxyInfo[];
  stats: ProxyStats;
}

export interface UploadProxyResponse {
  message: string;
  count: number;
  filename: string;
  warnings?: string[];
}

export interface ProxyCreateRequest {
  server: string;
  port: number;
  username: string;
  password: string;
}

export interface ProxyUpdateRequest {
  server?: string;
  port?: number;
  username?: string;
  password?: string;
  is_active?: boolean;
}

export interface ProxyDeleteResponse {
  message: string;
}

export interface ProxyClearResponse {
  message: string;
}

export interface ProxyResetFailuresResponse {
  message: string;
}

/**
 * Upload proxy CSV file
 */
export async function uploadProxyCSV(file: File): Promise<UploadProxyResponse> {
  const formData = new FormData();
  formData.append('file', file);
  return api.upload<UploadProxyResponse>('/api/v1/proxy/upload', formData);
}

/**
 * Get proxy list with statistics
 */
export async function getProxyList(): Promise<ProxyListResponse> {
  return api.get<ProxyListResponse>('/api/v1/proxy/list');
}

/**
 * Get proxy statistics
 */
export async function getProxyStats(): Promise<ProxyStats> {
  return api.get<ProxyStats>('/api/v1/proxy/stats');
}

/**
 * Clear all proxies
 */
export async function clearProxies(): Promise<ProxyClearResponse> {
  return api.delete<ProxyClearResponse>('/api/v1/proxy/clear-all');
}

/**
 * Add a single proxy
 */
export async function addProxy(proxy: ProxyCreateRequest): Promise<ProxyInfo> {
  return api.post<ProxyInfo>('/api/v1/proxy/add', proxy);
}

/**
 * Get a single proxy by ID
 */
export async function getProxy(proxyId: number): Promise<ProxyInfo> {
  return api.get<ProxyInfo>(`/api/v1/proxy/${proxyId}`);
}

/**
 * Update a proxy by ID
 */
export async function updateProxy(proxyId: number, data: ProxyUpdateRequest): Promise<ProxyInfo> {
  return api.put<ProxyInfo>(`/api/v1/proxy/${proxyId}`, data);
}

/**
 * Delete a proxy by ID
 */
export async function deleteProxy(proxyId: number): Promise<ProxyDeleteResponse> {
  return api.delete<ProxyDeleteResponse>(`/api/v1/proxy/${proxyId}`);
}

/**
 * Reset failure counts for all proxies
 */
export async function resetProxyFailures(): Promise<ProxyResetFailuresResponse> {
  return api.post<ProxyResetFailuresResponse>('/api/v1/proxy/reset-failures', {});
}

export const proxyApi = {
  uploadProxyCSV,
  getProxyList,
  getProxyStats,
  clearProxies,
  addProxy,
  getProxy,
  updateProxy,
  deleteProxy,
  resetProxyFailures,
};
