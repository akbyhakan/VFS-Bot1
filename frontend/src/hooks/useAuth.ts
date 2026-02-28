import { useAuthStore } from '@/store/authStore';

export function useAuth() {
  const { isAuthenticated, isLoading, error, username, login, logout, checkAuth, clearError } =
    useAuthStore();

  return {
    isAuthenticated,
    isLoading,
    error,
    username,
    login,
    logout,
    checkAuth,
    clearError,
  };
}
