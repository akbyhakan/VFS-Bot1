/**
 * Browser Notification utilities
 * Handles permission requests and sending notifications
 */

/**
 * Request notification permission from the user
 * @returns The permission state
 */
export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (!('Notification' in window)) {
    console.warn('This browser does not support desktop notifications');
    return 'denied';
  }

  if (Notification.permission === 'granted') {
    return 'granted';
  }

  if (Notification.permission !== 'denied') {
    return await Notification.requestPermission();
  }

  return Notification.permission;
}

/**
 * Send a browser notification
 * @param title - Notification title
 * @param body - Notification body text
 * @param options - Additional notification options
 */
export async function sendBrowserNotification(
  title: string,
  body: string,
  options?: NotificationOptions
): Promise<void> {
  if (!('Notification' in window)) {
    console.warn('This browser does not support desktop notifications');
    return;
  }

  if (Notification.permission === 'granted') {
    new Notification(title, {
      body,
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      tag: 'vfs-bot',
      requireInteraction: false,
      ...options,
    });
  } else if (Notification.permission !== 'denied') {
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      new Notification(title, {
        body,
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        tag: 'vfs-bot',
        requireInteraction: false,
        ...options,
      });
    }
  }
}

/**
 * Check if notifications are supported and permitted
 */
export function isNotificationSupported(): boolean {
  return 'Notification' in window;
}

/**
 * Check if notification permission is granted
 */
export function isNotificationPermitted(): boolean {
  return isNotificationSupported() && Notification.permission === 'granted';
}

/**
 * Send appointment found notification
 */
export async function notifyAppointmentFound(details: string): Promise<void> {
  await sendBrowserNotification(
    '🎉 Randevu Bulundu!',
    details,
    {
      requireInteraction: true,
      tag: 'appointment-found',
    }
  );
}

/**
 * Send bot error notification
 */
export async function notifyBotError(error: string): Promise<void> {
  await sendBrowserNotification(
    '⚠️ Bot Hatası',
    error,
    {
      requireInteraction: false,
      tag: 'bot-error',
    }
  );
}

/**
 * Send bot status change notification
 */
export async function notifyBotStatus(status: string, message: string): Promise<void> {
  await sendBrowserNotification(
    `Bot ${status}`,
    message,
    {
      requireInteraction: false,
      tag: 'bot-status',
    }
  );
}
