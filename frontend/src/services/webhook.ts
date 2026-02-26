import { api } from './api';
import type { WebhookUrls } from '@/types/payment';

interface WebhookResponse {
  token: string;
  webhook_url: string;
  message: string;
}

interface WebhookInfoResponse {
  webhook: {
    token: string;
    webhook_url: string;
    created_at: string;
  } | null;
}

interface DeleteWebhookResponse {
  message: string;
}

export const webhookApi = {
  /**
   * Create a webhook for a user
   */
  createWebhook: async (userId: number): Promise<WebhookResponse> => {
    return await api.post<WebhookResponse>(`/api/webhook/users/${userId}/create`);
  },

  /**
   * Get webhook information for a user
   */
  getWebhook: async (userId: number): Promise<WebhookInfoResponse> => {
    return await api.get<WebhookInfoResponse>(`/api/webhook/users/${userId}`);
  },

  /**
   * Delete a user's webhook
   */
  deleteWebhook: async (userId: number): Promise<DeleteWebhookResponse> => {
    return await api.delete<DeleteWebhookResponse>(`/api/webhook/users/${userId}`);
  },

  /**
   * Get webhook URLs for SMS forwarding
   */
  getWebhookUrls: async (): Promise<WebhookUrls> => {
    return await api.get<WebhookUrls>('/api/v1/appointments/settings/webhook-urls');
  },
};
