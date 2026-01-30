import { useState, useCallback } from 'react';

interface RateLimitConfig {
  maxAttempts: number;
  windowMs: number;
  lockoutMs: number;
}

export function useRateLimit(config: RateLimitConfig) {
  const [attempts, setAttempts] = useState(0);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);

  const isLocked = lockedUntil && Date.now() < lockedUntil;
  const remainingTime = lockedUntil ? Math.ceil((lockedUntil - Date.now()) / 1000) : 0;

  const recordAttempt = useCallback(() => {
    const newAttempts = attempts + 1;
    setAttempts(newAttempts);
    
    if (newAttempts >= config.maxAttempts) {
      setLockedUntil(Date.now() + config.lockoutMs);
      setTimeout(() => {
        setAttempts(0);
        setLockedUntil(null);
      }, config.lockoutMs);
    }
  }, [attempts, config]);

  const resetAttempts = useCallback(() => {
    setAttempts(0);
    setLockedUntil(null);
  }, []);

  return { isLocked, remainingTime, recordAttempt, resetAttempts, attempts };
}
