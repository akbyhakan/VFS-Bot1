import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useAsyncAction } from '@/hooks/useAsyncAction';

describe('useAsyncAction', () => {
  it('should handle successful async action', async () => {
    const mockAction = vi.fn().mockResolvedValue('success');
    const mockOnSuccess = vi.fn();

    const { result } = renderHook(() =>
      useAsyncAction(mockAction, {
        successMessage: 'Action completed',
        onSuccess: mockOnSuccess,
        showToast: false,
      })
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBe(null);
    expect(result.current.data).toBe(null);

    let returnedData: string | undefined;
    await act(async () => {
      returnedData = await result.current.execute('test-arg');
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockAction).toHaveBeenCalledWith('test-arg');
    expect(mockOnSuccess).toHaveBeenCalledWith('success');
    expect(result.current.data).toBe('success');
    expect(result.current.error).toBe(null);
    expect(returnedData).toBe('success');
  });

  it('should handle failed async action', async () => {
    const mockError = new Error('Test error');
    const mockAction = vi.fn().mockRejectedValue(mockError);
    const mockOnError = vi.fn();

    const { result } = renderHook(() =>
      useAsyncAction(mockAction, {
        errorMessage: 'Action failed',
        onError: mockOnError,
        showToast: false,
      })
    );

    let returnedData: unknown;
    await act(async () => {
      returnedData = await result.current.execute();
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockOnError).toHaveBeenCalledWith(mockError);
    expect(result.current.error).toEqual(mockError);
    expect(result.current.data).toBe(null);
    expect(returnedData).toBe(undefined);
  });

  it('should reset state', async () => {
    const mockAction = vi.fn().mockResolvedValue('success');

    const { result } = renderHook(() =>
      useAsyncAction(mockAction, { showToast: false })
    );

    await act(async () => {
      await result.current.execute();
    });

    await waitFor(() => expect(result.current.data).toBe('success'));

    act(() => {
      result.current.reset();
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBe(null);
    expect(result.current.data).toBe(null);
  });

  it('should support custom error message function', async () => {
    const mockError = new Error('Test error');
    const mockAction = vi.fn().mockRejectedValue(mockError);

    const { result } = renderHook(() =>
      useAsyncAction(mockAction, {
        errorMessage: (error: Error) => `Custom: ${error.message}`,
        showToast: false,
      })
    );

    await act(async () => {
      await result.current.execute();
    });

    await waitFor(() => expect(result.current.error).toEqual(mockError));
  });
});
