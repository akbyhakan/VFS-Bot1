import { BOT_STATUS } from '@/utils/constants';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  message: string;
  user: {
    username: string;
  };
}

export type BotStatusType = (typeof BOT_STATUS)[keyof typeof BOT_STATUS];

export interface BotStatus {
  running: boolean;
  status: BotStatusType;
  last_check: string | null;
  stats: {
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
}

export interface LogEntry {
  message: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
  timestamp: string;
}

export interface Metrics {
  uptime_seconds: number;
  requests_total: number;
  requests_success: number;
  requests_failed: number;
  success_rate: number;
  slots_checked: number;
  slots_found: number;
  appointments_booked: number;
  captchas_solved: number;
  errors_by_type: Record<string, number>;
  bot_status: string;
  circuit_breaker_trips: number;
  active_users: number;
  avg_response_time_ms: number;
  requests_per_minute: number;
}

export interface HealthCheck {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  uptime_seconds: number;
  components: {
    database: {
      status: string;
      latency_ms?: number;
      pool?: {
        size: number;
        idle: number;
        used: number;
        utilization: number;
      };
    };
    redis: { status: string; backend?: string };
    bot: { status: string; running: boolean; success_rate: number };
    circuit_breaker: { status: string; trips: number };
    notifications: { status: string };
    proxy: {
      status: string;
      total_proxies?: number;
      active_proxies?: number;
      inactive_proxies?: number;
      avg_failure_count?: number;
    };
  };
  metrics: {
    total_checks: number;
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
}

export interface BotStatusData {
  running?: boolean;
  status?: string;
  last_check?: string | null;
  message?: string;
  stats?: {
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
}

export interface StatsData {
  slots_found: number;
  appointments_booked: number;
  active_users: number;
}

export interface NotificationData {
  message: string;
  level?: 'info' | 'warning' | 'error' | 'success';
  title?: string;
}

export interface CriticalNotificationData {
  title: string;
  message: string;
  timestamp: number;
  priority: 'high' | 'normal';
}

export interface WebSocketErrorData {
  code?: number;
  message: string;
  recoverable?: boolean;
}

export type WebSocketMessage =
  | { type: 'status'; data: BotStatusData }
  | { type: 'log'; data: LogEntry }
  | { type: 'stats'; data: StatsData }
  | { type: 'notification'; data: NotificationData }
  | { type: 'critical_notification'; data: CriticalNotificationData }
  | { type: 'error'; data: WebSocketErrorData }
  | { type: 'ping'; data: Record<string, unknown> }
  | { type: 'ack'; data: Record<string, unknown> };

export interface ApiError {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  // Extension members
  recoverable?: boolean;
  retry_after?: number;
  field?: string;
  errors?: Record<string, string>;
}

export interface RuntimeConfigResponse {
  success: boolean;
  message: string;
  config: Record<string, number | string | boolean>;
}

export interface RuntimeConfigUpdateRequest {
  /** Configuration key in `'category.parameter'` format (must contain a dot). */
  key: string;
  value: number | string | boolean;
}
