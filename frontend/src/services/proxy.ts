/**
 * Proxy management API service
 */

import api from './api';

export interface ProxyStats {
  total: number;
  active: number;
  failed: number;
}

export interface ProxyInfo {
  endpoint: string;
  host: string;
  port: number;
  username: string;
  status: 'active' | 'failed';
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

  const response = await api.post<UploadProxyResponse>('/api/proxy/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}

/**
 * Get proxy list with statistics
 */
export async function getProxyList(): Promise<ProxyListResponse> {
  const response = await api.get<ProxyListResponse>('/api/proxy/list');
  return response.data;
}

/**
 * Get proxy statistics
 */
export async function getProxyStats(): Promise<ProxyStats> {
  const response = await api.get<ProxyStats>('/api/proxy/stats');
  return response.data;
}

/**
 * Clear all proxies
 */
export async function clearProxies(): Promise<void> {
  await api.delete('/api/proxy/clear');
}

export const proxyApi = {
  uploadProxyCSV,
  getProxyList,
  getProxyStats,
  clearProxies,
};
