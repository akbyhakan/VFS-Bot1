import { useEffect, useCallback, useRef } from 'react';
import { websocketService } from '@/services/websocket';
import { useBotStore } from '@/store/botStore';
import { useNotificationStore } from '@/store/notificationStore';
import type { WebSocketMessage, LogEntry } from '@/types/api';
import { isBotStatusData, isLogEntry, isStatsData } from '@/utils/typeGuards';
import { logger } from '@/utils/logger';
import { WEBSOCKET_THROTTLE } from '@/utils/constants';
import { useTranslation } from 'react-i18next';

const { LOG_BUFFER_TIME, STATUS_THROTTLE_TIME } = WEBSOCKET_THROTTLE;

export function useWebSocket() {
  const { updateStatus, addLogs, setConnected } = useBotStore();
  const { addNotification } = useNotificationStore();
  const { t } = useTranslation();
  
  // Store refs for store functions to prevent stale closures
  const addNotificationRef = useRef(addNotification);
  const addLogsRef = useRef(addLogs);
  const updateStatusRef = useRef(updateStatus);
  const setConnectedRef = useRef(setConnected);
  const tRef = useRef(t);

  // Keep refs up to date (ref changes don't trigger re-renders)
  useEffect(() => {
    addNotificationRef.current = addNotification;
    addLogsRef.current = addLogs;
    updateStatusRef.current = updateStatus;
    setConnectedRef.current = setConnected;
    tRef.current = t;
  });
  
  // Buffers for batching
  const logBuffer = useRef<LogEntry[]>([]);
  const logTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStatusUpdate = useRef<Record<string, unknown> | null>(null);

  // Maximum buffer size to prevent memory leak
  const MAX_LOG_BUFFER_SIZE = 100;

  // Flush log buffer - now with stable dependencies
  const flushLogs = useCallback(() => {
    if (logBuffer.current.length > 0) {
      addLogsRef.current(logBuffer.current);
      logBuffer.current = [];
    }
    logTimerRef.current = null;
  }, []); // Empty dependency array - stable reference

  // Flush status update - now with stable dependencies
  const flushStatus = useCallback(() => {
    if (pendingStatusUpdate.current) {
      updateStatusRef.current(pendingStatusUpdate.current);
      pendingStatusUpdate.current = null;
    }
    statusTimerRef.current = null;
  }, []); // Empty dependency array - stable reference

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
              addNotificationRef.current({
                title: tRef.current('notifications.botStarted'),
                message: tRef.current('notifications.botStartedMessage'),
                type: 'success',
              });
            } else if (status === 'stopped') {
              addNotificationRef.current({
                title: tRef.current('notifications.botStopped'),
                message: tRef.current('notifications.botStoppedMessage'),
                type: 'info',
              });
            } else if (status === 'error') {
              addNotificationRef.current({
                title: tRef.current('notifications.botError'),
                message: message.data.message || tRef.current('notifications.botErrorMessage'),
                type: 'error',
              });
            } else if (status === 'restarting') {
              addNotificationRef.current({
                title: tRef.current('notifications.botRestarting'),
                message: tRef.current('notifications.botRestartingMessage'),
                type: 'warning',
              });
            } else if (status === 'rate_limited') {
              addNotificationRef.current({
                title: tRef.current('notifications.rateLimitWarning'),
                message: tRef.current('notifications.rateLimitMessage'),
                type: 'warning',
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
              addNotificationRef.current({
                title: tRef.current('notifications.slotFound'),
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
            addNotificationRef.current({
              title: notificationData.title || tRef.current('notifications.defaultTitle'),
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
    [flushLogs, flushStatus] // Now stable callbacks
  );

  const handleOpen = useCallback(() => {
    setConnectedRef.current(true);
  }, []); // Stable reference

  const handleClose = useCallback(() => {
    setConnectedRef.current(false);
    // Flush any pending updates
    if (logTimerRef.current) {
      clearTimeout(logTimerRef.current);
      flushLogs();
    }
    if (statusTimerRef.current) {
      clearTimeout(statusTimerRef.current);
      flushStatus();
    }
  }, [flushLogs, flushStatus]); // Now stable callbacks

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
  }, [handleMessage, handleOpen, handleClose, handleError]); // Now stable dependencies

  return {
    isConnected: useBotStore((state) => state.isConnected),
    send: websocketService.send.bind(websocketService),
  };
}
