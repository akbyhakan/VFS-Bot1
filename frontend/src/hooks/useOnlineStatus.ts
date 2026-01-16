/**
 * Online status monitoring hook
 * Detects when the user goes online/offline and shows notifications
 */

import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      toast.success('Bağlantı yeniden kuruldu', {
        description: 'İnternet bağlantınız geri geldi',
      });
    };

    const handleOffline = () => {
      setIsOnline(false);
      toast.error('Bağlantı kesildi', {
        description: 'İnternet bağlantınız yok',
        duration: Infinity, // Keep showing until back online
      });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}
