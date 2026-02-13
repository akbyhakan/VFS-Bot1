export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || '';

export const REMEMBER_ME_KEY = 'vfs_bot_remember';

export const ROUTES = {
  LOGIN: '/login',
  DASHBOARD: '/',
  USERS: '/users',
  SETTINGS: '/settings',
  LOGS: '/logs',
  APPOINTMENTS: '/appointments',
  SYSTEM_HEALTH: '/system',
  AUDIT_LOGS: '/audit-logs',
} as const;

export const LOG_LEVELS = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARNING: 'WARNING',
  ERROR: 'ERROR',
  SUCCESS: 'SUCCESS',
} as const;

export const BOT_STATUS = {
  RUNNING: 'running',
  STOPPED: 'stopped',
  IDLE: 'idle',
  ERROR: 'error',
} as const;

export const REFRESH_INTERVALS = {
  STATUS: 5000, // 5 seconds
  LOGS: 10000, // 10 seconds
  METRICS: 30000, // 30 seconds
} as const;

export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100],
} as const;

export const WEBSOCKET_RECONNECT = {
  MAX_ATTEMPTS: 5,
  INITIAL_DELAY: 1000,
  MAX_DELAY: 30000,
  BACKOFF_MULTIPLIER: 2,
} as const;

export const WEBSOCKET_THROTTLE = {
  LOG_BUFFER_TIME: 100, // ms - buffer logs for batch addition
  STATUS_THROTTLE_TIME: 500, // ms - throttle status updates
} as const;

export const VISA_CATEGORIES = [
  'Tourist',
  'Business',
  'Student',
  'Work',
  'Family',
  'Transit',
] as const;

export const CENTER_NAMES = [
  'Istanbul',
  'Ankara',
  'Izmir',
  'Antalya',
  'Bursa',
] as const;
