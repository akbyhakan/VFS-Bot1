import { api } from './api';
import { REMEMBER_ME_KEY } from '@/utils/constants';
import { tokenManager } from '@/utils/tokenManager';
import type { LoginRequest, TokenResponse } from '@/types/api';

export class AuthService {
  async login(credentials: LoginRequest, rememberMe: boolean = false): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/api/auth/login', credentials);
    
    // Store token using tokenManager
    tokenManager.setToken(response.access_token, rememberMe);
    
    // Store remember me preference (for compatibility)
    if (rememberMe) {
      localStorage.setItem(REMEMBER_ME_KEY, 'true');
    } else {
      localStorage.removeItem(REMEMBER_ME_KEY);
    }
    
    return response;
  }

  logout(): void {
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
