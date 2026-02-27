import { toast } from 'sonner';
import { logger } from './logger';
import { isAppError } from './AppError';
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

  if (isAppError(error)) {
    if (error.isRateLimited) {
      message = error.retryAfter
        ? `${error.message} (${i18n.t('errors.retryAfter', { seconds: error.retryAfter, defaultValue: `${error.retryAfter}s sonra tekrar deneyin` })})`
        : error.message;
      if (logError) {
        logger.error('Error occurred:', error);
      }
      if (showToast) {
        toast.warning(message);
      }
      return message;
    }
    if (error.hasFieldErrors) {
      const firstFieldError = error.fieldErrors ? Object.values(error.fieldErrors)[0] : undefined;
      message = firstFieldError ?? error.message;
    } else {
      message = error.message;
    }
  } else if (error instanceof Error) {
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
