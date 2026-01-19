import { Modal } from '@/components/ui/Modal';
import { Keyboard } from 'lucide-react';
import type { KeyboardShortcut } from '@/hooks/useKeyboardShortcuts';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
  shortcuts: KeyboardShortcut[];
}

/**
 * Format shortcut keys for display
 */
function formatShortcut(shortcut: KeyboardShortcut): string {
  const keys: string[] = [];

  if (shortcut.ctrl) keys.push('Ctrl');
  if (shortcut.shift) keys.push('Shift');
  if (shortcut.alt) keys.push('Alt');

  // Format special keys
  const keyMap: Record<string, string> = {
    Escape: 'Esc',
    ',': ',',
    '?': '?',
  };

  const displayKey = keyMap[shortcut.key] || shortcut.key.toUpperCase();
  keys.push(displayKey);

  return keys.join(' + ');
}

export function ShortcutsModal({ isOpen, onClose, shortcuts }: ShortcutsModalProps) {
  // Group shortcuts by category
  const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = [];
    }
    acc[shortcut.category].push(shortcut);
    return acc;
  }, {} as Record<string, KeyboardShortcut[]>);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Klavye Kısayolları"
      description="Uygulamayı daha hızlı kullanmak için klavye kısayolları"
      size="lg"
    >
      <div className="space-y-6">
        {Object.entries(groupedShortcuts).map(([category, categoryShortcuts]) => (
          <div key={category}>
            <h3 className="text-sm font-semibold text-dark-300 mb-3 flex items-center gap-2">
              <Keyboard className="w-4 h-4" />
              {category}
            </h3>
            <div className="space-y-2">
              {categoryShortcuts.map((shortcut, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between py-2 px-3 bg-dark-800/50 rounded-lg hover:bg-dark-700/50 transition-colors"
                >
                  <span className="text-sm text-dark-200">{shortcut.description}</span>
                  <kbd className="px-3 py-1.5 text-xs font-mono bg-dark-700 text-dark-100 border border-dark-600 rounded shadow-sm">
                    {formatShortcut(shortcut)}
                  </kbd>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 pt-4 border-t border-dark-700">
        <p className="text-xs text-dark-400 text-center">
          💡 İpucu: <kbd className="px-2 py-1 text-xs bg-dark-700 rounded">?</kbd> tuşuna
          basarak bu yardımı tekrar açabilirsiniz
        </p>
      </div>
    </Modal>
  );
}
