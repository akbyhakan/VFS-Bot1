import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { proxyApi } from '@/services/proxy';

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
