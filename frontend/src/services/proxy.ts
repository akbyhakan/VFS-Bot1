/**
 * Proxy management API service
 */

import { api } from './api';
import axios from 'axios';
import { API_BASE_URL } from '@/utils/constants';
import { tokenManager } from '@/utils/tokenManager';

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

  const token = tokenManager.getToken();
  const response = await axios.post<UploadProxyResponse>(
    `${API_BASE_URL}/api/proxy/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }
  );

  return response.data;
}

/**
 * Get proxy list with statistics
 */
export async function getProxyList(): Promise<ProxyListResponse> {
  return api.get<ProxyListResponse>('/api/proxy/list');
}

/**
 * Get proxy statistics
 */
export async function getProxyStats(): Promise<ProxyStats> {
  return api.get<ProxyStats>('/api/proxy/stats');
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
