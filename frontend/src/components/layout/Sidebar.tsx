import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '@/utils/helpers';
import {
  LayoutDashboard,
  Users,
  Settings,
  FileText,
  Activity,
  Calendar,
  HeartPulse,
  Shield,
  X,
} from 'lucide-react';
import { ROUTES } from '@/utils/constants';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const prevPathnameRef = useRef(location.pathname);

  const navigation = [
    { href: ROUTES.DASHBOARD, icon: LayoutDashboard, nameKey: 'sidebar.dashboard' },
    { href: ROUTES.USERS, icon: Users, nameKey: 'sidebar.users' },
    { href: ROUTES.APPOINTMENTS, icon: Calendar, nameKey: 'sidebar.appointments' },
    { href: ROUTES.AUDIT_LOGS, icon: Shield, nameKey: 'sidebar.auditLogs' },
    { href: ROUTES.LOGS, icon: FileText, nameKey: 'sidebar.logs' },
    { href: ROUTES.SETTINGS, icon: Settings, nameKey: 'sidebar.settings' },
    { href: ROUTES.SYSTEM_HEALTH, icon: HeartPulse, nameKey: 'sidebar.systemHealth' },
  ];
  
  // Close sidebar on route change (mobile)
  useEffect(() => {
    if (location.pathname !== prevPathnameRef.current) {
      prevPathnameRef.current = location.pathname;
      if (isOpen && onClose) {
        onClose();
      }
    }
  }, [location.pathname, isOpen, onClose]);
  
  return (
    <aside className={cn(
      'fixed inset-y-0 left-0 z-40 w-64 glass border-r border-dark-700 transform transition-transform duration-300 ease-in-out',
      'md:relative md:translate-x-0',
      isOpen ? 'translate-x-0' : '-translate-x-full'
    )}>
      <div className="flex-1 flex flex-col min-h-0">
        {/* Logo & Close Button */}
        <div className="flex items-center justify-between h-16 flex-shrink-0 px-6 border-b border-dark-700">
          <div className="flex items-center">
            <Activity className="w-8 h-8 text-primary-500" />
            <span className="ml-3 text-xl font-bold text-gradient">VFS-Bot</span>
          </div>
          {/* Close button for mobile */}
          <button
            onClick={onClose}
            className="md:hidden text-dark-300 hover:text-dark-100 p-2 rounded focus:outline-none focus:ring-2 focus:ring-primary-500"
            aria-label={t('sidebar.closeMenu')}
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navigation.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all',
                  isActive
                    ? 'bg-primary-500/10 text-primary-400 shadow-glow-sm'
                    : 'text-dark-300 hover:bg-dark-800 hover:text-dark-100'
                )
              }
            >
              <item.icon className="w-5 h-5 mr-3" />
              {t(item.nameKey)}
            </NavLink>
          ))}
        </nav>

        {/* Version */}
        <div className="flex-shrink-0 p-4 border-t border-dark-700">
          <p className="text-xs text-dark-500 text-center">v2.0.0</p>
        </div>
      </div>
    </aside>
  );
}
