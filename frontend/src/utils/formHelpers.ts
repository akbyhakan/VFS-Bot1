import type { Dispatch, SetStateAction } from 'react';

/**
 * Creates a field change handler that updates formData and clears the
 * associated error key from formErrors.
 *
 * @param transform - Optional transformation/validation function applied to
 *   the raw input value before updating state. Return the processed string to
 *   accept the change, or return `null` to reject it (the state update is
 *   skipped entirely).
 */
export function createFieldChangeHandler<T extends Record<string, string>>(
  setFormData: Dispatch<SetStateAction<T>>,
  setFormErrors: Dispatch<SetStateAction<Record<string, string>>>,
  fieldKey: keyof T,
  errorKey: string,
  transform?: (value: string) => string | null,
) {
  return (value: string) => {
    const transformed = transform ? transform(value) : value;
    if (transformed === null) return; // validation failed, ignore
    setFormData((prev) => ({ ...prev, [fieldKey]: transformed }));
    setFormErrors((prev) => {
      const next = { ...prev };
      delete next[errorKey];
      return next;
    });
  };
}
