/**
 * Credit card validation utilities
 */

/**
 * Validate card number using Luhn algorithm
 */
export function validateCardNumber(cardNumber: string): boolean {
  // Remove spaces and dashes
  const cleanNumber = cardNumber.replace(/[\s-]/g, '');
  
  // Check if only digits
  if (!/^\d+$/.test(cleanNumber)) {
    return false;
  }
  
  // Check length (13-19 digits for most cards)
  if (cleanNumber.length < 13 || cleanNumber.length > 19) {
    return false;
  }
  
  // Luhn algorithm
  let sum = 0;
  let isEven = false;
  
  for (let i = cleanNumber.length - 1; i >= 0; i--) {
    let digit = parseInt(cleanNumber[i], 10);
    
    if (isEven) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    
    sum += digit;
    isEven = !isEven;
  }
  
  return sum % 10 === 0;
}

/**
 * Validate expiry date
 */
export function validateExpiryDate(month: string, year: string): boolean {
  const monthNum = parseInt(month, 10);
  const yearNum = parseInt(year, 10);
  
  // Validate month (1-12)
  if (isNaN(monthNum) || monthNum < 1 || monthNum > 12) {
    return false;
  }
  
  // Validate year format
  if (isNaN(yearNum)) {
    return false;
  }
  
  // Convert 2-digit year to 4-digit
  const fullYear = yearNum < 100 ? 2000 + yearNum : yearNum;
  
  // Check if not expired
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  
  if (fullYear < currentYear) {
    return false;
  }
  
  if (fullYear === currentYear && monthNum < currentMonth) {
    return false;
  }
  
  // Check if not too far in future (10 years max)
  if (fullYear > currentYear + 10) {
    return false;
  }
  
  return true;
}

/**
 * Validate CVV
 */
export function validateCVV(cvv: string): boolean {
  // CVV should be 3 or 4 digits
  return /^\d{3,4}$/.test(cvv);
}

/**
 * Validate cardholder name
 */
export function validateCardholderName(name: string): boolean {
  // At least 2 characters, only letters and spaces
  const trimmed = name.trim();
  return trimmed.length >= 2 && /^[a-zA-ZğüşıöçĞÜŞİÖÇ\s]+$/.test(trimmed);
}

/**
 * Format card number with spaces (for display)
 */
export function formatCardNumber(cardNumber: string): string {
  const clean = cardNumber.replace(/\D/g, '');
  if (!clean) return '';
  const groups = clean.match(/.{1,4}/g);
  return groups ? groups.join(' ') : clean;
}

/**
 * Get card type from number
 */
export function getCardType(cardNumber: string): 'visa' | 'mastercard' | 'amex' | 'unknown' {
  const clean = cardNumber.replace(/\D/g, '');
  
  if (/^4/.test(clean)) return 'visa';
  if (/^5[1-5]/.test(clean) || /^2[2-7]/.test(clean)) return 'mastercard';
  if (/^3[47]/.test(clean)) return 'amex';
  
  return 'unknown';
}

/**
 * Validate entire card form
 */
export interface CardValidationResult {
  isValid: boolean;
  errors: {
    cardNumber?: string;
    cardholderName?: string;
    expiryMonth?: string;
    expiryYear?: string;
    cvv?: string;
  };
}

export function validateCardForm(data: {
  card_holder_name: string;
  card_number: string;
  expiry_month: string;
  expiry_year: string;
  cvv?: string;
}): CardValidationResult {
  const errors: CardValidationResult['errors'] = {};
  
  if (!validateCardholderName(data.card_holder_name)) {
    errors.cardholderName = 'Geçerli bir kart sahibi adı girin';
  }
  
  if (!validateCardNumber(data.card_number)) {
    errors.cardNumber = 'Geçersiz kart numarası';
  }
  
  if (!data.expiry_month || !data.expiry_year) {
    errors.expiryMonth = 'Son kullanma tarihi gerekli';
  } else if (!validateExpiryDate(data.expiry_month, data.expiry_year)) {
    errors.expiryMonth = 'Geçersiz veya süresi dolmuş tarih';
  }
  
  if (data.cvv && !validateCVV(data.cvv)) {
    errors.cvv = 'Geçersiz CVV';
  }
  
  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}
