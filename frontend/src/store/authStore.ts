import { create } from 'zustand';
import { api } from '@/services/api';
import { authService } from '@/services/auth';
import { logger } from '@/utils/logger';
import type { LoginRequest } from '@/types/api';

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  username: string | null;
  login: (credentials: LoginRequest, rememberMe?: boolean) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  isLoading: false,
  error: null,
  username: null,

  login: async (credentials, rememberMe = false) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.login(credentials, rememberMe);
      set({ isAuthenticated: true, isLoading: false, username: response.user.username });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Giriş başarısız';
      set({ error: message, isLoading: false, isAuthenticated: false });
      throw error;
    }
  },

  logout: async () => {
    await authService.logout();
    set({ isAuthenticated: false, error: null, username: null });
  },

  checkAuth: async () => {
    try {
      const data = await api.get<{ username: string }>('/api/v1/auth/me');
      set({ isAuthenticated: true, username: data.username });
    } catch (error) {
      logger.debug('checkAuth failed - user not authenticated:', error instanceof Error ? error.message : 'Unknown error');
      set({ isAuthenticated: false, username: null });
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));
