import { useEffect, useCallback, useRef } from 'react';
import { websocketService } from '@/services/websocket';
import { useBotStore } from '@/store/botStore';
import { useNotificationStore } from '@/store/notificationStore';
import type { WebSocketMessage, LogEntry } from '@/types/api';
import { isBotStatusData, isLogEntry, isStatsData } from '@/utils/typeGuards';
import { logger } from '@/utils/logger';
import { WEBSOCKET_THROTTLE } from '@/utils/constants';

const { LOG_BUFFER_TIME, STATUS_THROTTLE_TIME } = WEBSOCKET_THROTTLE;

export function useWebSocket() {
  const { updateStatus, addLogs, setConnected } = useBotStore();
  const { addNotification } = useNotificationStore();
  
  // Buffers for batching
  const logBuffer = useRef<LogEntry[]>([]);
  const logTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStatusUpdate = useRef<Record<string, unknown> | null>(null);

  // Maximum buffer size to prevent memory leak
  const MAX_LOG_BUFFER_SIZE = 100;

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
            
            // Create notifications for status changes
            const status = message.data.status;
            if (status === 'running') {
              addNotification({
                title: 'Bot Başlatıldı',
                message: 'VFS Bot başarıyla çalışmaya başladı',
                type: 'success',
              });
            } else if (status === 'stopped') {
              addNotification({
                title: 'Bot Durduruldu',
                message: 'VFS Bot durduruldu',
                type: 'info',
              });
            }
          }
          break;
        case 'log':
          if (isLogEntry(message.data)) {
            // Buffer logs for batch addition with bounds checking
            logBuffer.current.push(message.data);
            
            // Check for slot found notification
            if (message.data.level === 'SUCCESS' && message.data.message.toLowerCase().includes('slot')) {
              addNotification({
                title: 'Slot Bulundu!',
                message: message.data.message,
                type: 'success',
              });
            }
            
            // Flush immediately if buffer is too large to prevent memory leak
            if (logBuffer.current.length >= MAX_LOG_BUFFER_SIZE) {
              if (logTimerRef.current) {
                clearTimeout(logTimerRef.current);
              }
              flushLogs();
            } else if (!logTimerRef.current) {
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
        case 'notification':
          // Handle explicit notification messages
          if (message.data && typeof message.data === 'object') {
            const notificationData = message.data as {
              title?: string;
              message?: string;
              type?: 'success' | 'error' | 'warning' | 'info';
            };
            addNotification({
              title: notificationData.title || 'Bildirim',
              message: notificationData.message || '',
              type: notificationData.type || 'info',
            });
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
    [flushLogs, flushStatus, addNotification]
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
