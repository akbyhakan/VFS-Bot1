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
  private rememberMe: boolean = false;

  /**
   * Set token with optional remember me and expiration
   */
  setToken(token: string, remember: boolean = false, expiresInMs?: number): void {
    this.memoryToken = token;
    this.rememberMe = remember;

    if (remember) {
      const tokenData: TokenData = {
        token,
        expiresAt: expiresInMs ? Date.now() + expiresInMs : undefined,
      };
      localStorage.setItem(AUTH_TOKEN_KEY, JSON.stringify(tokenData));
    } else {
      // Clear localStorage if not remembering
      localStorage.removeItem(AUTH_TOKEN_KEY);
    }
  }

  /**
   * Get token from memory or localStorage
   */
  getToken(): string | null {
    // First check memory
    if (this.memoryToken) {
      return this.memoryToken;
    }

    // Then check localStorage
    const stored = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!stored) {
      return null;
    }

    try {
      const tokenData: TokenData = JSON.parse(stored);
      
      // Check expiration
      if (tokenData.expiresAt && Date.now() > tokenData.expiresAt) {
        this.clearToken();
        return null;
      }

      // Restore to memory
      this.memoryToken = tokenData.token;
      this.rememberMe = true;
      return tokenData.token;
    } catch {
      // Invalid format, clear it
      localStorage.removeItem(AUTH_TOKEN_KEY);
      return null;
    }
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
    this.rememberMe = false;
    localStorage.removeItem(AUTH_TOKEN_KEY);
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
