/**
 * Hook for managing payment card
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { paymentCardApi } from '@/services/paymentCard';
import type { PaymentCardRequest } from '@/types/payment';

export function usePaymentCard() {
  const queryClient = useQueryClient();

  const { data: card = null, isLoading: loading, error: queryError } = useQuery({
    queryKey: ['payment-card'],
    queryFn: () => paymentCardApi.getPaymentCard(),
  });

  const error = queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null;

  const saveMutation = useMutation({
    mutationFn: (cardData: PaymentCardRequest) => paymentCardApi.savePaymentCard(cardData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-card'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => paymentCardApi.deletePaymentCard(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-card'] });
    },
  });

  const saveCard = async (cardData: PaymentCardRequest): Promise<boolean> => {
    try {
      await saveMutation.mutateAsync(cardData);
      return true;
    } catch {
      return false;
    }
  };

  const deleteCard = async (): Promise<boolean> => {
    try {
      await deleteMutation.mutateAsync();
      return true;
    } catch {
      return false;
    }
  };

  const reload = () => {
    queryClient.invalidateQueries({ queryKey: ['payment-card'] });
  };

  return {
    card,
    loading,
    error,
    saving: saveMutation.isPending,
    deleting: deleteMutation.isPending,
    saveCard,
    deleteCard,
    reload,
  };
}
