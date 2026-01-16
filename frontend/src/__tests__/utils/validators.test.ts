import { describe, it, expect } from 'vitest';
import {
  validateBirthDate,
  validatePassportIssueDate,
  validatePassportExpiryDate,
  validateEmail,
  validateTurkishPhone,
  validatePassportNumber,
  validatePreferredDate,
} from '@/utils/validators/appointment';

describe('Appointment Validators', () => {
  describe('validateBirthDate', () => {
    it('should accept valid past dates', () => {
      const pastDate = '01/01/1990';
      expect(validateBirthDate(pastDate)).toBe(true);
    });

    it('should reject future dates', () => {
      const futureDate = new Date();
      futureDate.setFullYear(futureDate.getFullYear() + 1);
      const dateStr = `${String(futureDate.getDate()).padStart(2, '0')}/${String(futureDate.getMonth() + 1).padStart(2, '0')}/${futureDate.getFullYear()}`;
      expect(validateBirthDate(dateStr)).toBe(false);
    });

    it('should reject invalid format', () => {
      expect(validateBirthDate('invalid')).toBe(false);
      expect(validateBirthDate('')).toBe(false);
    });
  });

  describe('validatePassportExpiryDate', () => {
    it('should accept dates more than 3 months in future', () => {
      const futureDate = new Date();
      futureDate.setMonth(futureDate.getMonth() + 6);
      const dateStr = `${String(futureDate.getDate()).padStart(2, '0')}/${String(futureDate.getMonth() + 1).padStart(2, '0')}/${futureDate.getFullYear()}`;
      expect(validatePassportExpiryDate(dateStr)).toBe(true);
    });

    it('should reject dates less than 3 months in future', () => {
      const soonDate = new Date();
      soonDate.setMonth(soonDate.getMonth() + 1);
      const dateStr = `${String(soonDate.getDate()).padStart(2, '0')}/${String(soonDate.getMonth() + 1).padStart(2, '0')}/${soonDate.getFullYear()}`;
      expect(validatePassportExpiryDate(dateStr)).toBe(false);
    });
  });

  describe('validateEmail', () => {
    it('should accept valid emails', () => {
      expect(validateEmail('test@example.com')).toBe(true);
      expect(validateEmail('user.name@domain.co.uk')).toBe(true);
    });

    it('should reject invalid emails', () => {
      expect(validateEmail('invalid')).toBe(false);
      expect(validateEmail('test@')).toBe(false);
      expect(validateEmail('@example.com')).toBe(false);
    });
  });

  describe('validateTurkishPhone', () => {
    it('should accept valid Turkish phone numbers', () => {
      expect(validateTurkishPhone('5551234567')).toBe(true);
      expect(validateTurkishPhone('5339876543')).toBe(true);
    });

    it('should reject invalid phone numbers', () => {
      expect(validateTurkishPhone('05551234567')).toBe(false); // starts with 0
      expect(validateTurkishPhone('555123456')).toBe(false); // too short
      expect(validateTurkishPhone('55512345678')).toBe(false); // too long
    });
  });

  describe('validatePassportNumber', () => {
    it('should accept valid passport numbers', () => {
      expect(validatePassportNumber('AB123456')).toBe(true);
      expect(validatePassportNumber('U12345678')).toBe(true);
    });

    it('should reject invalid passport numbers', () => {
      expect(validatePassportNumber('12345')).toBe(false); // too short
      expect(validatePassportNumber('A@#$%')).toBe(false); // invalid chars
    });
  });

  describe('validatePreferredDate', () => {
    it('should accept future dates', () => {
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + 7);
      const dateStr = `${String(futureDate.getDate()).padStart(2, '0')}/${String(futureDate.getMonth() + 1).padStart(2, '0')}/${futureDate.getFullYear()}`;
      expect(validatePreferredDate(dateStr)).toBe(true);
    });

    it('should reject past dates', () => {
      const pastDate = '01/01/2020';
      expect(validatePreferredDate(pastDate)).toBe(false);
    });
  });
});
