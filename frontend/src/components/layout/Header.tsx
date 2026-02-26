import { useAuth } from '@/hooks/useAuth';
import { useBotStore } from '@/store/botStore';
import { useThemeStore } from '@/store/themeStore';
import { useNotificationStore } from '@/store/notificationStore';
import { useHealthCheck } from '@/hooks/useApi';
import { Button } from '@/components/ui/Button';
import { NotificationPanel } from './NotificationPanel';
import { LogOut, Menu, Wifi, WifiOff, Sun, Moon, Bell, Globe } from 'lucide-react';
import { cn, getStatusColor } from '@/utils/helpers';
import { useTranslation } from 'react-i18next';
import { useRef } from 'react';
import { BOT_STATUS } from '@/utils/constants';
import type { BotStatusType } from '@/types/api';

const KNOWN_STATUSES = Object.values(BOT_STATUS) as BotStatusType[];

interface HeaderProps {
  onMenuClick?: () => void;
  isSidebarOpen?: boolean;
}

export function Header({ onMenuClick, isSidebarOpen = false }: HeaderProps) {
  const { logout } = useAuth();
  const { status, isConnected } = useBotStore();
  const { data: health } = useHealthCheck();
  const { theme, toggleTheme } = useThemeStore();
  const { t, i18n } = useTranslation();
  const { unreadCount, togglePanel } = useNotificationStore();
  const bellButtonRef = useRef<HTMLButtonElement>(null);

  const handleMenuClick = () => {
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
          aria-label={t('header.openMenu')}
          aria-expanded={isSidebarOpen}
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
              status === 'idle' && 'bg-yellow-500',
              status === 'error' && 'bg-red-600',
              status === 'starting' && 'bg-blue-500 animate-pulse',
              status === 'restarting' && 'bg-yellow-500 animate-pulse',
              status === 'not_configured' && 'bg-dark-500',
              status === 'rate_limited' && 'bg-orange-500 animate-pulse',
              !KNOWN_STATUSES.includes(status) && 'bg-dark-400'
            )}
          />
          <span className={cn('text-sm font-medium', getStatusColor(status))}>
            {status === 'running' && t('header.statusRunning')}
            {status === 'stopped' && t('header.statusStopped')}
            {status === 'idle' && t('header.statusIdle')}
            {status === 'error' && t('header.statusError')}
            {status === 'starting' && t('header.statusStarting')}
            {status === 'restarting' && t('header.statusRestarting')}
            {status === 'not_configured' && t('header.statusNotConfigured')}
            {status === 'rate_limited' && t('header.statusRateLimited')}
            {!KNOWN_STATUSES.includes(status) && status}
          </span>
          
          {/* System Health Indicator */}
          {health && health.status !== 'healthy' && (
            <div
              className={cn(
                'ml-2 w-2 h-2 rounded-full',
                health.status === 'degraded' && 'bg-yellow-500 animate-pulse',
                health.status === 'unhealthy' && 'bg-red-500 animate-pulse'
              )}
              title={`System: ${health.status}`}
              aria-label={`System health: ${health.status}`}
            />
          )}
        </div>

        {/* WebSocket Status */}
        <div className="flex items-center gap-2 text-xs text-dark-400">
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4 text-primary-500" />
              <span>{t('header.connected')}</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-red-500" />
              <span>{t('header.disconnected')}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Notification Icon */}
        <div className="relative">
          <button
            ref={bellButtonRef}
            onClick={togglePanel}
            className="p-2 text-dark-300 hover:text-dark-100 rounded hover:bg-dark-700 transition-colors relative"
            aria-label={t('header.notifications')}
            title={t('header.notifications')}
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <>
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" aria-hidden="true" />
                <span className="sr-only">{t('header.unreadNotifications', { count: unreadCount })}</span>
              </>
            )}
          </button>
          <NotificationPanel bellButtonRef={bellButtonRef} />
        </div>

        {/* Language Selector */}
        <button
          onClick={toggleLanguage}
          className="p-2 text-dark-300 hover:text-dark-100 rounded hover:bg-dark-700 transition-colors flex items-center gap-1"
          aria-label={t('header.changeLanguage')}
          title={t('header.changeLanguage')}
        >
          <Globe className="w-5 h-5" />
          <span className="text-sm font-medium uppercase">{i18n.language}</span>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 text-dark-300 hover:text-dark-100 rounded hover:bg-dark-700 transition-colors"
          aria-label={theme === 'dark' ? t('header.switchToLight') : t('header.switchToDark')}
          title={theme === 'dark' ? t('header.switchToLight') : t('header.switchToDark')}
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        <Button variant="ghost" size="sm" onClick={logout} leftIcon={<LogOut className="w-4 h-4" />}>
          {t('auth.logout')}
        </Button>
      </div>
    </header>
  );
}
