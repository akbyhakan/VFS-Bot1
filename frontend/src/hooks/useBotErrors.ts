import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import type { BotError, SelectorHealth } from '@/types/botErrors';

export function useBotErrors(limit: number = 20) {
  return useQuery<BotError[]>({
    queryKey: ['bot-errors', limit],
    queryFn: () => api.get<BotError[]>('/api/v1/bot/errors', { limit }),
    refetchInterval: 30000,
  });
}

export function useBotErrorDetail(errorId: string | null) {
  return useQuery<BotError>({
    queryKey: ['bot-error', errorId],
    queryFn: () => api.get<BotError>(`/api/v1/bot/errors/${errorId}`),
    enabled: !!errorId,
  });
}

export function useSelectorHealth() {
  return useQuery<SelectorHealth>({
    queryKey: ['selector-health'],
    queryFn: () => api.get<SelectorHealth>('/api/v1/bot/selector-health'),
    refetchInterval: 60000,
  });
}

export function getErrorScreenshotUrl(errorId: string, type: 'full' | 'element' = 'full'): string {
  return `/api/v1/bot/errors/${errorId}/screenshot?type=${type}`;
}

export function getErrorHtmlSnapshotUrl(errorId: string): string {
  return `/api/v1/bot/errors/${errorId}/html-snapshot`;
}
