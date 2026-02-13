import { toast } from 'sonner';
import { logger } from './logger';
import i18n from '@/i18n';

interface ErrorOptions {
  fallbackMessage?: string;
  showToast?: boolean;
  logError?: boolean;
}

/**
 * Centralized error handler for consistent error handling across the app
 */
export function handleError(
  error: unknown,
  options: ErrorOptions = {}
): string {
  const {
    fallbackMessage = i18n.t('errors.generic'),
    showToast = true,
    logError = true,
  } = options;

  let message: string;

  if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === 'string') {
    message = error;
  } else {
    message = fallbackMessage;
  }

  if (logError) {
    logger.error('Error occurred:', error);
  }

  if (showToast) {
    toast.error(message);
  }

  return message;
}

/**
 * Handle API errors specifically
 */
export function handleApiError(error: unknown, fallbackMessage: string = i18n.t('errors.apiFailed')): string {
  return handleError(error, { fallbackMessage, showToast: true });
}

/**
 * Handle form validation errors
 */
export function handleValidationError(errors: Record<string, string>): void {
  const firstError = Object.values(errors)[0];
  if (firstError) {
    toast.error(firstError);
  }
}
