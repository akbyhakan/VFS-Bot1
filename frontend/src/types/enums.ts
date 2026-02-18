/**
 * Centralized enum definitions for VFS-Bot frontend.
 * 
 * These enums mirror the Python enums in src/core/enums.py
 * to ensure type safety and consistency across the application.
 */

export enum AppointmentRequestStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  BOOKED = 'booked',
  CHECKING = 'checking',
}

export enum AppointmentStatus {
  PENDING = 'pending',
  CONFIRMED = 'confirmed',
  CANCELLED = 'cancelled',
}

export enum AppointmentHistoryStatus {
  FOUND = 'found',
  BOOKED = 'booked',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum LogLevel {
  INFO = 'INFO',
  WARNING = 'WARNING',
  ERROR = 'ERROR',
}
