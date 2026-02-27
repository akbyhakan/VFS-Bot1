import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Settings } from '@/pages/Settings';
import { usePaymentCard } from '@/hooks/usePaymentCard';

vi.mock('@/hooks/usePaymentCard');
vi.mock('@/hooks/useWebhook', () => ({
  useWebhookUrls: vi.fn().mockReturnValue({
    data: {
      appointment_webhook: 'https://example.com/appointment',
      payment_webhook: 'https://example.com/payment',
      base_url: 'https://example.com',
    },
    isLoading: false,
  }),
  useUserWebhook: vi.fn().mockReturnValue({ data: null, isLoading: false }),
  useCreateWebhook: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteWebhook: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/hooks/useProxy', () => ({
  useProxyStats: vi.fn().mockReturnValue({ data: null, isLoading: false }),
  useProxyList: vi.fn().mockReturnValue({ data: null, isLoading: false }),
  useUploadProxy: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
  useClearProxies: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('Settings', () => {
  const mockSaveCard = vi.fn();
  const mockDeleteCard = vi.fn();
  const mockReload = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePaymentCard).mockReturnValue({
      card: null,
      loading: false,
      error: null,
      saving: false,
      deleting: false,
      saveCard: mockSaveCard,
      deleteCard: mockDeleteCard,
      reload: mockReload,
    });
  });

  it('renders settings page with title', async () => {
    renderWithClient(<Settings />);
    
    expect(screen.getByText('Ayarlar')).toBeInTheDocument();
  });

  it('loads webhook URLs on mount', async () => {
    const { useWebhookUrls } = await import('@/hooks/useWebhook');
    renderWithClient(<Settings />);
    
    await waitFor(() => {
      expect(useWebhookUrls).toHaveBeenCalled();
    });
  });

  it('shows saved card when available', () => {
    vi.mocked(usePaymentCard).mockReturnValue({
      card: {
        id: 1,
        card_holder_name: 'John Doe',
        card_number_masked: '**** **** **** 1234',
        expiry_month: '12',
        expiry_year: '2025',
        created_at: '2024-01-01T00:00:00Z',
      },
      loading: false,
      error: null,
      saving: false,
      deleting: false,
      saveCard: mockSaveCard,
      deleteCard: mockDeleteCard,
      reload: mockReload,
    });

    renderWithClient(<Settings />);
    
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('handles loading state', () => {
    vi.mocked(usePaymentCard).mockReturnValue({
      card: null,
      loading: true,
      error: null,
      saving: false,
      deleting: false,
      saveCard: mockSaveCard,
      deleteCard: mockDeleteCard,
      reload: mockReload,
    });

    renderWithClient(<Settings />);
    
    // Just check that the page renders when in loading state
    expect(screen.getByText('Ayarlar')).toBeInTheDocument();
  });
});
