import { describe, it, expect, beforeEach, vi } from 'vitest';
import { tokenManager } from '@/utils/tokenManager';
import { AUTH_TOKEN_KEY } from '@/utils/constants';

describe('TokenManager (Deprecated)', () => {
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    // Reset internal state
    tokenManager.clearToken();
    // Spy on console.warn to suppress deprecation warnings in tests
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleWarnSpy.mockRestore();
  });

  describe('setToken (deprecated)', () => {
    it('does not store token in localStorage (no-op)', () => {
      tokenManager.setToken('test-token', true);
      expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('does not store token in sessionStorage (no-op)', () => {
      tokenManager.setToken('test-token', false);
      expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('logs deprecation warning', () => {
      tokenManager.setToken('test-token');
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DEPRECATED]')
      );
    });
  });

  describe('getToken (deprecated)', () => {
    it('returns null (no-op)', () => {
      expect(tokenManager.getToken()).toBeNull();
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('logs deprecation warning', () => {
      tokenManager.getToken();
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DEPRECATED]')
      );
    });
  });

  describe('hasToken (deprecated)', () => {
    it('returns false (no-op)', () => {
      expect(tokenManager.hasToken()).toBe(false);
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('logs deprecation warning', () => {
      tokenManager.hasToken();
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DEPRECATED]')
      );
    });
  });

  describe('clearToken (deprecated)', () => {
    it('clears legacy tokens from storage', () => {
      // Manually add legacy tokens
      localStorage.setItem(AUTH_TOKEN_KEY, 'legacy-token');
      sessionStorage.setItem(AUTH_TOKEN_KEY, 'legacy-token');
      
      tokenManager.clearToken();
      
      expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
      expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('logs deprecation warning', () => {
      tokenManager.clearToken();
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DEPRECATED]')
      );
    });
  });

  describe('isExpired (deprecated)', () => {
    it('returns true (no-op)', () => {
      expect(tokenManager.isExpired()).toBe(true);
      expect(consoleWarnSpy).toHaveBeenCalled();
    });

    it('logs deprecation warning', () => {
      tokenManager.isExpired();
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DEPRECATED]')
      );
    });
  });
});
