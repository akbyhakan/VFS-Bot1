export interface AuditLog {
  id: number;
  action: string;
  user_id: number | null;
  username: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: string | null;
  timestamp: string;
  success: boolean;
  resource_type: string | null;
  resource_id: string | null;
}

export interface AuditStats {
  total: number;
  by_action: Record<string, number>;
  success_rate: number;
  recent_failures: number;
}

export interface AuditLogFilters {
  limit?: number;
  action?: string;
  user_id?: number;
  success?: boolean;
}
