import { cn } from '@/utils/helpers';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse bg-dark-700 rounded',
        className
      )}
      aria-hidden="true"
    />
  );
}

export function TableSkeleton({ rows = 5, columns = 6 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Tablo yükleniyor">
      {/* Header skeleton */}
      <div className="flex gap-4 p-4 bg-dark-800 rounded-t-lg">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Row skeletons */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 p-4 border-b border-dark-700">
          {Array.from({ length: columns }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
      <span className="sr-only">Yükleniyor...</span>
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="p-6 bg-dark-800/50 rounded-lg space-y-4" role="status" aria-label="Kart yükleniyor">
      <Skeleton className="h-6 w-1/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <span className="sr-only">Yükleniyor...</span>
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" role="status" aria-label="İstatistikler yükleniyor">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="p-6 bg-dark-800/50 rounded-lg">
          <Skeleton className="h-4 w-24 mb-2" />
          <Skeleton className="h-8 w-16" />
        </div>
      ))}
      <span className="sr-only">Yükleniyor...</span>
    </div>
  );
}
