import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import { 
  Search, 
  Home, 
  Users, 
  Settings, 
  FileText, 
  Calendar,
  Moon,
  Sun,
  LogOut,
  Play,
  Square,
} from 'lucide-react';
import { ROUTES } from '@/utils/constants';
import { useAuth } from '@/hooks/useAuth';
import { useThemeStore } from '@/store/themeStore';
import { cn } from '@/utils/helpers';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onBotToggle?: () => void;
}

/**
 * Command Palette component for quick navigation and actions
 * Inspired by Spotlight/VSCode command palette
 */
export function CommandPalette({ isOpen, onClose, onBotToggle }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { theme, toggleTheme } = useThemeStore();
  const [search, setSearch] = useState('');

  // Close on Escape
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [onClose]);

  // Reset search when opening
  useEffect(() => {
    if (isOpen) {
      setSearch('');
    }
  }, [isOpen]);

  const handleSelect = useCallback((callback: () => void) => {
    callback();
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-fade-in"
        onClick={onClose}
      />

      {/* Command Palette */}
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-2xl z-50 px-4">
        <Command
          className="glass rounded-lg shadow-2xl animate-slide-in overflow-hidden"
          shouldFilter={true}
        >
          <div className="flex items-center border-b border-dark-700 px-4">
            <Search className="w-5 h-5 text-dark-400 mr-3" />
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder="Komut veya sayfa ara..."
              className="w-full bg-transparent py-4 text-base outline-none placeholder:text-dark-500"
            />
          </div>

          <Command.List className="max-h-[400px] overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-dark-400">
              Sonuç bulunamadı
            </Command.Empty>

            {/* Navigation */}
            <Command.Group heading="Navigasyon" className="text-xs text-dark-500 px-2 pt-2 pb-1 font-semibold">
              <CommandItem
                icon={Home}
                label="Dashboard"
                shortcut="Ctrl+D"
                onSelect={() => handleSelect(() => navigate(ROUTES.DASHBOARD))}
              />
              <CommandItem
                icon={Users}
                label="VFS Hesaplar"
                shortcut="Ctrl+U"
                onSelect={() => handleSelect(() => navigate(ROUTES.USERS))}
              />
              <CommandItem
                icon={FileText}
                label="Loglar"
                shortcut="Ctrl+L"
                onSelect={() => handleSelect(() => navigate(ROUTES.LOGS))}
              />
              <CommandItem
                icon={Calendar}
                label="Randevular"
                onSelect={() => handleSelect(() => navigate(ROUTES.APPOINTMENTS))}
              />
              <CommandItem
                icon={Settings}
                label="Ayarlar"
                shortcut="Ctrl+,"
                onSelect={() => handleSelect(() => navigate(ROUTES.SETTINGS))}
              />
            </Command.Group>

            {/* Actions */}
            <Command.Group heading="Aksiyonlar" className="text-xs text-dark-500 px-2 pt-2 pb-1 font-semibold">
              {onBotToggle && (
                <>
                  <CommandItem
                    icon={Play}
                    label="Bot'u Başlat"
                    onSelect={() => handleSelect(onBotToggle)}
                  />
                  <CommandItem
                    icon={Square}
                    label="Bot'u Durdur"
                    shortcut="Ctrl+Shift+S"
                    onSelect={() => handleSelect(onBotToggle)}
                  />
                </>
              )}
              <CommandItem
                icon={theme === 'dark' ? Sun : Moon}
                label={theme === 'dark' ? 'Açık Tema' : 'Koyu Tema'}
                onSelect={() => handleSelect(toggleTheme)}
              />
              <CommandItem
                icon={LogOut}
                label="Çıkış Yap"
                onSelect={() => handleSelect(logout)}
              />
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </>
  );
}

interface CommandItemProps {
  icon: React.ElementType;
  label: string;
  shortcut?: string;
  onSelect: () => void;
}

function CommandItem({ icon: Icon, label, shortcut, onSelect }: CommandItemProps) {
  return (
    <Command.Item
      onSelect={onSelect}
      className={cn(
        'flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer',
        'text-dark-200 hover:bg-dark-700/50 transition-colors',
        'data-[selected=true]:bg-primary-600/20 data-[selected=true]:text-primary-400'
      )}
    >
      <div className="flex items-center gap-3">
        <Icon className="w-4 h-4" />
        <span className="text-sm">{label}</span>
      </div>
      {shortcut && (
        <kbd className="px-2 py-0.5 text-xs bg-dark-800 text-dark-400 border border-dark-700 rounded">
          {shortcut}
        </kbd>
      )}
    </Command.Item>
  );
}
