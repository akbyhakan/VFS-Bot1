import { describe, it, expect } from 'vitest';
import {
  focusRing,
  focusRingDark,
  transitionBase,
  transitionSmooth,
  interactive,
  cardTransition,
  inputFocus,
} from '@/utils/styleUtils';

describe('styleUtils', () => {
  it('should export focusRing class', () => {
    expect(focusRing).toBeDefined();
    expect(typeof focusRing).toBe('string');
    expect(focusRing).toContain('focus:outline-none');
    expect(focusRing).toContain('focus:ring-2');
  });

  it('should export focusRingDark class', () => {
    expect(focusRingDark).toBeDefined();
    expect(typeof focusRingDark).toBe('string');
    expect(focusRingDark).toContain('focus:outline-none');
  });

  it('should export transition classes', () => {
    expect(transitionBase).toBeDefined();
    expect(transitionBase).toContain('transition-all');
    
    expect(transitionSmooth).toBeDefined();
    expect(transitionSmooth).toContain('transition-all');
    expect(transitionSmooth).toContain('ease-in-out');
  });

  it('should export interactive class combining focus and transition', () => {
    expect(interactive).toBeDefined();
    expect(interactive).toContain('focus:outline-none');
    expect(interactive).toContain('transition-all');
  });

  it('should export cardTransition class', () => {
    expect(cardTransition).toBeDefined();
    expect(cardTransition).toContain('transition-all');
  });

  it('should export inputFocus class', () => {
    expect(inputFocus).toBeDefined();
    expect(inputFocus).toContain('focus:outline-none');
    expect(inputFocus).toContain('focus:ring-2');
  });
});
