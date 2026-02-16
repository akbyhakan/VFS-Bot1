import { Card } from '@/components/ui/Card';
import { cn } from '@/utils/helpers';
import { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  color?: 'primary' | 'blue' | 'yellow' | 'red';
}

export function StatsCard({ title, value, icon: Icon, trend, color = 'primary' }: StatsCardProps) {
  return (
    <Card hover className="animate-fade-in relative overflow-hidden group">
      <div className="flex items-center justify-between relative z-10">
        <div className="flex-1">
          <p className="text-sm text-dark-400 mb-1">{title}</p>
          <p className="text-3xl font-bold text-white tracking-tight">{value}</p>
          {trend && (
            <p
              className={cn(
                'text-xs mt-2',
                trend.isPositive ? 'text-primary-400' : 'text-red-400'
              )}
            >
              {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </p>
          )}
        </div>
        <div className={cn(
            "p-3 rounded-xl transition-colors",
            color === 'primary' && "bg-primary-500/10 text-primary-500 group-hover:bg-primary-500 group-hover:text-white",
            color === 'blue' && "bg-blue-500/10 text-blue-500 group-hover:bg-blue-500 group-hover:text-white",
            color === 'yellow' && "bg-yellow-500/10 text-yellow-500 group-hover:bg-yellow-500 group-hover:text-white",
            color === 'red' && "bg-red-500/10 text-red-500 group-hover:bg-red-500 group-hover:text-white",
        )}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
       {/* Decorative background icon */}
      <Icon className={cn(
        "absolute -bottom-4 -right-4 w-24 h-24 opacity-5 rotate-12 transition-transform group-hover:scale-110",
        color === 'primary' && "text-primary-500",
        color === 'blue' && "text-blue-500",
        color === 'yellow' && "text-yellow-500",
        color === 'red' && "text-red-500"
      )} />
    </Card>
  );
}
