import { z } from 'zod';

export const loginSchema = z.object({
  username: z.string().min(1, 'Kullanıcı adı gerekli'),
  password: z.string().min(1, 'Şifre gerekli'),
  rememberMe: z.boolean().optional(),
});

// VFS Account schema - for VFS login credentials
export const vfsAccountSchema = z.object({
  email: z.string().email('Geçerli bir e-posta adresi girin'),
  password: z.string().optional(), // Optional for updates, required for creation
  phone: z.string().min(10, 'Geçerli bir telefon numarası girin'),
  is_active: z.boolean().default(true),
});

// Schema for creating new VFS accounts - password is required
export const createVFSAccountSchema = vfsAccountSchema.extend({
  password: z.string().min(6, 'Şifre en az 6 karakter olmalı'),
});

// NOTE: Bot settings validation is handled by backend API (see web/models/bot.py).
// Frontend only manages user-facing bot settings through API endpoints.

export type LoginFormData = z.infer<typeof loginSchema>;
export type VFSAccountFormData = z.infer<typeof vfsAccountSchema>;
export type CreateVFSAccountFormData = z.infer<typeof createVFSAccountSchema>;
