import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Input } from '@/components/ui/Input';

describe('Input', () => {
  it('renders without label', () => {
    render(<Input placeholder="Enter text" />);
    expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument();
  });

  it('renders with label', () => {
    render(<Input label="Username" placeholder="Enter username" />);
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
  });

  it('displays error message', () => {
    render(<Input label="Email" error="Invalid email" />);
    const errorElement = screen.getByRole('alert');
    expect(errorElement).toHaveTextContent('Invalid email');
    expect(errorElement).toHaveClass('text-red-400');
  });

  it('displays hint text', () => {
    render(<Input label="Password" hint="Must be at least 8 characters" />);
    expect(screen.getByText('Must be at least 8 characters')).toBeInTheDocument();
  });

  it('hides hint when error is present', () => {
    render(
      <Input
        label="Password"
        hint="Must be at least 8 characters"
        error="Password is required"
      />
    );
    expect(screen.queryByText('Must be at least 8 characters')).not.toBeInTheDocument();
    expect(screen.getByText('Password is required')).toBeInTheDocument();
  });

  it('renders with left icon', () => {
    const LeftIcon = () => <span data-testid="left-icon">Icon</span>;
    render(<Input leftIcon={<LeftIcon />} />);
    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
  });

  it('renders with right icon', () => {
    const RightIcon = () => <span data-testid="right-icon">Icon</span>;
    render(<Input rightIcon={<RightIcon />} />);
    expect(screen.getByTestId('right-icon')).toBeInTheDocument();
  });

  it('applies error styling when error prop is provided', () => {
    render(<Input error="Error message" />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveClass('border-red-500');
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });

  it('sets proper aria-describedby for accessibility', () => {
    render(<Input label="Test" error="Error text" />);
    const input = screen.getByRole('textbox');
    const describedBy = input.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(describedBy).toContain('error');
  });

  it('forwards ref correctly', () => {
    const ref = { current: null };
    render(<Input ref={ref as any} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it('accepts custom className', () => {
    render(<Input className="custom-class" />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveClass('custom-class');
  });

  it('handles different input types', () => {
    const { rerender } = render(<Input type="email" />);
    expect(screen.getByRole('textbox')).toHaveAttribute('type', 'email');

    rerender(<Input type="password" />);
    const passwordInput = document.querySelector('input[type="password"]');
    expect(passwordInput).toBeInTheDocument();
  });
});
