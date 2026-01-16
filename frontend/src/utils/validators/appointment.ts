/**
 * Appointment form validation utilities
 * Centralized validation logic for appointment requests
 */

/**
 * Validate birth date - must be in the past
 */
export function validateBirthDate(date: string): boolean {
  if (!date) return false;
  
  const [day, month, year] = date.split('/').map(Number);
  if (!day || !month || !year) return false;
  
  const inputDate = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  return inputDate <= today;
}

/**
 * Validate passport issue date - must be in the past
 */
export function validatePassportIssueDate(date: string): boolean {
  if (!date) return false;
  
  const [day, month, year] = date.split('/').map(Number);
  if (!day || !month || !year) return false;
  
  const inputDate = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  return inputDate <= today;
}

/**
 * Validate passport expiry date - must be at least 3 months in the future
 */
export function validatePassportExpiryDate(date: string): boolean {
  if (!date) return false;
  
  const [day, month, year] = date.split('/').map(Number);
  if (!day || !month || !year) return false;
  
  const inputDate = new Date(year, month - 1, day);
  const threeMonthsFromNow = new Date();
  threeMonthsFromNow.setMonth(threeMonthsFromNow.getMonth() + 3);
  
  return inputDate >= threeMonthsFromNow;
}

/**
 * Validate email format
 */
export function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Validate Turkish phone number format
 * 10 digits, not starting with 0
 * Example: 5551234567 (not 05551234567)
 */
export function validateTurkishPhone(phone: string): boolean {
  return /^[1-9]\d{9}$/.test(phone);
}

/**
 * Validate passport number format
 * Basic validation - alphanumeric, 6-20 characters
 */
export function validatePassportNumber(passport: string): boolean {
  return /^[A-Z0-9]{6,20}$/i.test(passport);
}

/**
 * Validate preferred date format
 * Must be in DD/MM/YYYY format and in the future
 */
export function validatePreferredDate(date: string): boolean {
  if (!date) return false;
  
  const [day, month, year] = date.split('/').map(Number);
  if (!day || !month || !year) return false;
  
  const inputDate = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  return inputDate >= today;
}
