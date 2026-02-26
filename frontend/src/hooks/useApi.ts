import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import type { BotStatus, BotCommand, Metrics, HealthCheck } from '@/types/api';
import type { VFSAccount, CreateVFSAccountRequest, UpdateVFSAccountRequest } from '@/types/user';

// Bot queries and mutations
export function useBotStatus() {
  return useQuery<BotStatus>({
    queryKey: ['bot-status'],
    queryFn: () => api.get<BotStatus>('/api/status'),
    refetchInterval: 5000,
  });
}

export function useStartBot() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error, BotCommand>({
    mutationFn: (command) => api.post('/api/v1/bot/start', command),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useStopBot() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post('/api/v1/bot/stop'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useRestartBot() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post('/api/v1/bot/restart'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useCheckNow() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post('/api/v1/bot/check-now'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useMetrics() {
  return useQuery<Metrics>({
    queryKey: ['metrics'],
    queryFn: () => api.get<Metrics>('/metrics'),
    refetchInterval: 30000,
  });
}

export function useHealthCheck() {
  return useQuery<HealthCheck>({
    queryKey: ['health'],
    queryFn: () => api.get<HealthCheck>('/health'),
    refetchInterval: 60000,
  });
}

export function useLogs(limit: number = 100) {
  return useQuery<{ logs: string[] }>({
    queryKey: ['logs', limit],
    queryFn: () => api.get<{ logs: string[] }>('/api/v1/bot/logs', { limit }),
    refetchInterval: 10000,
  });
}

// VFS Account queries and mutations
export function useVFSAccounts() {
  return useQuery<VFSAccount[]>({
    queryKey: ['vfs-accounts'],
    queryFn: () => api.get<VFSAccount[]>('/api/v1/vfs-accounts'),
  });
}

export function useCreateVFSAccount() {
  const queryClient = useQueryClient();
  return useMutation<VFSAccount, Error, CreateVFSAccountRequest>({
    mutationFn: (account) => api.post<VFSAccount>('/api/v1/vfs-accounts', account),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vfs-accounts'] });
    },
  });
}

export function useUpdateVFSAccount() {
  const queryClient = useQueryClient();
  return useMutation<VFSAccount, Error, { id: number } & UpdateVFSAccountRequest>({
    mutationFn: ({ id, ...data }) => api.put<VFSAccount>(`/api/v1/vfs-accounts/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vfs-accounts'] });
    },
  });
}

export function useDeleteVFSAccount() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) => api.delete(`/api/v1/vfs-accounts/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vfs-accounts'] });
    },
  });
}

export function useToggleVFSAccountStatus() {
  const queryClient = useQueryClient();
  return useMutation<VFSAccount, Error, { id: number; is_active: boolean }>({
    mutationFn: ({ id, is_active }) =>
      api.patch<VFSAccount>(`/api/v1/vfs-accounts/${id}`, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vfs-accounts'] });
    },
  });
}
