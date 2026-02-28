import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAuth } from '@/hooks/useAuth';
import { useAuthStore } from '@/store/authStore';
import { authService } from '@/services/auth';
import { api } from '@/services/api';

vi.mock('@/services/auth', () => ({
  authService: {
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
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
      username: null,
    });
  });

  it('should return authentication state', () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current).toHaveProperty('isAuthenticated');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('username');
    expect(result.current).toHaveProperty('login');
    expect(result.current).toHaveProperty('logout');
    expect(result.current).toHaveProperty('checkAuth');
    expect(result.current).toHaveProperty('clearError');
  });

  it('should handle successful login', async () => {
    vi.mocked(authService.login).mockResolvedValue({
      message: 'Login successful',
      user: { username: 'test' },
    });

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
    expect(result.current.username).toBe('test');
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
    useAuthStore.setState({ isAuthenticated: true, username: 'test' });
    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.logout();
    });

    expect(authService.logout).toHaveBeenCalled();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.username).toBe(null);
  });

  it('should check authentication status', async () => {
    vi.mocked(api.get).mockResolvedValue({ username: 'test' });

    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.checkAuth();
    });

    expect(api.get).toHaveBeenCalledWith('/api/v1/auth/me');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.username).toBe('test');
  });

  it('should handle failed checkAuth', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Unauthorized'));

    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.checkAuth();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.username).toBe(null);
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
