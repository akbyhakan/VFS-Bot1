import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useBotStatus, useStartBot, useStopBot, useUsers } from '@/hooks/useApi';
import { api } from '@/services/api';
import { type ReactNode } from 'react';

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('useApi hooks', () => {
  let queryClient: QueryClient;

  const createWrapper = () => {
    return function Wrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    };
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  describe('useBotStatus', () => {
    it('should fetch bot status successfully', async () => {
      const mockStatus = {
        status: 'running',
        uptime: 1000,
        last_check: '2024-01-01T00:00:00Z',
      };
      vi.mocked(api.get).mockResolvedValue(mockStatus);

      const { result } = renderHook(() => useBotStatus(), { wrapper: createWrapper() });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockStatus);
      expect(api.get).toHaveBeenCalledWith('/api/status');
    });

    it('should handle bot status fetch error', async () => {
      vi.mocked(api.get).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useBotStatus(), { wrapper: createWrapper() });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeInstanceOf(Error);
    });
  });

  describe('useStartBot', () => {
    it('should start bot successfully', async () => {
      const mockResponse = { status: 'success', message: 'Bot started' };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useStartBot(), { wrapper: createWrapper() });

      result.current.mutate({ action: 'start' });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(api.post).toHaveBeenCalledWith('/api/bot/start', {
        action: 'start',
      });
    });
  });

  describe('useStopBot', () => {
    it('should stop bot successfully', async () => {
      const mockResponse = { status: 'success', message: 'Bot stopped' };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useStopBot(), { wrapper: createWrapper() });

      result.current.mutate();

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(api.post).toHaveBeenCalledWith('/api/bot/stop');
    });
  });

  describe('useUsers', () => {
    it('should fetch users successfully', async () => {
      const mockUsers = [
        { id: 1, username: 'user1', email: 'user1@test.com', is_active: true },
        { id: 2, username: 'user2', email: 'user2@test.com', is_active: false },
      ];
      vi.mocked(api.get).mockResolvedValue(mockUsers);

      const { result } = renderHook(() => useUsers(), { wrapper: createWrapper() });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockUsers);
      expect(api.get).toHaveBeenCalledWith('/api/users');
    });
  });
});
