import { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/utils/constants';

export interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
  description: string;
  category: string;
}

/**
 * Hook for managing global keyboard shortcuts
 * @param shortcuts - Array of keyboard shortcut configurations
 * @param enabled - Whether shortcuts are enabled (default: true)
 */
export function useKeyboardShortcuts(
  shortcuts: KeyboardShortcut[],
  enabled: boolean = true
) {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // Don't trigger shortcuts when typing in inputs
      const target = event.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Allow Escape key even in inputs
        if (event.key !== 'Escape') {
          return;
        }
      }

      for (const shortcut of shortcuts) {
        const ctrlMatch = shortcut.ctrl ? event.ctrlKey || event.metaKey : !event.ctrlKey && !event.metaKey;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();

        if (ctrlMatch && shiftMatch && altMatch && keyMatch) {
          event.preventDefault();
          shortcut.action();
          break;
        }
      }
    },
    [shortcuts, enabled]
  );

  useEffect(() => {
    if (!enabled) return;

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown, enabled]);
}

/**
 * Hook that provides default application shortcuts
 * @param options - Optional callbacks for custom actions
 */
export function useAppKeyboardShortcuts(options?: {
  onCommandPaletteToggle?: () => void;
  onShortcutsHelp?: () => void;
  onBotToggle?: () => void;
  onModalClose?: () => void;
}) {
  const navigate = useNavigate();

  const shortcuts: KeyboardShortcut[] = [
    {
      key: 'k',
      ctrl: true,
      action: () => options?.onCommandPaletteToggle?.(),
      description: 'Komut paletini aç',
      category: 'Genel',
    },
    {
      key: 'd',
      ctrl: true,
      action: () => navigate(ROUTES.DASHBOARD),
      description: "Dashboard'a git",
      category: 'Navigasyon',
    },
    {
      key: 'u',
      ctrl: true,
      action: () => navigate(ROUTES.USERS),
      description: 'VFS Hesaplar sayfasına git',
      category: 'Navigasyon',
    },
    {
      key: 'l',
      ctrl: true,
      action: () => navigate(ROUTES.LOGS),
      description: 'Loglar sayfasına git',
      category: 'Navigasyon',
    },
    {
      key: ',',
      ctrl: true,
      action: () => navigate(ROUTES.SETTINGS),
      description: 'Ayarlar sayfasına git',
      category: 'Navigasyon',
    },
    {
      key: 's',
      ctrl: true,
      shift: true,
      action: () => options?.onBotToggle?.(),
      description: 'Bot Başlat/Durdur',
      category: 'Bot Kontrol',
    },
    {
      key: 'Escape',
      action: () => options?.onModalClose?.(),
      description: 'Modal/Dialog kapat',
      category: 'Genel',
    },
    {
      key: '?',
      action: () => options?.onShortcutsHelp?.(),
      description: 'Kısayol yardımını göster',
      category: 'Genel',
    },
  ];

  useKeyboardShortcuts(shortcuts);

  return shortcuts;
}
