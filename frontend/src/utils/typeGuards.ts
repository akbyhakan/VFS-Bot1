/**
 * Runtime type checking utilities
 * Provides type guards for safe runtime validation
 */

import type { WebSocketMessage, LogEntry } from '@/types/api';

/**
 * Type guard for bot status data
 */
export function isBotStatusData(data: unknown): data is {
  running?: boolean;
  status?: string;
  last_check?: string | null;
  stats?: {
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
} {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const obj = data as Record<string, unknown>;

  // Check optional fields
  if (obj.running !== undefined && typeof obj.running !== 'boolean') {
    return false;
  }

  if (obj.status !== undefined && typeof obj.status !== 'string') {
    return false;
  }

  if (obj.last_check !== undefined && obj.last_check !== null && typeof obj.last_check !== 'string') {
    return false;
  }

  if (obj.stats !== undefined) {
    if (!obj.stats || typeof obj.stats !== 'object') {
      return false;
    }
    const stats = obj.stats as Record<string, unknown>;
    if (
      typeof stats.slots_found !== 'number' ||
      typeof stats.appointments_booked !== 'number' ||
      typeof stats.active_users !== 'number'
    ) {
      return false;
    }
  }

  return true;
}

/**
 * Type guard for log entry
 */
export function isLogEntry(data: unknown): data is LogEntry {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const obj = data as Record<string, unknown>;

  return (
    typeof obj.message === 'string' &&
    typeof obj.level === 'string' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Type guard for WebSocket message
 */
export function isWebSocketMessage(data: unknown): data is WebSocketMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const obj = data as Record<string, unknown>;

  return typeof obj.type === 'string' && obj.data !== undefined;
}

/**
 * Type guard for stats data
 */
export function isStatsData(data: unknown): data is {
  slots_found: number;
  appointments_booked: number;
  active_users: number;
} {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const obj = data as Record<string, unknown>;

  return (
    typeof obj.slots_found === 'number' &&
    typeof obj.appointments_booked === 'number' &&
    typeof obj.active_users === 'number'
  );
}
