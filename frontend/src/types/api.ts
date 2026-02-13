export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface BotStatus {
  running: boolean;
  status: 'running' | 'stopped' | 'idle';
  last_check: string | null;
  stats: {
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
}

export interface BotCommand {
  action: 'start' | 'stop';
  config?: Record<string, unknown>;
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
  };
  metrics: {
    total_checks: number;
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
}

export interface WebSocketMessage {
  type: 'status' | 'log' | 'stats' | 'ping' | 'ack';
  data: Record<string, unknown>;
}

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
