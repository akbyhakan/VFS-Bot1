import { api } from './api';
import { REMEMBER_ME_KEY } from '@/utils/constants';
import type { LoginRequest, TokenResponse } from '@/types/api';

export class AuthService {
  async login(credentials: LoginRequest, rememberMe: boolean = false): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/api/auth/login', credentials);
    
    // HttpOnly cookie is automatically set by the server
    // Cookie-based authentication handles all token management
    
    // Store remember me preference
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
    
    // Clear local preferences
    localStorage.removeItem(REMEMBER_ME_KEY);
  }

  shouldRememberUser(): boolean {
    return localStorage.getItem(REMEMBER_ME_KEY) === 'true';
  }
}

export const authService = new AuthService();
