import { AppointmentRequestStatus } from './enums';

export interface AppointmentPerson {
  first_name: string;
  last_name: string;
  gender: 'female' | 'male';
  nationality: string;
  birth_date: string;
  passport_number: string;
  passport_issue_date: string;
  passport_expiry_date: string;
  phone_code: string;
  phone_number: string;
  email: string;
  is_child_with_parent: boolean;
}

export interface AppointmentPersonResponse extends AppointmentPerson {
  id: number;
}

export interface PaymentCard {
  card_number: string;
  expiry_month: string;
  expiry_year: string;
  cvv: string;
}

export interface AppointmentRequest {
  country_code: string;
  visa_category: string;
  visa_subcategory: string;
  centres: string[];
  preferred_dates: string[];
  person_count: number;
  persons: AppointmentPerson[];
  payment_card?: PaymentCard;
}

export interface AppointmentRequestResponse {
  id: number;
  country_code: string;
  visa_category: string;
  visa_subcategory: string;
  centres: string[];
  preferred_dates: string[];
  person_count: number;
  status: AppointmentRequestStatus;
  created_at: string;
  completed_at?: string;
  booked_date?: string;
  persons: AppointmentPersonResponse[];
}

export interface Country {
  code: string;
  name_en: string;
  name_tr: string;
}
