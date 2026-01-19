import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { Login } from '@/pages/Login';
import { useAuth } from '@/hooks/useAuth';

vi.mock('@/hooks/useAuth');

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: null }),
  };
});

describe('Login', () => {
  const mockLogin = vi.fn();
  const mockClearError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      login: mockLogin,
      isAuthenticated: false,
      error: null,
      clearError: mockClearError,
      isLoading: false,
      logout: vi.fn(),
      checkAuth: vi.fn(),
    });
  });

  const renderLogin = () => {
    return render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );
  };

  it('renders login form', () => {
    renderLogin();
    
    expect(screen.getByText('VFS-Bot Dashboard')).toBeInTheDocument();
    expect(screen.getByLabelText(/Kullanıcı Adı/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Şifre/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Giriş Yap/i })).toBeInTheDocument();
  });

  it('shows validation errors for empty fields', async () => {
    renderLogin();
    
    const submitButton = screen.getByRole('button', { name: /Giriş Yap/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Kullanıcı adı gerekli/i)).toBeInTheDocument();
      expect(screen.getByText(/Şifre gerekli/i)).toBeInTheDocument();
    });
  });

  it('calls login function with correct credentials', async () => {
    mockLogin.mockResolvedValue(undefined);
    renderLogin();
    
    const usernameInput = screen.getByLabelText(/Kullanıcı Adı/i);
    const passwordInput = screen.getByLabelText(/Şifre/i);
    const submitButton = screen.getByRole('button', { name: /Giriş Yap/i });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        { username: 'testuser', password: 'password123' },
        false
      );
    });
  });

  it('handles remember me checkbox', async () => {
    mockLogin.mockResolvedValue(undefined);
    renderLogin();
    
    const usernameInput = screen.getByLabelText(/Kullanıcı Adı/i);
    const passwordInput = screen.getByLabelText(/Şifre/i);
    const rememberMeCheckbox = screen.getByLabelText(/Beni hatırla/i);
    const submitButton = screen.getByRole('button', { name: /Giriş Yap/i });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(rememberMeCheckbox);
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        { username: 'testuser', password: 'password123' },
        true
      );
    });
  });

  it('redirects when already authenticated', () => {
    vi.mocked(useAuth).mockReturnValue({
      login: mockLogin,
      isAuthenticated: true,
      error: null,
      clearError: mockClearError,
      isLoading: false,
      logout: vi.fn(),
      checkAuth: vi.fn(),
    });

    renderLogin();

    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
  });

  it('shows loading state during login', async () => {
    renderLogin();
    
    const usernameInput = screen.getByLabelText(/Kullanıcı Adı/i);
    const passwordInput = screen.getByLabelText(/Şifre/i);
    const submitButton = screen.getByRole('button', { name: /Giriş Yap/i });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(submitButton);

    // During submission, button should be disabled
    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });
  });
});
