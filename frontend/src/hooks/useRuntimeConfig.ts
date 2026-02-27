import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRuntimeConfig, updateRuntimeConfig } from '@/services/runtimeConfig';
import type { RuntimeConfigResponse, RuntimeConfigUpdateRequest } from '@/types/api';

export function useRuntimeConfig() {
  return useQuery<RuntimeConfigResponse>({
    queryKey: ['runtime-config'],
    queryFn: getRuntimeConfig,
    staleTime: 30000,
  });
}

export function useUpdateRuntimeConfig() {
  const queryClient = useQueryClient();
  return useMutation<RuntimeConfigResponse, Error, RuntimeConfigUpdateRequest>({
    mutationFn: updateRuntimeConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runtime-config'] });
    },
  });
}
