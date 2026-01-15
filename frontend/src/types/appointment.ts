export interface AppointmentPerson {
  first_name: string;
  last_name: string;
  nationality: string;
  birth_date: string;
  passport_number: string;
  passport_issue_date: string;
  passport_expiry_date: string;
  phone_code: string;
  phone_number: string;
  email: string;
}

export interface AppointmentPersonResponse extends AppointmentPerson {
  id: number;
}

export interface AppointmentRequest {
  country_code: string;
  centres: string[];
  preferred_dates: string[];
  person_count: number;
  persons: AppointmentPerson[];
}

export interface AppointmentRequestResponse {
  id: number;
  country_code: string;
  centres: string[];
  preferred_dates: string[];
  person_count: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  completed_at?: string;
  persons: AppointmentPersonResponse[];
}

export interface Country {
  code: string;
  name_en: string;
  name_tr: string;
}
