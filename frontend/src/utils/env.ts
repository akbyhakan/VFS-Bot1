/**
 * Type-safe environment variable utility
 * Provides validated access to environment variables
 */

/**
 * Get environment variable with validation
 * @param key - Environment variable key
 * @param defaultValue - Optional default value
 * @throws Error if required variable is missing and no default provided
 */
function getEnv(key: string, defaultValue?: string): string {
  const value = import.meta.env[key];
  
  if (value === undefined || value === '') {
    if (defaultValue !== undefined) {
      return defaultValue;
    }
    throw new Error(`Missing required environment variable: ${key}`);
  }
  
  return String(value);
}

/**
 * Get optional environment variable
 * @param key - Environment variable key
 * @param defaultValue - Default value if not set
 */
function getOptionalEnv(key: string, defaultValue = ''): string {
  return getEnv(key, defaultValue);
}

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
  API_BASE_URL: getOptionalEnv('VITE_API_BASE_URL', ''),
  WS_BASE_URL: getOptionalEnv('VITE_WS_BASE_URL', ''),
  MODE: getMode(),
  IS_DEV: isDev(),
  IS_PROD: isProd(),
} as const;

/**
 * Validate that all required environment variables are set
 * Call this at app initialization
 */
export function validateEnv(): void {
  const required = ['VITE_API_BASE_URL', 'VITE_WS_BASE_URL'];
  
  const missing = required.filter((key) => {
    const value = import.meta.env[key];
    return value === undefined || value === '';
  });
  
  if (missing.length > 0 && isProd()) {
    console.warn(
      `Missing environment variables in production: ${missing.join(', ')}`
    );
  }
}

export default env;
