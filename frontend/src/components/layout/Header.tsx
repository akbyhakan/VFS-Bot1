import { useAuth } from '@/hooks/useAuth';
import { useBotStore } from '@/store/botStore';
import { useThemeStore } from '@/store/themeStore';
import { Button } from '@/components/ui/Button';
import { LogOut, Menu, Wifi, WifiOff, Sun, Moon, Bell, Globe } from 'lucide-react';
import { cn, getStatusColor } from '@/utils/helpers';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { logout } = useAuth();
  const { status, isConnected } = useBotStore();
  const { theme, toggleTheme } = useThemeStore();
  const { i18n } = useTranslation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleMenuClick = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
    onMenuClick?.();
  };

  const toggleLanguage = () => {
    const newLang = i18n.language === 'tr' ? 'en' : 'tr';
    i18n.changeLanguage(newLang);
  };

  return (
    <header className="glass border-b border-dark-700 h-16 flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        {/* Mobile menu button */}
        <button
          className="md:hidden text-dark-300 hover:text-dark-100 p-2 rounded focus:outline-none focus:ring-2 focus:ring-primary-500"
          onClick={handleMenuClick}
          aria-label="Menüyü aç"
          aria-expanded={isMobileMenuOpen}
        >
          <Menu className="w-6 h-6" aria-hidden="true" />
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
        {/* Notification Icon */}
        <button
          className="p-2 text-dark-300 hover:text-dark-100 rounded hover:bg-dark-700 transition-colors relative"
          aria-label="Bildirimler"
          title="Bildirimler"
        >
          <Bell className="w-5 h-5" />
          {/* Notification badge - can be conditionally shown */}
          {/* <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span> */}
        </button>

        {/* Language Selector */}
        <button
          onClick={toggleLanguage}
          className="p-2 text-dark-300 hover:text-dark-100 rounded hover:bg-dark-700 transition-colors flex items-center gap-1"
          aria-label="Dil değiştir"
          title="Dil değiştir"
        >
          <Globe className="w-5 h-5" />
          <span className="text-sm font-medium uppercase">{i18n.language}</span>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 text-dark-300 hover:text-dark-100 rounded hover:bg-dark-700 transition-colors"
          aria-label={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
          title={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        <Button variant="ghost" size="sm" onClick={logout} leftIcon={<LogOut className="w-4 h-4" />}>
          Çıkış
        </Button>
      </div>
    </header>
  );
}
