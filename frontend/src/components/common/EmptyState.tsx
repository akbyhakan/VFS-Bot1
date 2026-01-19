import { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/utils/helpers';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

/**
 * Empty state component for displaying when no data is available
 * Shows an icon, title, optional description and action button
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-12 px-4 text-center',
        className
      )}
    >
      {Icon && (
        <div className="mb-4 p-3 bg-dark-800/50 rounded-full">
          <Icon className="w-12 h-12 text-dark-500" />
        </div>
      )}
      
      <h3 className="text-lg font-semibold text-dark-200 mb-2">{title}</h3>
      
      {description && (
        <p className="text-sm text-dark-400 max-w-md mb-6">{description}</p>
      )}
      
      {action && <div>{action}</div>}
    </div>
  );
}
