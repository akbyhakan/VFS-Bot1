import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Settings } from '@/pages/Settings';
import { usePaymentCard } from '@/hooks/usePaymentCard';
import { webhookApi } from '@/services/paymentCard';

vi.mock('@/hooks/usePaymentCard');
vi.mock('@/services/paymentCard', () => ({
  webhookApi: {
    getWebhookUrls: vi.fn(),
  },
}));

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
    vi.mocked(webhookApi.getWebhookUrls).mockResolvedValue({
      appointment_webhook: 'https://example.com/appointment',
      payment_webhook: 'https://example.com/payment',
      base_url: 'https://example.com',
    });
  });

  it('renders settings page with title', async () => {
    render(<Settings />);
    
    expect(screen.getByText('Ayarlar')).toBeInTheDocument();
  });

  it('loads webhook URLs on mount', async () => {
    render(<Settings />);
    
    await waitFor(() => {
      expect(webhookApi.getWebhookUrls).toHaveBeenCalled();
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

    render(<Settings />);
    
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

    render(<Settings />);
    
    // Just check that the page renders when in loading state
    expect(screen.getByText('Ayarlar')).toBeInTheDocument();
  });
});
