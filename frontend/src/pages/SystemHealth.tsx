import { useTranslation } from 'react-i18next';
import { useHealthCheck, useMetrics } from '@/hooks/useApi';
import { useBotErrors, useSelectorHealth, getErrorScreenshotUrl, getErrorHtmlSnapshotUrl } from '@/hooks/useBotErrors';
import { Card } from '@/components/ui/Card';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { cn } from '@/utils/helpers';
import {
  Activity,
  Database,
  Server,
  Zap,
  Bell,
  Shield,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  TrendingUp,
  AlertCircle,
  Bug,
  Camera,
  FileCode,
  Search,
} from 'lucide-react';

export function SystemHealth() {
  const { t } = useTranslation();
  const { data: health, isLoading: healthLoading } = useHealthCheck();
  const { data: metrics, isLoading: metricsLoading } = useMetrics();
  const { data: botErrors } = useBotErrors(10);
  const { data: selectorHealth } = useSelectorHealth();

  if (healthLoading || metricsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500"></div>
      </div>
    );
  }

  if (!health || !metrics) {
    return (
      <Card className="p-8 text-center">
        <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
        <p className="text-dark-300">{t('systemHealth.dataLoadFailed')}</p>
      </Card>
    );
  }

  const getStatusIcon = (status: string) => {
    if (status === 'healthy') return <CheckCircle className="w-5 h-5 text-primary-500" />;
    if (status === 'degraded') return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
    return <XCircle className="w-5 h-5 text-red-500" />;
  };

  const getStatusColor = (status: string) => {
    if (status === 'healthy') return 'text-primary-500 bg-primary-500/10';
    if (status === 'degraded') return 'text-yellow-500 bg-yellow-500/10';
    return 'text-red-500 bg-red-500/10';
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}g ${hours}s`;
    if (hours > 0) return `${hours}s ${minutes}d`;
    return `${minutes}d`;
  };

  const successRate = health.components.bot.success_rate * 100;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">{t('systemHealth.title')}</h1>
        <p className="text-dark-400">{t('systemHealth.subtitle')}</p>
      </div>

      {/* Overall Status */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{t('systemHealth.overallStatus')}</h2>
          <span
            className={cn(
              'px-4 py-2 rounded-lg font-medium uppercase text-sm',
              getStatusColor(health.status)
            )}
          >
            {health.status === 'healthy' && t('systemHealth.healthy')}
            {health.status === 'degraded' && t('systemHealth.degraded')}
            {health.status === 'unhealthy' && t('systemHealth.unhealthy')}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.version')}</p>
            <p className="font-medium">{health.version}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.uptime')}</p>
            <p className="font-medium">{formatUptime(health.uptime_seconds)}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.lastCheck')}</p>
            <p className="font-medium">
              {new Date(health.timestamp).toLocaleTimeString('tr-TR')}
            </p>
          </div>
        </div>
      </Card>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title={t('systemHealth.successRate')}
          value={`${successRate.toFixed(1)}%`}
          icon={TrendingUp}
          color={successRate >= 90 ? 'primary' : successRate >= 70 ? 'yellow' : 'red'}
        />
        <StatsCard
          title={t('systemHealth.avgResponseTime')}
          value={`${metrics.avg_response_time_ms.toFixed(0)}ms`}
          icon={Clock}
          color={
            metrics.avg_response_time_ms < 500
              ? 'primary'
              : metrics.avg_response_time_ms < 1000
                ? 'yellow'
                : 'red'
          }
        />
        <StatsCard
          title={t('systemHealth.requestsPerMinute')}
          value={metrics.requests_per_minute.toFixed(1)}
          icon={Activity}
          color="blue"
        />
        <StatsCard
          title={t('systemHealth.circuitBreakerTrips')}
          value={metrics.circuit_breaker_trips}
          icon={Shield}
          color={metrics.circuit_breaker_trips === 0 ? 'primary' : 'yellow'}
        />
      </div>

      {/* Component Health */}
      <Card>
        <h2 className="text-xl font-semibold mb-4">{t('systemHealth.componentHealth')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Database */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-dark-400" />
                <span className="font-medium">{t('systemHealth.database')}</span>
              </div>
              {getStatusIcon(health.components.database.status)}
            </div>
            <span
              className={cn(
                'text-xs px-2 py-1 rounded',
                getStatusColor(health.components.database.status)
              )}
            >
              {health.components.database.status}
            </span>
          </div>

          {/* Redis */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Server className="w-5 h-5 text-dark-400" />
                <span className="font-medium">{t('systemHealth.redis')}</span>
              </div>
              {getStatusIcon(health.components.redis.status)}
            </div>
            <span
              className={cn(
                'text-xs px-2 py-1 rounded',
                getStatusColor(health.components.redis.status)
              )}
            >
              {health.components.redis.status}
            </span>
            {health.components.redis.backend && (
              <p className="text-xs text-dark-400 mt-2">
                {t('systemHealth.backend')}: {health.components.redis.backend}
              </p>
            )}
          </div>

          {/* Bot */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-dark-400" />
                <span className="font-medium">{t('systemHealth.bot')}</span>
              </div>
              {getStatusIcon(health.components.bot.status)}
            </div>
            <span
              className={cn(
                'text-xs px-2 py-1 rounded',
                getStatusColor(health.components.bot.status)
              )}
            >
              {health.components.bot.status}
            </span>
            <div className="mt-2 space-y-1 text-xs text-dark-400">
              <p>
                {t('systemHealth.status')}: {health.components.bot.running ? t('systemHealth.running') : t('systemHealth.stopped')}
              </p>
              <p>{t('systemHealth.success')}: {(health.components.bot.success_rate * 100).toFixed(1)}%</p>
            </div>
          </div>

          {/* Circuit Breaker */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-dark-400" />
                <span className="font-medium">{t('systemHealth.circuitBreaker')}</span>
              </div>
              {getStatusIcon(health.components.circuit_breaker.status)}
            </div>
            <span
              className={cn(
                'text-xs px-2 py-1 rounded',
                getStatusColor(health.components.circuit_breaker.status)
              )}
            >
              {health.components.circuit_breaker.status}
            </span>
            <p className="text-xs text-dark-400 mt-2">
              {t('systemHealth.trips')}: {health.components.circuit_breaker.trips}
            </p>
          </div>

          {/* Notifications */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Bell className="w-5 h-5 text-dark-400" />
                <span className="font-medium">{t('systemHealth.notifications')}</span>
              </div>
              {getStatusIcon(health.components.notifications.status)}
            </div>
            <span
              className={cn(
                'text-xs px-2 py-1 rounded',
                getStatusColor(health.components.notifications.status)
              )}
            >
              {health.components.notifications.status}
            </span>
          </div>

          {/* Selector Health */}
          {selectorHealth && (
            <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Search className="w-5 h-5 text-dark-400" />
                  <span className="font-medium">{t('systemHealth.selectorHealth')}</span>
                </div>
                {getStatusIcon(selectorHealth.status)}
              </div>
              <span
                className={cn(
                  'text-xs px-2 py-1 rounded',
                  getStatusColor(selectorHealth.status)
                )}
              >
                {selectorHealth.status}
              </span>
              {selectorHealth.message && (
                <p className="text-xs text-dark-400 mt-2">{selectorHealth.message}</p>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Error Breakdown */}
      {metrics.errors_by_type && Object.keys(metrics.errors_by_type).length > 0 && (
        <Card>
          <h2 className="text-xl font-semibold mb-4">{t('systemHealth.errorBreakdown')}</h2>
          <div className="space-y-2">
            {Object.entries(metrics.errors_by_type).map(([type, count]) => (
              <div
                key={type}
                className="flex items-center justify-between p-3 rounded-lg bg-dark-800"
              >
                <span className="text-dark-300">{type}</span>
                <span className="font-medium text-red-400">{count}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent Bot Errors */}
      {botErrors && botErrors.length > 0 && (
        <Card>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Bug className="w-5 h-5 text-red-400" />
            {t('systemHealth.recentBotErrors')}
          </h2>
          <div className="space-y-3">
            {botErrors.map((error) => (
              <div key={error.id} className="p-3 rounded-lg bg-dark-800 border border-dark-700">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-red-400">{error.error_type}</span>
                  <span className="text-xs text-dark-400">
                    {new Date(error.timestamp).toLocaleString('tr-TR')}
                  </span>
                </div>
                <p className="text-sm text-dark-300 mb-2">{error.error_message}</p>
                <div className="flex gap-3 text-xs">
                  {error.captures?.full_screenshot && (
                    <a
                      href={getErrorScreenshotUrl(error.id, 'full')}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-primary-400 hover:text-primary-300"
                    >
                      <Camera className="w-3 h-3" />
                      {t('systemHealth.screenshot')}
                    </a>
                  )}
                  {error.captures?.html_snapshot && (
                    <a
                      href={getErrorHtmlSnapshotUrl(error.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-primary-400 hover:text-primary-300"
                    >
                      <FileCode className="w-3 h-3" />
                      {t('systemHealth.htmlSnapshot')}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* System Metrics */}
      <Card>
        <h2 className="text-xl font-semibold mb-4">{t('systemHealth.systemMetrics')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.totalChecks')}</p>
            <p className="font-medium text-xl">{health.metrics.total_checks.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.slotsFound')}</p>
            <p className="font-medium text-xl">{health.metrics.slots_found.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.appointmentsBooked')}</p>
            <p className="font-medium text-xl">
              {health.metrics.appointments_booked.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">{t('systemHealth.activeUsers')}</p>
            <p className="font-medium text-xl">{health.metrics.active_users.toLocaleString()}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default SystemHealth;
