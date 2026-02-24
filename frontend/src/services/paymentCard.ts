/**
 * Payment card API methods
 */

import { api } from './api';
import type { PaymentCard, PaymentCardRequest, WebhookUrls } from '@/types/payment';
import { isApiError } from '@/utils/typeGuards';

export const paymentCardApi = {
  /**
   * Get the saved payment card (masked)
   */
  async getPaymentCard(): Promise<PaymentCard | null> {
    try {
      const card = await api.get<PaymentCard>('/api/v1/payment/payment-card');
      return card;
    } catch (error: unknown) {
      // Return null if no card exists (404) or if card is explicitly null
      if (isApiError(error)) {
        if (error.response?.status === 404 || error.response?.data === null) {
          return null;
        }
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
    try {
      return await api.post('/api/v1/payment/payment-card', cardData);
    } catch (error: unknown) {
      // Handle 422 validation errors from Pydantic
      if (isApiError(error) && error.response?.status === 422) {
        const detail = error.response.data?.detail;
        if (Array.isArray(detail)) {
          // Extract field-specific validation errors
          const fieldErrors = detail
            .map((err: { loc: string[]; msg: string }) => {
              const field = err.loc[err.loc.length - 1];
              return `${field}: ${err.msg}`;
            })
            .join('; ');
          throw new Error(`Validation error: ${fieldErrors}`);
        }
      }
      throw error;
    }
  },

  /**
   * Delete the saved payment card
   */
  async deletePaymentCard(): Promise<{ success: boolean; message: string }> {
    return await api.delete('/api/v1/payment/payment-card');
  },
};

export const webhookApi = {
  /**
   * Get webhook URLs for SMS forwarding
   */
  async getWebhookUrls(): Promise<WebhookUrls> {
    return await api.get<WebhookUrls>('/api/v1/appointments/settings/webhook-urls');
  },
};
