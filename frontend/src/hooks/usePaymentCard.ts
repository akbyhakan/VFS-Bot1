/**
 * Hook for managing payment card
 */

import { useState, useEffect } from 'react';
import { paymentCardApi } from '@/services/paymentCard';
import type { PaymentCard, PaymentCardRequest } from '@/types/payment';

export function usePaymentCard() {
  const [card, setCard] = useState<PaymentCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadCard = async () => {
    try {
      setLoading(true);
      setError(null);
      const cardData = await paymentCardApi.getPaymentCard();
      setCard(cardData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load payment card');
    } finally {
      setLoading(false);
    }
  };

  const saveCard = async (cardData: PaymentCardRequest): Promise<boolean> => {
    try {
      setSaving(true);
      setError(null);
      await paymentCardApi.savePaymentCard(cardData);
      await loadCard(); // Reload card data
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save payment card');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const deleteCard = async (): Promise<boolean> => {
    try {
      setDeleting(true);
      setError(null);
      await paymentCardApi.deletePaymentCard();
      setCard(null);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete payment card');
      return false;
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    loadCard();
  }, []);

  return {
    card,
    loading,
    error,
    saving,
    deleting,
    saveCard,
    deleteCard,
    reload: loadCard,
  };
}
