import { create } from 'zustand';

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

export const useNotificationStore = create<NotificationState>((set) => ({
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

      const notifications = [newNotification, ...state.notifications].slice(0, MAX_NOTIFICATIONS);
      const unreadCount = notifications.filter((n) => !n.read).length;

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
      const notifications = state.notifications.filter((n) => n.id !== id);
      const unreadCount = notifications.filter((n) => !n.read).length;
      return { notifications, unreadCount };
    }),
}));
