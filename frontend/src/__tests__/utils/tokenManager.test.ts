import { describe, it, expect, beforeEach } from 'vitest';
import { tokenManager } from '@/utils/tokenManager';
import { AUTH_TOKEN_KEY } from '@/utils/constants';

describe('TokenManager', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    // Reset internal state
    tokenManager.clearToken();
  });

  describe('setToken', () => {
    it('stores token in memory', () => {
      tokenManager.setToken('test-token');
      expect(tokenManager.getToken()).toBe('test-token');
    });

    it('stores token in localStorage when remember is true', () => {
      tokenManager.setToken('test-token', true);
      const stored = localStorage.getItem(AUTH_TOKEN_KEY);
      expect(stored).toBeTruthy();
      expect(JSON.parse(stored!).token).toBe('test-token');
    });

    it('stores token in sessionStorage when remember is false', () => {
      tokenManager.setToken('test-token', false);
      expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token');
      expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    });
  });

  describe('getToken', () => {
    it('returns token from memory first', () => {
      tokenManager.setToken('memory-token');
      localStorage.setItem(AUTH_TOKEN_KEY, JSON.stringify({ token: 'storage-token' }));
      expect(tokenManager.getToken()).toBe('memory-token');
    });

    it('returns null for expired token', () => {
      const expiredData = {
        token: 'expired-token',
        expiresAt: Date.now() - 1000, // Expired 1 second ago
      };
      localStorage.setItem(AUTH_TOKEN_KEY, JSON.stringify(expiredData));
      expect(tokenManager.getToken()).toBeNull();
    });
  });

  describe('clearToken', () => {
    it('clears token from all storage', () => {
      tokenManager.setToken('test-token', true);
      tokenManager.clearToken();
      
      expect(tokenManager.getToken()).toBeNull();
      expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
      expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    });
  });

  describe('hasToken', () => {
    it('returns true when token exists', () => {
      tokenManager.setToken('test-token');
      expect(tokenManager.hasToken()).toBe(true);
    });

    it('returns false when no token', () => {
      expect(tokenManager.hasToken()).toBe(false);
    });
  });
});
