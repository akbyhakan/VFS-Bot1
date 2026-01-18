/**
 * Secure token manager with memory-first storage
 * Provides token management with remember me support and expiration handling
 */

import { AUTH_TOKEN_KEY } from './constants';

interface TokenData {
  token: string;
  expiresAt?: number;
}

class TokenManager {
  private memoryToken: string | null = null;

  /**
   * Set token with optional remember me and expiration
   */
  setToken(token: string, remember: boolean = false, expiresInMs?: number): void {
    this.memoryToken = token;

    if (remember) {
      const tokenData: TokenData = {
        token,
        expiresAt: expiresInMs ? Date.now() + expiresInMs : undefined,
      };
      localStorage.setItem(AUTH_TOKEN_KEY, JSON.stringify(tokenData));
      sessionStorage.removeItem(AUTH_TOKEN_KEY); // Clear sessionStorage
    } else {
      // Use sessionStorage for session-only tokens (more secure)
      sessionStorage.setItem(AUTH_TOKEN_KEY, token);
      localStorage.removeItem(AUTH_TOKEN_KEY); // Clear localStorage
    }
  }

  /**
   * Get token from memory or localStorage/sessionStorage
   */
  getToken(): string | null {
    // First check memory
    if (this.memoryToken) {
      return this.memoryToken;
    }

    // Then check localStorage (remember me)
    const stored = localStorage.getItem(AUTH_TOKEN_KEY);
    if (stored) {
      try {
        const tokenData: TokenData = JSON.parse(stored);
        if (tokenData?.token && typeof tokenData.token === 'string') {
          // Basic JWT structure validation (three base64url parts separated by dots)
          const jwtPattern = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
          if (!jwtPattern.test(tokenData.token)) {
            this.clearToken();
            return null;
          }
          
          if (tokenData.expiresAt && Date.now() > tokenData.expiresAt) {
            this.clearToken();
            return null;
          }
          this.memoryToken = tokenData.token;
          return tokenData.token;
        }
      } catch {
        localStorage.removeItem(AUTH_TOKEN_KEY);
      }
    }

    // Finally check sessionStorage (session-only)
    const sessionToken = sessionStorage.getItem(AUTH_TOKEN_KEY);
    if (sessionToken) {
      // Validate JWT structure for session tokens too
      const jwtPattern = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
      if (!jwtPattern.test(sessionToken)) {
        sessionStorage.removeItem(AUTH_TOKEN_KEY);
        return null;
      }
      this.memoryToken = sessionToken;
      return sessionToken;
    }

    return null;
  }

  /**
   * Check if token exists and is valid
   */
  hasToken(): boolean {
    return this.getToken() !== null;
  }

  /**
   * Clear token from all storage
   */
  clearToken(): void {
    this.memoryToken = null;
    localStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
  }

  /**
   * Check if token is expired (if expiration was set)
   */
  isExpired(): boolean {
    const stored = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!stored) {
      return !this.memoryToken; // If no localStorage, check memory
    }

    try {
      const tokenData: TokenData = JSON.parse(stored);
      if (tokenData.expiresAt) {
        return Date.now() > tokenData.expiresAt;
      }
      return false;
    } catch {
      return true;
    }
  }
}

export const tokenManager = new TokenManager();
