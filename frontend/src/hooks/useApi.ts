import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import type { BotStatus, BotCommand, Metrics, HealthCheck } from '@/types/api';
import type { User, CreateUserRequest, UpdateUserRequest } from '@/types/user';

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
    mutationFn: (command) => api.post('/api/bot/start', command),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useStopBot() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post('/api/bot/stop'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useRestartBot() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post('/api/bot/restart'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useCheckNow() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post('/api/bot/check-now'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useMetrics() {
  return useQuery<Metrics>({
    queryKey: ['metrics'],
    queryFn: () => api.get<Metrics>('/api/metrics'),
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
    queryFn: () => api.get<{ logs: string[] }>('/api/logs', { limit }),
    refetchInterval: 10000,
  });
}

// User queries and mutations
export function useUsers() {
  return useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => api.get<User[]>('/api/users'),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation<User, Error, CreateUserRequest>({
    mutationFn: (user) => api.post<User>('/api/users', user),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation<User, Error, { id: number } & UpdateUserRequest>({
    mutationFn: ({ id, ...data }) => api.put<User>(`/api/users/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) => api.delete(`/api/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useToggleUserStatus() {
  const queryClient = useQueryClient();
  return useMutation<User, Error, { id: number; is_active: boolean }>({
    mutationFn: ({ id, is_active }) =>
      api.patch<User>(`/api/users/${id}`, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
