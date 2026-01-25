import { z } from 'zod';

export const loginSchema = z.object({
  username: z.string().min(1, 'Kullanıcı adı gerekli'),
  password: z.string().min(1, 'Şifre gerekli'),
  rememberMe: z.boolean().optional(),
});

// VFS Account schema - simplified for VFS login credentials
export const userSchema = z.object({
  email: z.string().email('Geçerli bir e-posta adresi girin'),
  password: z.string().optional(), // Optional for updates, required for creation (see createUserSchema)
  phone: z.string().min(10, 'Geçerli bir telefon numarası girin'),
  is_active: z.boolean().default(true),
});

// Schema for creating new VFS accounts - password is required
export const createUserSchema = userSchema.extend({
  password: z.string().min(6, 'Şifre en az 6 karakter olmalı'),
});

export const settingsSchema = z.object({
  check_interval: z.number().min(30, 'Kontrol aralığı en az 30 saniye olmalı'),
  headless_mode: z.boolean(),
  max_retries: z.number().min(1).max(10),
  timeout: z.number().min(5000).max(60000),
  anti_detection: z.object({
    enabled: z.boolean(),
    canvas_noise: z.boolean(),
    webgl_vendor_override: z.boolean(),
    audio_context_randomization: z.boolean(),
    mouse_movement_simulation: z.boolean(),
    typing_simulation: z.boolean(),
  }),
  proxy: z.object({
    enabled: z.boolean(),
    proxy_file: z.string().optional(),
    rotation_enabled: z.boolean(),
    failover_enabled: z.boolean(),
  }),
  notifications: z.object({
    telegram: z.object({
      enabled: z.boolean(),
      bot_token: z.string().optional(),
      chat_id: z.string().optional(),
      notifications_on_slot_found: z.boolean(),
      notifications_on_appointment_booked: z.boolean(),
      notifications_on_error: z.boolean(),
    }),
    email: z.object({
      enabled: z.boolean(),
      sender: z.string().email().optional(),
      receiver: z.string().email().optional(),
      smtp_server: z.string().optional(),
      smtp_port: z.number().optional(),
      use_tls: z.boolean(),
      notifications_on_slot_found: z.boolean(),
      notifications_on_appointment_booked: z.boolean(),
      notifications_on_error: z.boolean(),
    }),
  }),
});

export type LoginFormData = z.infer<typeof loginSchema>;
export type UserFormData = z.infer<typeof userSchema>;
export type CreateUserFormData = z.infer<typeof createUserSchema>;
export type SettingsFormData = z.infer<typeof settingsSchema>;
