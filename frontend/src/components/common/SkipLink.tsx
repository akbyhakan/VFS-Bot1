/**
 * Skip to main content link for keyboard navigation
 * Improves accessibility for keyboard and screen reader users
 */

export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-white focus:rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
    >
      Ana içeriğe atla
    </a>
  );
}
