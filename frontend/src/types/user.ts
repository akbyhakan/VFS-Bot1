export interface User {
  id: number;
  email: string;
  phone: string;
  first_name: string;
  last_name: string;
  center_name: string;
  visa_category: string;
  visa_subcategory: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateUserRequest {
  email: string;
  password: string;  // VFS password (required for creation)
  phone: string;
  first_name: string;
  last_name: string;
  center_name: string;
  visa_category: string;
  visa_subcategory: string;
  is_active?: boolean;
}

export interface UpdateUserRequest {
  email?: string;
  password?: string;  // VFS password (optional - only updated if provided)
  phone?: string;
  first_name?: string;
  last_name?: string;
  center_name?: string;
  visa_category?: string;
  visa_subcategory?: string;
  is_active?: boolean;
}

export interface UpdateUserPayload {
  id: number;
  data: UpdateUserRequest;
}

export interface UserStats {
  total_users: number;
  active_users: number;
  inactive_users: number;
  appointments_booked: number;
}
