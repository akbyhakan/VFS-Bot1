import { useNotificationStore } from '@/store/notificationStore';
import { useEffect, useRef } from 'react';
import { formatRelativeTime } from '@/utils/helpers';
import { CheckCheck, Trash2, X, AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '@/utils/helpers';
import { useTranslation } from 'react-i18next';

interface NotificationPanelProps {
  bellButtonRef: React.RefObject<HTMLButtonElement>;
}

export function NotificationPanel({ bellButtonRef }: NotificationPanelProps) {
  const { notifications, isOpen, unreadCount, togglePanel, markAllAsRead, clearAll, removeNotification } = useNotificationStore();
  const panelRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  // Close panel when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        // Check if click is on the bell button using ref
        if (bellButtonRef.current && bellButtonRef.current.contains(event.target as Node)) {
          return;
        }
        if (isOpen) {
          togglePanel();
        }
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen, togglePanel, bellButtonRef]);

  if (!isOpen) return null;

  const getIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'info':
      default:
        return <Info className="w-5 h-5 text-blue-500" />;
    }
  };

  return (
    <div
      ref={panelRef}
      className="absolute top-14 right-0 w-96 max-h-[32rem] glass border border-dark-600 rounded-lg shadow-xl z-50 flex flex-col"
      role="dialog"
      aria-label={t('notificationPanel.panelLabel')}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-dark-700">
        <h3 className="font-semibold text-lg">{t('notificationPanel.title')}</h3>
        <button
          onClick={togglePanel}
          className="p-1 text-dark-400 hover:text-dark-100 rounded"
          aria-label={t('notificationPanel.closePanel')}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Notifications List */}
      <div className="flex-1 overflow-y-auto max-h-80">
        {notifications.length === 0 ? (
          <div className="p-8 text-center text-dark-400">
            <Info className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>{t('notificationPanel.noNotifications')}</p>
          </div>
        ) : (
          <div className="divide-y divide-dark-700">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className={cn(
                  'p-4 hover:bg-dark-800/50 transition-colors relative',
                  !notification.read && 'bg-dark-800/30'
                )}
              >
                <div className="flex gap-3">
                  <div className="flex-shrink-0 mt-1">
                    {getIcon(notification.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-medium text-sm">{notification.title}</h4>
                      <button
                        onClick={() => removeNotification(notification.id)}
                        className="text-dark-400 hover:text-red-500 flex-shrink-0"
                        aria-label={t('notificationPanel.deleteNotification')}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-sm text-dark-400 mt-1">{notification.message}</p>
                    <p className="text-xs text-dark-500 mt-1">
                      {formatRelativeTime(notification.timestamp)}
                    </p>
                  </div>
                </div>
                {!notification.read && (
                  <div className="absolute top-4 right-12 w-2 h-2 bg-primary-500 rounded-full" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Actions */}
      {notifications.length > 0 && (
        <div className="p-3 border-t border-dark-700 flex gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm text-dark-300 hover:text-dark-100 hover:bg-dark-800 rounded transition-colors"
            >
              <CheckCheck className="w-4 h-4" />
              {t('notificationPanel.markAllRead')}
            </button>
          )}
          <button
            onClick={clearAll}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm text-dark-300 hover:text-red-400 hover:bg-dark-800 rounded transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            {t('notificationPanel.clearAll')}
          </button>
        </div>
      )}
    </div>
  );
}
