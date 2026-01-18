import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content to prevent XSS attacks
 */
export const sanitizeHTML = (dirty: string): string => {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'span', 'br'],
    ALLOWED_ATTR: ['class'],
  });
};

/**
 * Sanitize plain text (removes all HTML)
 */
export const sanitizeText = (dirty: string): string => {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
  });
};

/**
 * Sanitize URL to prevent javascript: protocol attacks
 */
export const sanitizeUrl = (url: string): string => {
  const sanitized = DOMPurify.sanitize(url);
  if (sanitized.toLowerCase().startsWith('javascript:')) {
    return '';
  }
  return sanitized;
};
