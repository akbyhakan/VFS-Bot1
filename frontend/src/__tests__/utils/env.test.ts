import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { env, isDev, isProd, getMode, validateEnv } from '@/utils/env';

describe('env utility', () => {
  // Store original env mode
  const originalMode = import.meta.env.MODE;

  afterEach(() => {
    // Restore original mode
    import.meta.env.MODE = originalMode;
  });

  it('should export environment configuration', () => {
    expect(env).toBeDefined();
    expect(env.API_BASE_URL).toBeDefined();
    expect(env.WS_BASE_URL).toBeDefined();
    expect(env.MODE).toBeDefined();
    expect(typeof env.IS_DEV).toBe('boolean');
    expect(typeof env.IS_PROD).toBe('boolean');
  });

  it('should have helper functions', () => {
    expect(typeof isDev()).toBe('boolean');
    expect(typeof isProd()).toBe('boolean');
    expect(typeof getMode()).toBe('string');
  });

  it('should validate env without throwing in development', () => {
    // Ensure we're in dev mode for this test
    if (!isDev()) {
      import.meta.env.MODE = 'development';
      import.meta.env.DEV = true;
      import.meta.env.PROD = false;
    }
    expect(() => validateEnv()).not.toThrow();
  });

  it('should have consistent dev/prod flags', () => {
    expect(isDev()).toBe(!isProd());
  });
});
