import { useState, useCallback, useRef, useEffect } from 'react';
import { toast } from 'sonner';

interface UseAsyncActionOptions<T> {
  /**
   * Success message to display
   */
  successMessage?: string;
  
  /**
   * Error message to display (or function to generate message from error)
   */
  errorMessage?: string | ((error: Error) => string);
  
  /**
   * Callback on success
   */
  onSuccess?: (data: T) => void;
  
  /**
   * Callback on error
   */
  onError?: (error: Error) => void;
  
  /**
   * Whether to show toast notifications
   */
  showToast?: boolean;
}

interface UseAsyncActionResult<T, Args extends unknown[]> {
  /**
   * Execute the async action
   */
  execute: (...args: Args) => Promise<T | undefined>;
  
  /**
   * Loading state
   */
  isLoading: boolean;
  
  /**
   * Error state
   */
  error: Error | null;
  
  /**
   * Result data
   */
  data: T | null;
  
  /**
   * Reset state
   */
  reset: () => void;
}

/**
 * Custom hook for handling async actions with loading/error states
 * Provides consistent pattern for loading states, error handling, and success notifications
 * 
 * @example
 * ```tsx
 * const deleteUser = useCallback(
 *   async (userId: string) => {
 *     return await api.deleteUser(userId);
 *   },
 *   []
 * );
 * 
 * const { execute, isLoading, error } = useAsyncAction(
 *   deleteUser,
 *   {
 *     successMessage: 'User deleted successfully',
 *     errorMessage: 'Failed to delete user',
 *   }
 * );
 * 
 * <Button onClick={() => execute(userId)} isLoading={isLoading}>
 *   Delete
 * </Button>
 * ```
 * 
 * @important The action function MUST be wrapped with useCallback to prevent unnecessary
 * recreations of the execute function on every render. Not doing so will cause performance issues.
 */
export function useAsyncAction<T, Args extends unknown[] = []>(
  action: (...args: Args) => Promise<T>,
  options: UseAsyncActionOptions<T> = {}
): UseAsyncActionResult<T, Args> {
  const {
    successMessage,
    errorMessage,
    onSuccess,
    onError,
    showToast = true,
  } = options;

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<T | null>(null);

  // Use ref to avoid recreating execute when action changes
  // This allows for better performance while still supporting dynamic actions
  const actionRef = useRef(action);
  useEffect(() => {
    actionRef.current = action;
  }, [action]);

  const execute = useCallback(
    async (...args: Args): Promise<T | undefined> => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await actionRef.current(...args);
        setData(result);
        
        if (showToast && successMessage) {
          toast.success(successMessage);
        }
        
        onSuccess?.(result);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('An unknown error occurred');
        setError(error);
        
        if (showToast) {
          const message = typeof errorMessage === 'function' 
            ? errorMessage(error)
            : errorMessage || error.message;
          toast.error(message);
        }
        
        onError?.(error);
        return undefined;
      } finally {
        setIsLoading(false);
      }
    },
    [successMessage, errorMessage, onSuccess, onError, showToast]
  );

  const reset = useCallback(() => {
    setIsLoading(false);
    setError(null);
    setData(null);
  }, []);

  return {
    execute,
    isLoading,
    error,
    data,
    reset,
  };
}
