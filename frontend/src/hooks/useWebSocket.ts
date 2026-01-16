import { useEffect, useCallback, useRef } from 'react';
import { websocketService } from '@/services/websocket';
import { useBotStore } from '@/store/botStore';
import type { WebSocketMessage, LogEntry } from '@/types/api';
import { isBotStatusData, isLogEntry, isStatsData } from '@/utils/typeGuards';
import { logger } from '@/utils/logger';

const LOG_BUFFER_TIME = 100; // ms
const STATUS_THROTTLE_TIME = 500; // ms

export function useWebSocket() {
  const { updateStatus, addLog, addLogs, setConnected } = useBotStore();
  
  // Buffers for batching
  const logBuffer = useRef<LogEntry[]>([]);
  const logTimerRef = useRef<NodeJS.Timeout | null>(null);
  const statusTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingStatusUpdate = useRef<Record<string, unknown> | null>(null);

  // Flush log buffer
  const flushLogs = useCallback(() => {
    if (logBuffer.current.length > 0) {
      addLogs(logBuffer.current);
      logBuffer.current = [];
    }
    logTimerRef.current = null;
  }, [addLogs]);

  // Flush status update
  const flushStatus = useCallback(() => {
    if (pendingStatusUpdate.current) {
      updateStatus(pendingStatusUpdate.current);
      pendingStatusUpdate.current = null;
    }
    statusTimerRef.current = null;
  }, [updateStatus]);

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case 'status':
          if (isBotStatusData(message.data)) {
            // Throttle status updates
            pendingStatusUpdate.current = {
              ...pendingStatusUpdate.current,
              ...message.data,
            };
            
            if (!statusTimerRef.current) {
              statusTimerRef.current = setTimeout(flushStatus, STATUS_THROTTLE_TIME);
            }
          }
          break;
        case 'log':
          if (isLogEntry(message.data)) {
            // Buffer logs for batch addition
            logBuffer.current.push(message.data);
            
            if (!logTimerRef.current) {
              logTimerRef.current = setTimeout(flushLogs, LOG_BUFFER_TIME);
            }
          }
          break;
        case 'stats':
          if (isStatsData(message.data)) {
            pendingStatusUpdate.current = {
              ...pendingStatusUpdate.current,
              stats: message.data,
            };
            
            if (!statusTimerRef.current) {
              statusTimerRef.current = setTimeout(flushStatus, STATUS_THROTTLE_TIME);
            }
          }
          break;
        case 'ping':
          // Respond to ping to keep connection alive
          websocketService.send({ type: 'pong' });
          break;
        default:
          logger.warn('Unknown message type:', message.type);
      }
    },
    [flushLogs, flushStatus]
  );

  const handleOpen = useCallback(() => {
    setConnected(true);
  }, [setConnected]);

  const handleClose = useCallback(() => {
    setConnected(false);
    // Flush any pending updates
    if (logTimerRef.current) {
      clearTimeout(logTimerRef.current);
      flushLogs();
    }
    if (statusTimerRef.current) {
      clearTimeout(statusTimerRef.current);
      flushStatus();
    }
  }, [setConnected, flushLogs, flushStatus]);

  const handleError = useCallback((error: Event) => {
    logger.error('WebSocket error:', error);
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
      // Clear timers
      if (logTimerRef.current) {
        clearTimeout(logTimerRef.current);
      }
      if (statusTimerRef.current) {
        clearTimeout(statusTimerRef.current);
      }
      
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
