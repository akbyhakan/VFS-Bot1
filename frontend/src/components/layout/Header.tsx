import { useAuth } from '@/hooks/useAuth';
import { useBotStore } from '@/store/botStore';
import { Button } from '@/components/ui/Button';
import { LogOut, Menu, Wifi, WifiOff } from 'lucide-react';
import { cn, getStatusColor } from '@/utils/helpers';

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { logout } = useAuth();
  const { status, isConnected } = useBotStore();

  return (
    <header className="glass border-b border-dark-700 h-16 flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        {/* Mobile menu button */}
        <button
          className="md:hidden text-dark-300 hover:text-dark-100"
          onClick={onMenuClick}
        >
          <Menu className="w-6 h-6" />
        </button>

        {/* Bot Status */}
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              status === 'running' && 'bg-primary-500 animate-pulse',
              status === 'stopped' && 'bg-red-500',
              status === 'idle' && 'bg-yellow-500'
            )}
          />
          <span className={cn('text-sm font-medium', getStatusColor(status))}>
            {status === 'running' && 'Çalışıyor'}
            {status === 'stopped' && 'Durduruldu'}
            {status === 'idle' && 'Beklemede'}
          </span>
        </div>

        {/* WebSocket Status */}
        <div className="flex items-center gap-2 text-xs text-dark-400">
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4 text-primary-500" />
              <span>Bağlı</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-red-500" />
              <span>Bağlantı Yok</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={logout} leftIcon={<LogOut className="w-4 h-4" />}>
          Çıkış
        </Button>
      </div>
    </header>
  );
}
