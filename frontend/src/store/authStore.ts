import { create } from 'zustand';
import { authService } from '@/services/auth';
import type { LoginRequest } from '@/types/api';

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginRequest, rememberMe?: boolean) => Promise<void>;
  logout: () => void;
  checkAuth: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: authService.isAuthenticated(),
  isLoading: false,
  error: null,

  login: async (credentials, rememberMe = false) => {
    set({ isLoading: true, error: null });
    try {
      await authService.login(credentials, rememberMe);
      set({ isAuthenticated: true, isLoading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Giriş başarısız';
      set({ error: message, isLoading: false, isAuthenticated: false });
      throw error;
    }
  },

  logout: () => {
    authService.logout();
    set({ isAuthenticated: false, error: null });
  },

  checkAuth: () => {
    const isAuthenticated = authService.isAuthenticated();
    set({ isAuthenticated });
  },

  clearError: () => {
    set({ error: null });
  },
}));
