import { useState } from 'react';
import { AlertTriangle, XCircle, X, ChevronDown, ChevronUp } from 'lucide-react';
import { useHealthCheck } from '@/hooks/useApi';
import { Card } from '@/components/ui/Card';
import { cn } from '@/utils/helpers';

export function HealthBanner() {
  const { data: health } = useHealthCheck();
  const [isDismissed, setIsDismissed] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't show banner if healthy, loading, or dismissed
  if (!health || health.status === 'healthy' || isDismissed) {
    return null;
  }

  const isDegraded = health.status === 'degraded';
  const isUnhealthy = health.status === 'unhealthy';

  // Get components with issues
  const componentIssues = Object.entries(health.components)
    .filter(([_, component]) => component.status !== 'healthy')
    .map(([name, component]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1).replace('_', ' '),
      status: component.status,
    }));

  return (
    <Card
      className={cn(
        'animate-fade-in mb-6 border-2',
        isDegraded && 'border-yellow-500/50 bg-yellow-500/5',
        isUnhealthy && 'border-red-500/50 bg-red-500/5'
      )}
      role="alert"
      aria-live="polite"
      aria-label={`System health is ${health.status}`}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className={cn(
            'p-2 rounded-lg flex-shrink-0',
            isDegraded && 'bg-yellow-500/10',
            isUnhealthy && 'bg-red-500/10'
          )}
        >
          {isDegraded && <AlertTriangle className="w-6 h-6 text-yellow-500" />}
          {isUnhealthy && <XCircle className="w-6 h-6 text-red-500" />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-4 mb-2">
            <h3
              className={cn(
                'text-lg font-semibold',
                isDegraded && 'text-yellow-400',
                isUnhealthy && 'text-red-400'
              )}
            >
              {isDegraded && 'System Performance Degraded'}
              {isUnhealthy && 'System Unhealthy'}
            </h3>

            <button
              onClick={() => setIsDismissed(true)}
              className="p-1 hover:bg-dark-700 rounded transition-colors"
              aria-label="Dismiss health warning"
            >
              <X className="w-5 h-5 text-dark-400 hover:text-dark-100" />
            </button>
          </div>

          <p className="text-dark-300 text-sm mb-3">
            {isDegraded &&
              'Some system components are experiencing issues. Functionality may be limited.'}
            {isUnhealthy &&
              'Critical system components are down. Service is severely impacted.'}
          </p>

          {/* Component Details Toggle */}
          {componentIssues.length > 0 && (
            <>
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 text-sm text-dark-400 hover:text-dark-100 transition-colors"
                aria-expanded={isExpanded}
                aria-controls="component-details"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    Hide component details
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    Show affected components ({componentIssues.length})
                  </>
                )}
              </button>

              {isExpanded && (
                <div
                  id="component-details"
                  className="mt-3 space-y-2 pl-2 border-l-2 border-dark-700"
                >
                  {componentIssues.map((issue) => (
                    <div
                      key={issue.name}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="text-dark-300">{issue.name}</span>
                      <span
                        className={cn(
                          'px-2 py-1 rounded text-xs font-medium',
                          issue.status === 'degraded' &&
                            'bg-yellow-500/10 text-yellow-400',
                          issue.status === 'unhealthy' && 'bg-red-500/10 text-red-400'
                        )}
                      >
                        {issue.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Card>
  );
}
