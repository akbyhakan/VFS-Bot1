import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useBotStore } from '@/store/botStore';
import { BOT_STATUS } from '@/utils/constants';

// Mock the websocket service
vi.mock('@/services/websocket', () => ({
  websocketService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    send: vi.fn(),
    onMessage: vi.fn(() => vi.fn()),
    onOpen: vi.fn(() => vi.fn()),
    onClose: vi.fn(() => vi.fn()),
    onError: vi.fn(() => vi.fn()),
  },
}));

describe('useWebSocket', () => {
  beforeEach(() => {
    // Reset store before each test
    useBotStore.setState({
      logs: [],
      isConnected: false,
      running: false,
      status: BOT_STATUS.STOPPED,
      last_check: null,
      stats: {
        slots_found: 0,
        appointments_booked: 0,
        active_users: 0,
      },
    });
  });

  it('should initialize WebSocket connection', () => {
    const { result } = renderHook(() => useWebSocket());
    
    expect(result.current.isConnected).toBe(false);
  });

  it('should handle connection state', async () => {
    const { result } = renderHook(() => useWebSocket());
    
    // Simulate connection
    useBotStore.setState({ isConnected: true });
    
    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });

  it('should provide send method', () => {
    const { result } = renderHook(() => useWebSocket());
    
    expect(typeof result.current.send).toBe('function');
  });
});
