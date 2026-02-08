/**
 * DEPRECATED: Secure token manager with memory-first storage
 * 
 * ⚠️ WARNING: This module is DEPRECATED as of v2.2.0
 * 
 * Primary authentication is now via HttpOnly cookies for XSS protection.
 * The browser automatically sends the HttpOnly cookie with each request.
 * 
 * This module is maintained for backward compatibility only.
 * New code should NOT use this module.
 * 
 * Migration guide:
 * - Remove all tokenManager.setToken() calls
 * - Remove all tokenManager.getToken() calls  
 * - Remove Authorization headers (cookies are sent automatically)
 * - Use cookie-based authentication endpoints
 */

import { AUTH_TOKEN_KEY } from './constants';

interface TokenData {
  token: string;
  expiresAt?: number;
}

class TokenManager {
  private memoryToken: string | null = null;

  /**
   * @deprecated Use HttpOnly cookies instead
   * Set token with optional remember me and expiration
   */
  setToken(token: string, remember: boolean = false, expiresInMs?: number): void {
    console.warn(
      '[DEPRECATED] tokenManager.setToken() is deprecated. ' +
      'Authentication now uses HttpOnly cookies for security. ' +
      'This call is a no-op and tokens are not stored in localStorage/sessionStorage.'
    );
    // No-op: Do not store tokens in browser storage anymore
    // Authentication is handled via HttpOnly cookies
  }

  /**
   * @deprecated Use HttpOnly cookies instead
   * Get token from memory or localStorage/sessionStorage
   */
  getToken(): string | null {
    console.warn(
      '[DEPRECATED] tokenManager.getToken() is deprecated. ' +
      'Authentication now uses HttpOnly cookies which are sent automatically. ' +
      'Returning null.'
    );
    // No-op: Always return null since tokens are not stored anymore
    return null;
  }

  /**
   * @deprecated Use HttpOnly cookies instead
   * Check if token exists and is valid
   */
  hasToken(): boolean {
    console.warn(
      '[DEPRECATED] tokenManager.hasToken() is deprecated. ' +
      'Use server-side authentication check instead (e.g., /api/auth/me endpoint).'
    );
    // No-op: Always return false since tokens are not stored
    return false;
  }

  /**
   * @deprecated Use HttpOnly cookies instead
   * Clear token from all storage
   */
  clearToken(): void {
    console.warn(
      '[DEPRECATED] tokenManager.clearToken() is deprecated. ' +
      'Call /api/auth/logout endpoint to clear HttpOnly cookies.'
    );
    // Clean up any legacy tokens that might exist
    this.memoryToken = null;
    localStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
  }

  /**
   * @deprecated Use HttpOnly cookies instead
   * Check if token is expired (if expiration was set)
   */
  isExpired(): boolean {
    console.warn(
      '[DEPRECATED] tokenManager.isExpired() is deprecated. ' +
      'Token expiration is handled server-side with HttpOnly cookies.'
    );
    // No-op: Always return true since we don't store tokens
    return true;
  }
}

export const tokenManager = new TokenManager();
