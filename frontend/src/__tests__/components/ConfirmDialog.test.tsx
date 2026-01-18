import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

describe('ConfirmDialog', () => {
  const defaultProps = {
    isOpen: true,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    title: 'Confirm Action',
    message: 'Are you sure?',
  };

  it('renders title and message', () => {
    render(<ConfirmDialog {...defaultProps} />);
    
    expect(screen.getByText('Confirm Action')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />);
    
    fireEvent.click(screen.getByText('Onayla'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when cancel button is clicked', () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />);
    
    fireEvent.click(screen.getByText('İptal'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('uses custom button text', () => {
    render(
      <ConfirmDialog
        {...defaultProps}
        confirmText="Yes, delete"
        cancelText="No, keep"
      />
    );
    
    expect(screen.getByText('Yes, delete')).toBeInTheDocument();
    expect(screen.getByText('No, keep')).toBeInTheDocument();
  });

  it('shows loading state on confirm button', () => {
    render(<ConfirmDialog {...defaultProps} isLoading />);
    
    const confirmButton = screen.getByText('Onayla').closest('button');
    expect(confirmButton).toBeDisabled();
  });

  it('has correct aria attributes', () => {
    render(<ConfirmDialog {...defaultProps} />);
    
    expect(screen.getByRole('alertdialog')).toHaveAttribute('aria-modal', 'true');
  });
});
