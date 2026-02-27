import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '@/utils/constants';
import type { ApiError } from '@/types/api';
import { AppError } from '@/utils/AppError';

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
      withCredentials: true,  // Send HttpOnly cookies with every request
    });

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
                return this.client(originalRequest);
              })
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            // Attempt to refresh the token via cookie-based refresh endpoint
            await this.refreshToken();

            // Process queued requests - new cookie is set automatically
            this.failedQueue.forEach((prom) => prom.resolve());
            this.failedQueue = [];

            // Retry original request - cookie is sent automatically
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed, clear queue and logout
            this.failedQueue.forEach((prom) => prom.reject(refreshError));
            this.failedQueue = [];

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

  private async refreshToken(): Promise<void> {
    try {
      // Refresh endpoint will set new HttpOnly cookie automatically
      await this.client.post('/api/v1/auth/refresh');
    } catch (error) {
      throw new Error('Token refresh failed');
    }
  }

  private handleError(error: AxiosError<ApiError>): AppError {
    const data = error.response?.data;
    const message =
      data?.detail ?? error.message ?? 'Bilinmeyen bir hata oluştu';
    return new AppError(message, {
      type: data?.type,
      title: data?.title,
      status: data?.status ?? error.response?.status,
      recoverable: data?.recoverable,
      retryAfter: data?.retry_after,
      field: data?.field,
      fieldErrors: data?.errors,
    });
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
