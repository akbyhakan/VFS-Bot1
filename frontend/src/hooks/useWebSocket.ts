import { useEffect, useCallback } from 'react';
import { websocketService } from '@/services/websocket';
import { useBotStore } from '@/store/botStore';
import type { WebSocketMessage, LogEntry } from '@/types/api';

export function useWebSocket() {
  const { updateStatus, addLog, setConnected } = useBotStore();

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case 'status':
          updateStatus(message.data);
          break;
        case 'log':
          addLog(message.data as LogEntry);
          break;
        case 'stats':
          updateStatus({ stats: message.data });
          break;
        case 'ping':
          // Respond to ping to keep connection alive
          websocketService.send({ type: 'pong' });
          break;
        default:
          console.log('Unknown message type:', message.type);
      }
    },
    [updateStatus, addLog]
  );

  const handleOpen = useCallback(() => {
    setConnected(true);
  }, [setConnected]);

  const handleClose = useCallback(() => {
    setConnected(false);
  }, [setConnected]);

  const handleError = useCallback((error: Event) => {
    console.error('WebSocket error:', error);
  }, []);

  useEffect(() => {
    // Connect WebSocket
    websocketService.connect();

    // Setup event handlers
    const unsubMessage = websocketService.onMessage(handleMessage);
    const unsubOpen = websocketService.onOpen(handleOpen);
    const unsubClose = websocketService.onClose(handleClose);
    const unsubError = websocketService.onError(handleError);

    // Cleanup on unmount
    return () => {
      unsubMessage();
      unsubOpen();
      unsubClose();
      unsubError();
      websocketService.disconnect();
    };
  }, [handleMessage, handleOpen, handleClose, handleError]);

  return {
    isConnected: useBotStore((state) => state.isConnected),
    send: websocketService.send.bind(websocketService),
  };
}
