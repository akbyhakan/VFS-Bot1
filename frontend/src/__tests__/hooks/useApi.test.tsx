import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useBotStatus, useStartBot, useStopBot, useVFSAccounts, useDeleteVFSAccount } from '@/hooks/useApi';
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

      result.current.mutate();

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(api.post).toHaveBeenCalledWith('/api/v1/bot/start');
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
      expect(api.post).toHaveBeenCalledWith('/api/v1/bot/stop');
    });
  });

  describe('useVFSAccounts', () => {
    it('should fetch VFS accounts successfully', async () => {
      const mockAccounts = [
        { id: 1, email: 'account1@test.com', phone: '5551234567', is_active: true },
        { id: 2, email: 'account2@test.com', phone: '5559876543', is_active: false },
      ];
      vi.mocked(api.get).mockResolvedValue(mockAccounts);

      const { result } = renderHook(() => useVFSAccounts(), { wrapper: createWrapper() });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockAccounts);
      expect(api.get).toHaveBeenCalledWith('/api/v1/vfs-accounts');
    });
  });

  describe('useDeleteVFSAccount', () => {
    it('should delete VFS account successfully', async () => {
      vi.mocked(api.delete).mockResolvedValue(undefined);

      const { result } = renderHook(() => useDeleteVFSAccount(), { wrapper: createWrapper() });

      result.current.mutate(1);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(api.delete).toHaveBeenCalledWith('/api/v1/vfs-accounts/1');
    });

    it('should handle delete error', async () => {
      vi.mocked(api.delete).mockRejectedValue(new Error('Delete failed'));

      const { result } = renderHook(() => useDeleteVFSAccount(), { wrapper: createWrapper() });

      result.current.mutate(1);

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeInstanceOf(Error);
    });
  });
});
