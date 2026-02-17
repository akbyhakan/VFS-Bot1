/**
 * Type-safe environment variable utility
 * Provides validated access to environment variables using Zod
 */

import { z } from 'zod';

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().optional().or(z.literal('')),
  VITE_WS_BASE_URL: z.string().optional(),
  MODE: z.enum(['development', 'production', 'test']),
});

type EnvType = z.infer<typeof envSchema>;

// Parse and validate environment variables
const parseEnv = (): EnvType => {
  try {
    return envSchema.parse({
      VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
      VITE_WS_BASE_URL: import.meta.env.VITE_WS_BASE_URL,
      MODE: import.meta.env.MODE,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error('Environment validation failed:', error.errors);
      throw new Error(`Invalid environment configuration: ${error.errors.map(e => e.message).join(', ')}`);
    }
    throw error;
  }
};

const validatedEnv = parseEnv();

/**
 * Check if running in development mode
 */
export const isDev = (): boolean => import.meta.env.DEV;

/**
 * Check if running in production mode
 */
export const isProd = (): boolean => import.meta.env.PROD;

/**
 * Get current environment mode
 */
export const getMode = (): string => import.meta.env.MODE;

/**
 * Type-safe environment configuration
 */
export const env = {
  API_BASE_URL: validatedEnv.VITE_API_BASE_URL || '',
  WS_BASE_URL: validatedEnv.VITE_WS_BASE_URL || '',
  MODE: validatedEnv.MODE,
  IS_DEV: isDev(),
  IS_PROD: isProd(),
} as const;

/**
 * Validate that all required environment variables are set
 * Call this at app initialization
 * @throws Error in production if required variables are missing
 */
export function validateEnv(): void {
  const requiredVars = ['VITE_API_BASE_URL', 'VITE_WS_BASE_URL'] as const;
  const missing = requiredVars.filter((key) => {
    const value = import.meta.env[key];
    return value === undefined || value === '';
  });
  
  if (missing.length > 0) {
    const message = `Missing required environment variables: ${missing.join(', ')}`;
    if (isProd()) {
      throw new Error(message);
    } else {
      console.warn(message);
    }
  }
}

export default env;
