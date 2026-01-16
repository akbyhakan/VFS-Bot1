/**
 * Focus trap hook for modal accessibility
 * Traps focus within a container element
 */

import { useEffect, RefObject } from 'react';

export function useFocusTrap(containerRef: RefObject<HTMLElement>, isActive: boolean = true) {
  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const container = containerRef.current;
    const focusableElements = container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    };

    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        // Optionally handle escape - caller can implement
        container.dispatchEvent(new CustomEvent('escape'));
      }
    };

    container.addEventListener('keydown', handleTabKey as EventListener);
    container.addEventListener('keydown', handleEscapeKey as EventListener);

    // Focus first element when activated
    firstElement?.focus();

    return () => {
      container.removeEventListener('keydown', handleTabKey as EventListener);
      container.removeEventListener('keydown', handleEscapeKey as EventListener);
    };
  }, [containerRef, isActive]);
}
