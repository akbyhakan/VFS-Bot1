/**
 * Offline banner component
 * Displays a banner when the user is offline
 */

import { useOnlineStatus } from '@/hooks/useOnlineStatus';
import { WifiOff } from 'lucide-react';

export function OfflineBanner() {
  const isOnline = useOnlineStatus();

  if (isOnline) {
    return null;
  }

  return (
    <div
      className="fixed top-0 left-0 right-0 z-50 bg-red-600 text-white px-4 py-2 text-center"
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-center justify-center gap-2">
        <WifiOff className="w-4 h-4" />
        <span className="font-medium">
          Bağlantı yok - İnternet bağlantınızı kontrol edin
        </span>
      </div>
    </div>
  );
}
