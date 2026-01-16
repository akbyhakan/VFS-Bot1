/**
 * Production-safe logger utility
 * Hides debug/info/warn logs in production, always shows errors
 */

const isDev = import.meta.env.DEV;

export const logger = {
  debug: isDev ? console.debug.bind(console) : () => {},
  info: isDev ? console.info.bind(console) : () => {},
  warn: isDev ? console.warn.bind(console) : () => {},
  error: console.error.bind(console), // Errors always logged
  log: isDev ? console.log.bind(console) : () => {},
};
