import * as Sentry from '@sentry/react';

/**
 * Initialize error tracking with Sentry
 * Only initializes in production mode when DSN is available
 */
export const initErrorTracking = () => {
  if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
    Sentry.init({
      dsn: import.meta.env.VITE_SENTRY_DSN,
      environment: import.meta.env.MODE,
      tracesSampleRate: 0.1,
      integrations: [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration({
          maskAllText: false,
          blockAllMedia: false,
        }),
      ],
      replaysSessionSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
    });
  }
};

/**
 * Capture an error and send to Sentry in production
 * Always logs to console for debugging
 */
export const captureError = (error: Error, context?: Record<string, unknown>) => {
  console.error(error);
  if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
    Sentry.captureException(error, { extra: context });
  }
};

/**
 * Capture a message/event to Sentry
 */
export const captureMessage = (message: string, level: Sentry.SeverityLevel = 'info') => {
  if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
    Sentry.captureMessage(message, level);
  }
};

/**
 * Set user context for error tracking
 */
export const setUserContext = (user: { id: string; email?: string; username?: string }) => {
  if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
    Sentry.setUser(user);
  }
};

/**
 * Clear user context
 */
export const clearUserContext = () => {
  if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
    Sentry.setUser(null);
  }
};
