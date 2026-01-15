import { useAuthStore } from '@/store/authStore';

export function useAuth() {
  const { isAuthenticated, isLoading, error, login, logout, checkAuth, clearError } =
    useAuthStore();

  return {
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    checkAuth,
    clearError,
  };
}
