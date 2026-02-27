import { api } from './api';

export interface BotSettingsResponse {
  cooldown_minutes: number;
  cooldown_seconds: number;
  quarantine_minutes: number;
  max_failures: number;
}

export interface BotSettingsUpdate {
  cooldown_minutes: number;
  quarantine_minutes?: number;
  max_failures?: number;
}

export interface BotSettingsUpdateResponse {
  status: string;
  message: string;
}

/**
 * Get current bot settings
 */
export async function getBotSettings(): Promise<BotSettingsResponse> {
  return api.get<BotSettingsResponse>('/api/v1/bot/settings');
}

/**
 * Update bot settings
 */
export async function updateBotSettings(settings: BotSettingsUpdate): Promise<BotSettingsUpdateResponse> {
  return api.put<BotSettingsUpdateResponse>('/api/v1/bot/settings', settings);
}
