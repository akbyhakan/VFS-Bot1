import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';

export interface DropdownSyncStatus {
  country_code: string;
  sync_status: 'pending' | 'syncing' | 'completed' | 'failed';
  last_synced_at: string | null;
  error_message: string | null;
}

/**
 * Hook to fetch all dropdown sync statuses
 */
export function useDropdownSyncStatuses() {
  return useQuery<DropdownSyncStatus[]>({
    queryKey: ['dropdown-sync-statuses'],
    queryFn: () => api.get<DropdownSyncStatus[]>('/api/v1/dropdown-sync/status'),
    refetchInterval: 5000, // Poll every 5 seconds to show live updates during sync
  });
}

/**
 * Hook to fetch sync status for a specific country
 */
export function useDropdownSyncStatus(countryCode: string) {
  return useQuery<DropdownSyncStatus>({
    queryKey: ['dropdown-sync-status', countryCode],
    queryFn: () => api.get<DropdownSyncStatus>(`/api/v1/dropdown-sync/${countryCode}/status`),
    enabled: !!countryCode,
    refetchInterval: 5000,
  });
}

/**
 * Hook to trigger sync for a specific country
 */
export function useTriggerCountrySync() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (countryCode: string) => 
      api.post(`/api/v1/dropdown-sync/${countryCode}`, {}),
    onSuccess: () => {
      // Invalidate and refetch sync statuses
      queryClient.invalidateQueries({ queryKey: ['dropdown-sync-statuses'] });
    },
  });
}

/**
 * Hook to trigger sync for all countries
 */
export function useTriggerAllSync() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => api.post('/api/v1/dropdown-sync/all', {}),
    onSuccess: () => {
      // Invalidate and refetch sync statuses
      queryClient.invalidateQueries({ queryKey: ['dropdown-sync-statuses'] });
    },
  });
}
