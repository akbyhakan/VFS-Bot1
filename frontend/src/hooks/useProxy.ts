import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { proxyApi } from '@/services/proxy';
import type { ProxyCreateRequest, ProxyUpdateRequest } from '@/services/proxy';

export function useProxyStats() {
  return useQuery({
    queryKey: ['proxy-stats'],
    queryFn: () => proxyApi.getProxyStats(),
  });
}

export function useProxyList() {
  return useQuery({
    queryKey: ['proxy-list'],
    queryFn: () => proxyApi.getProxyList(),
  });
}

export function useUploadProxy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => proxyApi.uploadProxyCSV(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxy-stats'] });
      queryClient.invalidateQueries({ queryKey: ['proxy-list'] });
    },
  });
}

export function useClearProxies() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => proxyApi.clearProxies(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxy-stats'] });
      queryClient.invalidateQueries({ queryKey: ['proxy-list'] });
    },
  });
}

export function useAddProxy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proxy: ProxyCreateRequest) => proxyApi.addProxy(proxy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxy-stats'] });
      queryClient.invalidateQueries({ queryKey: ['proxy-list'] });
    },
  });
}

export function useProxy(proxyId: number) {
  return useQuery({
    queryKey: ['proxy', proxyId],
    queryFn: () => proxyApi.getProxy(proxyId),
  });
}

export function useUpdateProxy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ proxyId, data }: { proxyId: number; data: ProxyUpdateRequest }) =>
      proxyApi.updateProxy(proxyId, data),
    onSuccess: (_data, { proxyId }) => {
      queryClient.invalidateQueries({ queryKey: ['proxy-stats'] });
      queryClient.invalidateQueries({ queryKey: ['proxy-list'] });
      queryClient.invalidateQueries({ queryKey: ['proxy', proxyId] });
    },
  });
}

export function useDeleteProxy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proxyId: number) => proxyApi.deleteProxy(proxyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxy-stats'] });
      queryClient.invalidateQueries({ queryKey: ['proxy-list'] });
    },
  });
}

export function useResetProxyFailures() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => proxyApi.resetProxyFailures(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxy-stats'] });
      queryClient.invalidateQueries({ queryKey: ['proxy-list'] });
    },
  });
}
