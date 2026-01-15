/**
 * Payment card API methods
 */

import { api } from './api';
import type { PaymentCard, PaymentCardRequest, WebhookUrls } from '@/types/payment';

export const paymentCardApi = {
  /**
   * Get the saved payment card (masked)
   */
  async getPaymentCard(): Promise<PaymentCard | null> {
    try {
      const card = await api.get<PaymentCard>('/api/payment-card');
      return card;
    } catch (error) {
      // Return null if no card exists (404)
      if (error instanceof Error && error.message.includes('404')) {
        return null;
      }
      throw error;
    }
  },

  /**
   * Save or update payment card
   */
  async savePaymentCard(
    cardData: PaymentCardRequest
  ): Promise<{ success: boolean; card_id: number; message: string }> {
    return await api.post('/api/payment-card', cardData);
  },

  /**
   * Delete the saved payment card
   */
  async deletePaymentCard(): Promise<{ success: boolean; message: string }> {
    return await api.delete('/api/payment-card');
  },
};

export const webhookApi = {
  /**
   * Get webhook URLs for SMS forwarding
   */
  async getWebhookUrls(): Promise<WebhookUrls> {
    return await api.get<WebhookUrls>('/api/settings/webhook-urls');
  },
};
