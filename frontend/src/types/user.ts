// VFS Account types - for VFS login credentials stored in vfs_account_pool
export interface VFSAccount {
  id: number;
  email: string;
  phone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateVFSAccountRequest {
  email: string;
  password: string;  // VFS password (required for creation)
  phone: string;
  is_active?: boolean;
}

export interface UpdateVFSAccountRequest {
  email?: string;
  password?: string;  // VFS password (optional - only updated if provided)
  phone?: string;
  is_active?: boolean;
}

export interface UpdateVFSAccountPayload {
  id: number;
  data: UpdateVFSAccountRequest;
}

export interface VFSAccountStats {
  total_accounts: number;
  active_accounts: number;
  inactive_accounts: number;
}
