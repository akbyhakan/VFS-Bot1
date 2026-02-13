import { NavLink } from 'react-router-dom';
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
} from 'lucide-react';
import { ROUTES } from '@/utils/constants';

const navigation = [
  { name: 'Dashboard', href: ROUTES.DASHBOARD, icon: LayoutDashboard },
  { name: 'Kullanıcılar', href: ROUTES.USERS, icon: Users },
  { name: 'Randevu Talebi', href: ROUTES.APPOINTMENTS, icon: Calendar },
  { name: 'Denetim Logları', href: ROUTES.AUDIT_LOGS, icon: Shield },
  { name: 'Loglar', href: ROUTES.LOGS, icon: FileText },
  { name: 'Ayarlar', href: ROUTES.SETTINGS, icon: Settings },
  { name: 'Sistem Sağlığı', href: ROUTES.SYSTEM_HEALTH, icon: HeartPulse },
];

export function Sidebar() {
  return (
    <aside className="hidden md:flex md:flex-col md:w-64 glass border-r border-dark-700">
      <div className="flex-1 flex flex-col min-h-0">
        {/* Logo */}
        <div className="flex items-center h-16 flex-shrink-0 px-6 border-b border-dark-700">
          <Activity className="w-8 h-8 text-primary-500" />
          <span className="ml-3 text-xl font-bold text-gradient">VFS-Bot</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
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
              {item.name}
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
