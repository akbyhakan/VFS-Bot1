/**
 * Payment card type definitions
 */

export interface PaymentCard {
  id: number;
  card_holder_name: string;
  card_number_masked: string;
  expiry_month: string;
  expiry_year: string;
  created_at: string;
}

export interface PaymentCardRequest {
  card_holder_name: string;
  card_number: string;
  expiry_month: string;
  expiry_year: string;
  cvv: string;
}

export interface WebhookUrls {
  appointment_webhook: string;
  payment_webhook: string;
  base_url: string;
}
