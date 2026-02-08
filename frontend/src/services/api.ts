import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '@/utils/constants';
import { tokenManager } from '@/utils/tokenManager';
import type { ApiError } from '@/types/api';

// Default timeout: 30 seconds
const DEFAULT_TIMEOUT = 30000;

// Extended config type for retry tracking
interface ExtendedAxiosRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

class ApiClient {
  private client: AxiosInstance;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value?: unknown) => void;
    reject: (reason?: unknown) => void;
  }> = [];

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: DEFAULT_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,  // Send cookies with every request (for HttpOnly cookie auth)
    });

    // Request interceptor to add auth token
    // Note: Primary auth is via HttpOnly cookie (automatically sent by browser).
    // Authorization header is kept for backward compatibility with API clients.
    this.client.interceptors.request.use(
      (config) => {
        const token = tokenManager.getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling with token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ApiError>) => {
        const originalRequest = error.config as ExtendedAxiosRequestConfig;

        if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
          if (this.isRefreshing) {
            // If already refreshing, queue this request
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then(() => {
                originalRequest.headers.Authorization = `Bearer ${tokenManager.getToken()}`;
                return this.client(originalRequest);
              })
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            // Attempt to refresh the token
            const newToken = await this.refreshToken();
            tokenManager.setToken(newToken);

            // Process queued requests with new token
            this.failedQueue.forEach((prom) => prom.resolve());
            this.failedQueue = [];

            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed, clear queue and logout
            this.failedQueue.forEach((prom) => prom.reject(refreshError));
            this.failedQueue = [];

            tokenManager.clearToken();
            // Only redirect if not already on login page to prevent infinite loop
            if (!window.location.pathname.includes('/login')) {
              window.location.href = '/login';
            }
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(this.handleError(error));
      }
    );
  }

  private async refreshToken(): Promise<string> {
    try {
      const response = await this.client.post<{ access_token: string }>('/api/auth/refresh');
      return response.data.access_token;
    } catch (error) {
      throw new Error('Token refresh failed');
    }
  }

  private handleError(error: AxiosError<ApiError>): Error {
    if (error.response?.data?.detail) {
      return new Error(error.response.data.detail);
    }
    if (error.message) {
      return new Error(error.message);
    }
    return new Error('Bilinmeyen bir hata oluştu');
  }

  async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  async put<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }

  async patch<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }
}

export const api = new ApiClient();
