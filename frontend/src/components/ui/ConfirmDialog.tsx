import { useEffect, useRef } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
import { AlertTriangle, Trash2, Info } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
  isLoading?: boolean;
}

const variantConfig = {
  danger: {
    icon: Trash2,
    iconColor: 'text-red-500',
    buttonVariant: 'danger' as const,
  },
  warning: {
    icon: AlertTriangle,
    iconColor: 'text-yellow-500',
    buttonVariant: 'primary' as const,
  },
  info: {
    icon: Info,
    iconColor: 'text-blue-500',
    buttonVariant: 'primary' as const,
  },
};

export function ConfirmDialog({
  isOpen,
  onConfirm,
  onCancel,
  title,
  message,
  confirmText = 'Onayla',
  cancelText = 'İptal',
  variant = 'danger',
  isLoading = false,
}: ConfirmDialogProps) {
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const config = variantConfig[variant];
  const Icon = config.icon;

  // Focus confirm button when dialog opens
  useEffect(() => {
    if (isOpen && confirmButtonRef.current) {
      confirmButtonRef.current.focus();
    }
  }, [isOpen]);

  // Handle escape key (only if this is the active modal)
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        // Check if this dialog is in focus (topmost modal)
        const dialogElement = document.querySelector('[role="alertdialog"]');
        if (dialogElement && document.activeElement && 
            (dialogElement === document.activeElement || dialogElement.contains(document.activeElement))) {
          onCancel();
        }
      }
    };
    
    if (isOpen) {
      window.addEventListener('keydown', handleEscape);
      return () => window.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onCancel]);

  return (
    <Modal isOpen={isOpen} onClose={onCancel} title={title} size="sm">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
      >
        <div className="flex items-start gap-4 mb-6">
          <div className={`p-2 rounded-full bg-dark-700 ${config.iconColor}`}>
            <Icon className="w-6 h-6" aria-hidden="true" />
          </div>
          <div>
            <h3 id="confirm-dialog-title" className="text-lg font-semibold mb-2">
              {title}
            </h3>
            <p id="confirm-dialog-description" className="text-dark-400">
              {message}
            </p>
          </div>
        </div>

        <div className="flex gap-3 justify-end">
          <Button
            variant="secondary"
            onClick={onCancel}
            disabled={isLoading}
          >
            {cancelText}
          </Button>
          <Button
            ref={confirmButtonRef}
            variant={config.buttonVariant}
            onClick={onConfirm}
            isLoading={isLoading}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
