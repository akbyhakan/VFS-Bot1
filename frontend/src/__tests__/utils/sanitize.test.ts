import { describe, it, expect } from 'vitest';
import { sanitizeHTML, sanitizeText, sanitizeUrl } from '@/utils/sanitize';

describe('sanitize utilities', () => {
  describe('sanitizeHTML', () => {
    it('allows safe HTML tags', () => {
      const input = '<b>Bold</b> and <i>italic</i>';
      expect(sanitizeHTML(input)).toBe('<b>Bold</b> and <i>italic</i>');
    });

    it('removes script tags', () => {
      const input = '<script>alert("xss")</script>Hello';
      expect(sanitizeHTML(input)).toBe('Hello');
    });

    it('removes onclick handlers', () => {
      const input = '<button onclick="alert(1)">Click</button>';
      expect(sanitizeHTML(input)).not.toContain('onclick');
    });

    it('removes dangerous attributes', () => {
      const input = '<img src="x" onerror="alert(1)">';
      expect(sanitizeHTML(input)).not.toContain('onerror');
    });
  });

  describe('sanitizeText', () => {
    it('removes all HTML tags', () => {
      const input = '<b>Bold</b> text';
      expect(sanitizeText(input)).toBe('Bold text');
    });

    it('handles plain text correctly', () => {
      const input = 'Hello World';
      expect(sanitizeText(input)).toBe('Hello World');
    });
  });

  describe('sanitizeUrl', () => {
    it('allows http URLs', () => {
      const input = 'https://example.com';
      expect(sanitizeUrl(input)).toBe('https://example.com');
    });

    it('blocks javascript: protocol', () => {
      const input = 'javascript:alert(1)';
      expect(sanitizeUrl(input)).toBe('');
    });

    it('blocks JavaScript: protocol (case insensitive)', () => {
      const input = 'JavaScript:alert(1)';
      expect(sanitizeUrl(input)).toBe('');
    });
  });
});
