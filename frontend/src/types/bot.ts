// NOTE: Bot configuration (check_interval, headless, notifications, etc.) is managed
// via config.yaml on the backend. Frontend only manages user-facing bot settings
// through the backend API (see BotSettingsResponse in services/bot.ts).

export type BotStatusType = 'running' | 'stopped' | 'idle' | 'error';

export interface BotState {
  status: BotStatusType;
  running: boolean;
  last_check: string | null;
  stats: {
    slots_found: number;
    appointments_booked: number;
    active_users: number;
  };
}
