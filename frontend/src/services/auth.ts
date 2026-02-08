import { api } from './api';
import { REMEMBER_ME_KEY } from '@/utils/constants';
import { tokenManager } from '@/utils/tokenManager';
import type { LoginRequest, TokenResponse } from '@/types/api';

export class AuthService {
  async login(credentials: LoginRequest, rememberMe: boolean = false): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/api/auth/login', credentials);
    
    // HttpOnly cookie is automatically set by the server
    // Store token in localStorage/sessionStorage as fallback for backward compatibility
    tokenManager.setToken(response.access_token, rememberMe);
    
    // Store remember me preference (for compatibility)
    if (rememberMe) {
      localStorage.setItem(REMEMBER_ME_KEY, 'true');
    } else {
      localStorage.removeItem(REMEMBER_ME_KEY);
    }
    
    return response;
  }

  async logout(): Promise<void> {
    // Call logout endpoint to clear HttpOnly cookie
    try {
      await api.post('/api/auth/logout');
    } catch (error) {
      // Log error with context for debugging authentication flow issues
      // In production, this should be sent to a proper error tracking service
      console.error('Logout API call failed - continuing with local cleanup:', {
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString(),
      });
    }
    
    // Clear local storage
    tokenManager.clearToken();
    localStorage.removeItem(REMEMBER_ME_KEY);
  }

  getToken(): string | null {
    return tokenManager.getToken();
  }

  isAuthenticated(): boolean {
    return tokenManager.hasToken();
  }

  shouldRememberUser(): boolean {
    return localStorage.getItem(REMEMBER_ME_KEY) === 'true';
  }
}

export const authService = new AuthService();
