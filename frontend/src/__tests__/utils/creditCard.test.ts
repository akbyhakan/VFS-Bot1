import { describe, it, expect } from 'vitest';
import {
  validateCardNumber,
  validateExpiryDate,
  validateCVV,
  validateCardholderName,
  formatCardNumber,
  getCardType,
  validateCardForm,
} from '@/utils/validators/creditCard';

describe('Credit Card Validators', () => {
  describe('validateCardNumber', () => {
    it('should accept valid card numbers', () => {
      expect(validateCardNumber('4111111111111111')).toBe(true); // Valid Visa test card
      expect(validateCardNumber('5555555555554444')).toBe(true); // Valid Mastercard test card
      expect(validateCardNumber('378282246310005')).toBe(true); // Valid Amex test card
    });

    it('should accept card numbers with spaces or dashes', () => {
      expect(validateCardNumber('4111 1111 1111 1111')).toBe(true);
      expect(validateCardNumber('5555-5555-5555-4444')).toBe(true);
    });

    it('should reject invalid card numbers (Luhn check)', () => {
      expect(validateCardNumber('4111111111111112')).toBe(false); // Invalid checksum
      expect(validateCardNumber('1234567890123456')).toBe(false); // Invalid checksum
    });

    it('should reject card numbers with wrong length', () => {
      expect(validateCardNumber('4111')).toBe(false); // Too short
      expect(validateCardNumber('41111111111111111111')).toBe(false); // Too long
    });

    it('should reject non-numeric card numbers', () => {
      expect(validateCardNumber('abcd1111abcd1111')).toBe(false);
      expect(validateCardNumber('4111-11aa-1111-1111')).toBe(false);
    });

    it('should reject empty string', () => {
      expect(validateCardNumber('')).toBe(false);
    });
  });

  describe('validateExpiryDate', () => {
    const currentDate = new Date();
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth() + 1;

    it('should accept valid future dates', () => {
      const futureYear = currentYear + 2;
      expect(validateExpiryDate('12', futureYear.toString())).toBe(true);
    });

    it('should accept current month and year', () => {
      expect(validateExpiryDate(currentMonth.toString(), currentYear.toString())).toBe(true);
    });

    it('should accept 2-digit year', () => {
      const twoDigitYear = (currentYear + 2) % 100;
      expect(validateExpiryDate('12', twoDigitYear.toString())).toBe(true);
    });

    it('should reject expired dates', () => {
      expect(validateExpiryDate('01', (currentYear - 1).toString())).toBe(false);
      
      if (currentMonth > 1) {
        expect(validateExpiryDate((currentMonth - 1).toString(), currentYear.toString())).toBe(false);
      }
    });

    it('should reject invalid months', () => {
      expect(validateExpiryDate('0', currentYear.toString())).toBe(false); // Month 0
      expect(validateExpiryDate('13', currentYear.toString())).toBe(false); // Month 13
      expect(validateExpiryDate('99', currentYear.toString())).toBe(false); // Invalid month
    });

    it('should reject dates too far in future', () => {
      const farFutureYear = currentYear + 15;
      expect(validateExpiryDate('12', farFutureYear.toString())).toBe(false);
    });

    it('should reject invalid input', () => {
      expect(validateExpiryDate('', '')).toBe(false);
      expect(validateExpiryDate('abc', 'xyz')).toBe(false);
    });
  });

  describe('validateCVV', () => {
    it('should accept valid 3-digit CVV', () => {
      expect(validateCVV('123')).toBe(true);
      expect(validateCVV('999')).toBe(true);
    });

    it('should accept valid 4-digit CVV', () => {
      expect(validateCVV('1234')).toBe(true);
      expect(validateCVV('9999')).toBe(true);
    });

    it('should reject invalid CVV', () => {
      expect(validateCVV('12')).toBe(false); // Too short
      expect(validateCVV('12345')).toBe(false); // Too long
      expect(validateCVV('abc')).toBe(false); // Non-numeric
      expect(validateCVV('')).toBe(false); // Empty
    });
  });

  describe('validateCardholderName', () => {
    it('should accept valid names', () => {
      expect(validateCardholderName('John Doe')).toBe(true);
      expect(validateCardholderName('Mary Jane Smith')).toBe(true);
      expect(validateCardholderName('Ahmet Yılmaz')).toBe(true);
    });

    it('should accept Turkish characters', () => {
      expect(validateCardholderName('Çağlar Şimşek')).toBe(true);
      expect(validateCardholderName('Öznur Güneş')).toBe(true);
    });

    it('should reject names that are too short', () => {
      expect(validateCardholderName('A')).toBe(false);
      expect(validateCardholderName(' ')).toBe(false);
    });

    it('should reject names with numbers or special characters', () => {
      expect(validateCardholderName('John123')).toBe(false);
      expect(validateCardholderName('John@Doe')).toBe(false);
      expect(validateCardholderName('John-Doe')).toBe(false);
    });

    it('should reject empty string', () => {
      expect(validateCardholderName('')).toBe(false);
    });
  });

  describe('formatCardNumber', () => {
    it('should format card numbers with spaces', () => {
      expect(formatCardNumber('4111111111111111')).toBe('4111 1111 1111 1111');
      expect(formatCardNumber('378282246310005')).toBe('3782 8224 6310 005');
    });

    it('should handle partial card numbers', () => {
      expect(formatCardNumber('4111')).toBe('4111');
      expect(formatCardNumber('41111111')).toBe('4111 1111');
    });

    it('should remove existing formatting', () => {
      expect(formatCardNumber('4111-1111-1111-1111')).toBe('4111 1111 1111 1111');
      expect(formatCardNumber('4111 1111 1111 1111')).toBe('4111 1111 1111 1111');
    });
  });

  describe('getCardType', () => {
    it('should detect Visa cards', () => {
      expect(getCardType('4111111111111111')).toBe('visa');
      expect(getCardType('4')).toBe('visa');
    });

    it('should detect Mastercard', () => {
      expect(getCardType('5555555555554444')).toBe('mastercard');
      expect(getCardType('2221000000000000')).toBe('mastercard'); // New Mastercard range
    });

    it('should detect American Express', () => {
      expect(getCardType('378282246310005')).toBe('amex');
      expect(getCardType('371449635398431')).toBe('amex');
    });

    it('should return unknown for invalid or unknown cards', () => {
      expect(getCardType('9111111111111111')).toBe('unknown');
      expect(getCardType('1234')).toBe('unknown');
    });
  });

  describe('validateCardForm', () => {
    const currentDate = new Date();
    const futureYear = currentDate.getFullYear() + 2;

    it('should validate a complete valid form', () => {
      const result = validateCardForm({
        card_holder_name: 'John Doe',
        card_number: '4111111111111111',
        expiry_month: '12',
        expiry_year: futureYear.toString(),
        cvv: '123',
      });

      expect(result.isValid).toBe(true);
      expect(Object.keys(result.errors).length).toBe(0);
    });

    it('should return errors for invalid card holder name', () => {
      const result = validateCardForm({
        card_holder_name: 'A',
        card_number: '4111111111111111',
        expiry_month: '12',
        expiry_year: futureYear.toString(),
        cvv: '123',
      });

      expect(result.isValid).toBe(false);
      expect(result.errors.cardholderName).toBeDefined();
    });

    it('should return errors for invalid card number', () => {
      const result = validateCardForm({
        card_holder_name: 'John Doe',
        card_number: '1234567890123456', // Invalid Luhn
        expiry_month: '12',
        expiry_year: futureYear.toString(),
        cvv: '123',
      });

      expect(result.isValid).toBe(false);
      expect(result.errors.cardNumber).toBeDefined();
    });

    it('should return errors for invalid expiry date', () => {
      const result = validateCardForm({
        card_holder_name: 'John Doe',
        card_number: '4111111111111111',
        expiry_month: '13', // Invalid month
        expiry_year: futureYear.toString(),
        cvv: '123',
      });

      expect(result.isValid).toBe(false);
      expect(result.errors.expiryMonth).toBeDefined();
    });

    it('should return errors for invalid CVV', () => {
      const result = validateCardForm({
        card_holder_name: 'John Doe',
        card_number: '4111111111111111',
        expiry_month: '12',
        expiry_year: futureYear.toString(),
        cvv: '12', // Too short
      });

      expect(result.isValid).toBe(false);
      expect(result.errors.cvv).toBeDefined();
    });

    it('should return multiple errors for multiple invalid fields', () => {
      const result = validateCardForm({
        card_holder_name: 'A',
        card_number: '1234',
        expiry_month: '13',
        expiry_year: '2000',
        cvv: '12',
      });

      expect(result.isValid).toBe(false);
      expect(result.errors.cardholderName).toBeDefined();
      expect(result.errors.cardNumber).toBeDefined();
      expect(result.errors.expiryMonth).toBeDefined();
      expect(result.errors.cvv).toBeDefined();
    });
  });
});
