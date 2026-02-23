import { useEffect, useRef, useCallback } from 'react';
import { logger } from '@/utils/logger';
import { toast } from 'sonner';

interface UseAutoSaveOptions<T> {
  /**
   * Data to save
   */
  data: T;
  
  /**
   * Function to save the data
   */
  onSave: (data: T) => void | Promise<void>;
  
  /**
   * Delay in milliseconds before auto-saving (default: 2000ms)
   */
  delay?: number;
  
  /**
   * Whether auto-save is enabled (default: true)
   */
  enabled?: boolean;
  
  /**
   * Show toast notification on save (default: false)
   */
  showToast?: boolean;
  
  /**
   * Function to check if data is valid before saving
   */
  validate?: (data: T) => boolean;
  
  /**
   * Storage key for localStorage persistence
   */
  storageKey?: string;
}

/**
 * Hook for auto-saving form data
 * Automatically saves data after a delay when it changes
 * Optionally persists to localStorage for draft recovery
 */
export function useAutoSave<T>({
  data,
  onSave,
  delay = 2000,
  enabled = true,
  showToast = false,
  validate,
  storageKey,
}: UseAutoSaveOptions<T>) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const isSavingRef = useRef(false);
  const lastSavedDataRef = useRef<string>();

  // Load draft from localStorage on mount
  useEffect(() => {
    if (storageKey) {
      const draft = localStorage.getItem(storageKey);
      if (draft) {
        try {
          // Draft is available but we don't auto-load it
          // Instead, we just make it available
          logger.log('Draft available in localStorage:', storageKey);
        } catch (error) {
          logger.error('Failed to parse draft:', error);
        }
      }
    }
  }, [storageKey]);

  // Save to localStorage
  const saveToLocalStorage = useCallback((data: T) => {
    if (storageKey) {
      try {
        localStorage.setItem(storageKey, JSON.stringify(data));
      } catch (error) {
        logger.error('Failed to save draft to localStorage:', error);
      }
    }
  }, [storageKey]);

  // Auto-save logic
  useEffect(() => {
    if (!enabled || isSavingRef.current) {
      return;
    }

    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Convert data to string for comparison
    const dataString = JSON.stringify(data);
    
    // Don't save if data hasn't changed
    if (dataString === lastSavedDataRef.current) {
      return;
    }

    // Set new timeout
    timeoutRef.current = setTimeout(async () => {
      // Validate data if validator is provided
      if (validate && !validate(data)) {
        return;
      }

      isSavingRef.current = true;
      
      try {
        // Save to localStorage
        saveToLocalStorage(data);
        
        // Call save function
        await onSave(data);
        
        // Update last saved data
        lastSavedDataRef.current = dataString;
        
        if (showToast) {
          toast.success('Otomatik kaydedildi', {
            duration: 2000,
          });
        }
      } catch (error) {
        logger.error('Auto-save failed:', error);
        if (showToast) {
          toast.error('Otomatik kaydetme başarısız');
        }
      } finally {
        isSavingRef.current = false;
      }
    }, delay);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [data, onSave, delay, enabled, validate, showToast, saveToLocalStorage]);

  // Clear draft from localStorage
  const clearDraft = useCallback(() => {
    if (storageKey) {
      localStorage.removeItem(storageKey);
    }
  }, [storageKey]);

  // Load draft from localStorage
  const loadDraft = useCallback((): T | null => {
    if (storageKey) {
      const draft = localStorage.getItem(storageKey);
      if (draft) {
        try {
          return JSON.parse(draft);
        } catch (error) {
          logger.error('Failed to parse draft:', error);
        }
      }
    }
    return null;
  }, [storageKey]);

  return {
    clearDraft,
    loadDraft,
  };
}
