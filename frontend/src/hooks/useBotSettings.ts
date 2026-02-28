import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getBotSettings, updateBotSettings } from '@/services/bot';
import type { BotSettingsResponse, BotSettingsUpdate, BotSettingsUpdateResponse } from '@/services/bot';

/**
 * Hook to fetch current bot settings (cooldown, quarantine, max_failures).
 * GET /api/v1/bot/settings
 */
export function useBotSettings() {
  return useQuery<BotSettingsResponse>({
    queryKey: ['bot-settings'],
    queryFn: getBotSettings,
    staleTime: 60000, // 1 minute - settings don't change often
  });
}

/**
 * Hook to update bot settings.
 * PUT /api/v1/bot/settings
 */
export function useUpdateBotSettings() {
  const queryClient = useQueryClient();
  return useMutation<BotSettingsUpdateResponse, Error, BotSettingsUpdate>({
    mutationFn: updateBotSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-settings'] });
    },
  });
}
