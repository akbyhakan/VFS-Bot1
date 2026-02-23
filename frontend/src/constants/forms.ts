export const EMPTY_CARD_FORM = {
  card_holder_name: '',
  card_number: '',
  expiry_month: '',
  expiry_year: '',
} as const;

export type CardFormData = {
  card_holder_name: string;
  card_number: string;
  expiry_month: string;
  expiry_year: string;
};
