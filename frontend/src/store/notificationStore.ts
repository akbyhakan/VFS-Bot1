import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  timestamp: string;
  read: boolean;
}

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  isOpen: boolean;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markAllAsRead: () => void;
  togglePanel: () => void;
  clearAll: () => void;
  removeNotification: (id: string) => void;
}

const MAX_NOTIFICATIONS = 50;

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set) => ({
      notifications: [],
      unreadCount: 0,
      isOpen: false,

      addNotification: (notification) =>
        set((state) => {
          const newNotification: Notification = {
            ...notification,
            id: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            read: false,
          };

          const allNotifications = [newNotification, ...state.notifications];
          const notifications = allNotifications.slice(0, MAX_NOTIFICATIONS);
          
          // Calculate how many unread notifications were dropped due to slice
          const droppedCount = allNotifications.length - notifications.length;
          const droppedUnread = droppedCount > 0
            ? allNotifications.slice(MAX_NOTIFICATIONS).filter(n => !n.read).length
            : 0;
          
          // Increment unreadCount for new notification, subtract any dropped unread
          const unreadCount = state.unreadCount + 1 - droppedUnread;

          return { notifications, unreadCount };
        }),

      markAllAsRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        })),

      togglePanel: () => set((state) => ({ isOpen: !state.isOpen })),

      clearAll: () =>
        set({
          notifications: [],
          unreadCount: 0,
          isOpen: false,
        }),

      removeNotification: (id) =>
        set((state) => {
          const removed = state.notifications.find((n) => n.id === id);
          const notifications = state.notifications.filter((n) => n.id !== id);
          // Only decrement if the removed notification was unread
          const unreadCount = removed && !removed.read ? state.unreadCount - 1 : state.unreadCount;
          return { notifications, unreadCount };
        }),
    }),
    {
      name: 'vfs-bot-notifications',
      partialize: (state) => ({
        notifications: state.notifications,
        unreadCount: state.unreadCount,
      }),
    }
  )
);
