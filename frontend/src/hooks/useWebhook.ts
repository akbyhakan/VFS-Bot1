import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { webhookApi } from '@/services/webhook';

export function useWebhookUrls() {
  return useQuery({
    queryKey: ['webhook-urls'],
    queryFn: () => webhookApi.getWebhookUrls(),
  });
}

export function useUserWebhook(userId: number | undefined) {
  return useQuery({
    queryKey: ['user-webhook', userId],
    queryFn: () => webhookApi.getWebhook(userId!),
    enabled: !!userId,
  });
}

export function useCreateWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => webhookApi.createWebhook(userId),
    onSuccess: (_data, userId) => {
      queryClient.invalidateQueries({ queryKey: ['user-webhook', userId] });
    },
  });
}

export function useDeleteWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => webhookApi.deleteWebhook(userId),
    onSuccess: (_data, userId) => {
      queryClient.invalidateQueries({ queryKey: ['user-webhook', userId] });
    },
  });
}
