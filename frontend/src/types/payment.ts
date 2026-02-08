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
  /** Card holder name: 2-100 characters, letters and spaces only */
  card_holder_name: string;
  /** Card number: 13-19 digits only, validated with Luhn algorithm */
  card_number: string;
  /** Expiry month: 01-12 format */
  expiry_month: string;
  /** Expiry year: YY or YYYY format */
  expiry_year: string;
  /** CVV: 3-4 digits only */
  cvv: string;
}

export interface WebhookUrls {
  appointment_webhook: string;
  payment_webhook: string;
  base_url: string;
}
