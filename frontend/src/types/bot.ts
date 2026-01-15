export interface BotSettings {
  check_interval: number;
  headless_mode: boolean;
  max_retries: number;
  timeout: number;
  anti_detection: AntiDetectionSettings;
  proxy: ProxySettings;
  notifications: NotificationSettings;
}

export interface AntiDetectionSettings {
  enabled: boolean;
  canvas_noise: boolean;
  webgl_vendor_override: boolean;
  audio_context_randomization: boolean;
  mouse_movement_simulation: boolean;
  typing_simulation: boolean;
}

export interface ProxySettings {
  enabled: boolean;
  proxy_file: string;
  rotation_enabled: boolean;
  failover_enabled: boolean;
}

export interface NotificationSettings {
  telegram: TelegramSettings;
  email: EmailSettings;
}

export interface TelegramSettings {
  enabled: boolean;
  bot_token: string;
  chat_id: string;
  notifications_on_slot_found: boolean;
  notifications_on_appointment_booked: boolean;
  notifications_on_error: boolean;
}

export interface EmailSettings {
  enabled: boolean;
  sender: string;
  receiver: string;
  smtp_server: string;
  smtp_port: number;
  use_tls: boolean;
  notifications_on_slot_found: boolean;
  notifications_on_appointment_booked: boolean;
  notifications_on_error: boolean;
}

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
