import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAuth } from '@/hooks/useAuth';
import { useAuthStore } from '@/store/authStore';
import { authService } from '@/services/auth';

vi.mock('@/services/auth', () => ({
  authService: {
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state
    useAuthStore.setState({
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  it('should return authentication state', () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current).toHaveProperty('isAuthenticated');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('login');
    expect(result.current).toHaveProperty('logout');
    expect(result.current).toHaveProperty('checkAuth');
    expect(result.current).toHaveProperty('clearError');
  });

  it('should handle successful login', async () => {
    const mockTokenResponse = { access_token: 'token123', token_type: 'bearer' };
    vi.mocked(authService.login).mockResolvedValue(mockTokenResponse);

    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.login({ username: 'test', password: 'password' });
    });

    expect(authService.login).toHaveBeenCalledWith(
      { username: 'test', password: 'password' },
      false
    );
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.error).toBe(null);
  });

  it('should handle login error', async () => {
    const error = new Error('Invalid credentials');
    vi.mocked(authService.login).mockRejectedValue(error);

    const { result } = renderHook(() => useAuth());

    try {
      await act(async () => {
        await result.current.login({ username: 'test', password: 'wrong' });
      });
    } catch (e) {
      // Expected to throw
      expect(result.current.isAuthenticated).toBe(false);
    }
  });

  it('should handle logout', async () => {
    useAuthStore.setState({ isAuthenticated: true });
    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.logout();
    });

    expect(authService.logout).toHaveBeenCalled();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('should check authentication status', () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.checkAuth();
    });

    // checkAuth is now a no-op, so state should remain unchanged
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('should clear error', () => {
    useAuthStore.setState({ error: 'Some error' });
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBe(null);
  });
});
