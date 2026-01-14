import { api } from './api';
import { AUTH_TOKEN_KEY, REMEMBER_ME_KEY } from '@/utils/constants';
import type { LoginRequest, TokenResponse } from '@/types/api';

export class AuthService {
  async login(credentials: LoginRequest, rememberMe: boolean = false): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>('/api/auth/login', credentials);
    
    // Store token
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    
    // Store remember me preference
    if (rememberMe) {
      localStorage.setItem(REMEMBER_ME_KEY, 'true');
    } else {
      localStorage.removeItem(REMEMBER_ME_KEY);
    }
    
    return response;
  }

  logout(): void {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(REMEMBER_ME_KEY);
  }

  getToken(): string | null {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  shouldRememberUser(): boolean {
    return localStorage.getItem(REMEMBER_ME_KEY) === 'true';
  }
}

export const authService = new AuthService();
