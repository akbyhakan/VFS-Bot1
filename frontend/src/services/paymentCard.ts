/**
 * Payment card API methods
 */

import { api } from './api';
import type { PaymentCard, PaymentCardRequest } from '@/types/payment';
import { isAppError } from '@/utils/AppError';

export const paymentCardApi = {
  /**
   * Get the saved payment card (masked)
   */
  async getPaymentCard(): Promise<PaymentCard | null> {
    try {
      const card = await api.get<PaymentCard>('/api/v1/payment/payment-card');
      return card ?? null;
    } catch (error: unknown) {
      // Return null if no card exists (404) or if card is explicitly null
      if (isAppError(error)) {
        if (error.status === 404) {
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
      if (isAppError(error) && error.status === 422) {
        if (error.hasFieldErrors && error.fieldErrors) {
          const fieldErrors = Object.entries(error.fieldErrors)
            .map(([field, msg]) => `${field}: ${msg}`)
            .join('; ');
          throw new Error(`Validation error: ${fieldErrors}`);
        }
        if (error.message) {
          throw new Error(`Validation error: ${error.message}`);
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
