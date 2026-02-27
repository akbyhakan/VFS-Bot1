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
export async function clearProxies(): Promise<void> {
  await api.delete('/api/v1/proxy/clear-all');
}

export const proxyApi = {
  uploadProxyCSV,
  getProxyList,
  getProxyStats,
  clearProxies,
};
