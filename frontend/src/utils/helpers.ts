import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow } from 'date-fns';
import { tr } from 'date-fns/locale/tr';

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format date to Turkish locale
 */
export function formatDate(date: string | Date, formatStr: string = 'PPp'): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return format(dateObj, formatStr, { locale: tr });
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: string | Date): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return formatDistanceToNow(dateObj, { addSuffix: true, locale: tr });
}

/**
 * Format duration in seconds to human readable
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}sa ${minutes}dk ${secs}sn`;
  } else if (minutes > 0) {
    return `${minutes}dk ${secs}sn`;
  } else {
    return `${secs}sn`;
  }
}

/**
 * Format number with thousand separators
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('tr-TR').format(num);
}

/**
 * Format percentage
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

/**
 * Get status color class
 */
export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'running':
      return 'text-primary-500';
    case 'stopped':
      return 'text-red-500';
    case 'idle':
      return 'text-yellow-500';
    case 'error':
      return 'text-red-600';
    case 'starting':
      return 'text-blue-500';
    case 'restarting':
      return 'text-yellow-500';
    case 'not_configured':
      return 'text-dark-400';
    case 'rate_limited':
      return 'text-orange-500';
    case 'healthy':
      return 'text-primary-500';
    case 'degraded':
      return 'text-yellow-500';
    case 'unhealthy':
      return 'text-red-500';
    default:
      return 'text-dark-400';
  }
}

/**
 * Get log level color class
 */
export function getLogLevelColor(level: string): string {
  switch (level.toUpperCase()) {
    case 'DEBUG':
      return 'text-dark-400';
    case 'INFO':
      return 'text-blue-400';
    case 'WARNING':
      return 'text-yellow-400';
    case 'ERROR':
      return 'text-red-400';
    case 'SUCCESS':
      return 'text-primary-400';
    default:
      return 'text-dark-300';
  }
}

/**
 * Sleep utility
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null;
      func(...args);
    };

    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);
  };
}

/**
 * Get initials from name
 */
export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

/**
 * Safe JSON parse
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
}

/**
 * Copy to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
