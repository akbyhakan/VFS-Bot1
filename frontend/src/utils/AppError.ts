/**
 * AppError — custom Error subclass that preserves RFC 7807 Problem Details fields.
 * Since AppError extends Error, error.message still works everywhere.
 */

export class AppError extends Error {
  readonly type?: string;
  readonly title?: string;
  readonly status?: number;
  readonly recoverable?: boolean;
  readonly retryAfter?: number;
  readonly field?: string;
  readonly fieldErrors?: Record<string, string>;

  constructor(
    message: string,
    options?: {
      type?: string;
      title?: string;
      status?: number;
      recoverable?: boolean;
      retryAfter?: number;
      field?: string;
      fieldErrors?: Record<string, string>;
    }
  ) {
    super(message);
    this.name = 'AppError';
    this.type = options?.type;
    this.title = options?.title;
    this.status = options?.status;
    this.recoverable = options?.recoverable;
    this.retryAfter = options?.retryAfter;
    this.field = options?.field;
    this.fieldErrors = options?.fieldErrors;

    // Restore prototype chain (needed for instanceof checks with transpiled classes)
    Object.setPrototypeOf(this, AppError.prototype);
  }

  /** True when the error is rate-limited (HTTP 429) */
  get isRateLimited(): boolean {
    return this.status === 429;
  }

  /** True when retrying makes sense (rate-limited or server explicitly says so) */
  get canRetry(): boolean {
    return this.isRateLimited || this.recoverable === true;
  }

  /** True when the error carries field-level validation details */
  get hasFieldErrors(): boolean {
    return !!this.fieldErrors && Object.keys(this.fieldErrors).length > 0;
  }
}

/**
 * Type guard for AppError
 */
export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError;
}
