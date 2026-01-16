import { WEBSOCKET_RECONNECT } from '@/utils/constants';
import { tokenManager } from '@/utils/tokenManager';
import { logger } from '@/utils/logger';
import type { WebSocketMessage } from '@/types/api';

type MessageHandler = (message: WebSocketMessage) => void;
type ErrorHandler = (error: Event) => void;
type CloseHandler = () => void;
type OpenHandler = () => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();
  private closeHandlers: Set<CloseHandler> = new Set();
  private openHandlers: Set<OpenHandler> = new Set();
  private isIntentionallyClosed = false;

  connect(): void {
    this.isIntentionallyClosed = false;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      logger.info('WebSocket connected');
      this.reconnectAttempts = 0;

      // Send authentication token
      const token = tokenManager.getToken();
      if (token && this.ws) {
        this.ws.send(JSON.stringify({ token }));
      }

      this.openHandlers.forEach((handler) => handler());
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.messageHandlers.forEach((handler) => handler(message));
      } catch (error) {
        logger.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      logger.error('WebSocket error:', error);
      this.errorHandlers.forEach((handler) => handler(error));
    };

    this.ws.onclose = () => {
      logger.info('WebSocket disconnected');
      this.closeHandlers.forEach((handler) => handler());

      if (!this.isIntentionallyClosed) {
        this.scheduleReconnect();
      }
    };
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.reconnectAttempts = 0;
  }

  send(data: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      logger.warn('WebSocket is not connected');
    }
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  onClose(handler: CloseHandler): () => void {
    this.closeHandlers.add(handler);
    return () => this.closeHandlers.delete(handler);
  }

  onOpen(handler: OpenHandler): () => void {
    this.openHandlers.add(handler);
    return () => this.openHandlers.delete(handler);
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= WEBSOCKET_RECONNECT.MAX_ATTEMPTS) {
      logger.error('Max WebSocket reconnection attempts reached');
      return;
    }

    const delay = Math.min(
      WEBSOCKET_RECONNECT.INITIAL_DELAY *
        Math.pow(WEBSOCKET_RECONNECT.BACKOFF_MULTIPLIER, this.reconnectAttempts),
      WEBSOCKET_RECONNECT.MAX_DELAY
    );

    logger.info(`Reconnecting WebSocket in ${delay}ms...`);
    this.reconnectAttempts++;

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

export const websocketService = new WebSocketService();
