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
 * Required environment variables for production
 */
const REQUIRED_ENV_VARS = ['VITE_API_BASE_URL', 'VITE_WS_BASE_URL'] as const;

/**
 * Type-safe environment configuration
 * Note: API_BASE_URL and WS_BASE_URL use empty string defaults for development flexibility,
 * but are validated as required in production via validateEnv()
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
 * @throws Error in production if required variables are missing
 */
export function validateEnv(): void {
  const missing = REQUIRED_ENV_VARS.filter((key) => {
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
