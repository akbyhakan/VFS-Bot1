import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import type { AuditLog, AuditStats, AuditLogFilters } from '@/types/audit';

export type { AuditLog, AuditStats, AuditLogFilters };

/**
 * Hook to fetch audit logs with optional filters
 */
export function useAuditLogs(filters?: AuditLogFilters) {
  return useQuery<AuditLog[]>({
    queryKey: ['audit-logs', filters],
    queryFn: () => {
      const params = new URLSearchParams();
      
      if (filters?.limit) params.append('limit', filters.limit.toString());
      if (filters?.action) params.append('action', filters.action);
      if (filters?.user_id) params.append('user_id', filters.user_id.toString());
      if (filters?.success !== undefined) params.append('success', filters.success.toString());
      
      const queryString = params.toString();
      const url = queryString ? `/api/v1/audit/logs?${queryString}` : '/api/v1/audit/logs';
      
      return api.get<AuditLog[]>(url);
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

/**
 * Hook to fetch a single audit log entry by ID
 */
export function useAuditLogDetail(id: number | null) {
  return useQuery<AuditLog>({
    queryKey: ['audit-log', id],
    queryFn: () => api.get<AuditLog>(`/api/v1/audit/logs/${id}`),
    enabled: id !== null && id > 0,
  });
}

/**
 * Hook to fetch audit log statistics
 */
export function useAuditStats() {
  return useQuery<AuditStats>({
    queryKey: ['audit-stats'],
    queryFn: () => api.get<AuditStats>('/api/v1/audit/stats'),
    refetchInterval: 60000, // Refresh every minute
  });
}
