/**
 * Common style utilities for consistent focus and transition styles
 * Use these utility classes to avoid repetition across components
 */

/**
 * Standard focus ring style
 * Use for interactive elements like buttons, inputs, links
 */
export const focusRing = 'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-dark-900';

/**
 * Alternative focus ring for elements on dark backgrounds
 */
export const focusRingDark = 'focus:outline-none focus:ring-2 focus:ring-primary-500';

/**
 * Base transition style
 * Use for most interactive elements
 */
export const transitionBase = 'transition-all duration-200';

/**
 * Smooth transition style
 * Use for more noticeable animations
 */
export const transitionSmooth = 'transition-all duration-300 ease-in-out';

/**
 * Interactive element style (focus + transition)
 * Common pattern for buttons, links, clickable elements
 */
export const interactive = `${focusRing} ${transitionBase}`;

/**
 * Card transition style
 * For hoverable cards
 */
export const cardTransition = 'transition-all duration-300';

/**
 * Input focus style
 * For form inputs
 */
export const inputFocus = 'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent';

export default {
  focusRing,
  focusRingDark,
  transitionBase,
  transitionSmooth,
  interactive,
  cardTransition,
  inputFocus,
};
