import { useHealthCheck, useMetrics } from '@/hooks/useApi';
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
} from 'lucide-react';

export function SystemHealth() {
  const { data: health, isLoading: healthLoading } = useHealthCheck();
  const { data: metrics, isLoading: metricsLoading } = useMetrics();

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
        <p className="text-dark-300">Sistem sağlık verileri yüklenemedi</p>
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
        <h1 className="text-3xl font-bold mb-2">Sistem Sağlığı</h1>
        <p className="text-dark-400">Sistem durumu, performans ve bileşen sağlığı</p>
      </div>

      {/* Overall Status */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Genel Durum</h2>
          <span
            className={cn(
              'px-4 py-2 rounded-lg font-medium uppercase text-sm',
              getStatusColor(health.status)
            )}
          >
            {health.status === 'healthy' && 'Sağlıklı'}
            {health.status === 'degraded' && 'Düşük Performans'}
            {health.status === 'unhealthy' && 'Sağlıksız'}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-dark-400 mb-1">Versiyon</p>
            <p className="font-medium">{health.version}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">Çalışma Süresi</p>
            <p className="font-medium">{formatUptime(health.uptime_seconds)}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">Son Kontrol</p>
            <p className="font-medium">
              {new Date(health.timestamp).toLocaleTimeString('tr-TR')}
            </p>
          </div>
        </div>
      </Card>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Başarı Oranı"
          value={`${successRate.toFixed(1)}%`}
          icon={TrendingUp}
          color={successRate >= 90 ? 'primary' : successRate >= 70 ? 'yellow' : 'red'}
        />
        <StatsCard
          title="Ort. Yanıt Süresi"
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
          title="İstek/Dakika"
          value={metrics.requests_per_minute.toFixed(1)}
          icon={Activity}
          color="blue"
        />
        <StatsCard
          title="Devre Kesici Tetikleme"
          value={metrics.circuit_breaker_trips}
          icon={Shield}
          color={metrics.circuit_breaker_trips === 0 ? 'primary' : 'yellow'}
        />
      </div>

      {/* Component Health */}
      <Card>
        <h2 className="text-xl font-semibold mb-4">Bileşen Sağlığı</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Database */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-dark-400" />
                <span className="font-medium">Database</span>
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
                <span className="font-medium">Redis</span>
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
                Backend: {health.components.redis.backend}
              </p>
            )}
          </div>

          {/* Bot */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-dark-400" />
                <span className="font-medium">Bot</span>
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
                Durum: {health.components.bot.running ? 'Çalışıyor' : 'Durduruldu'}
              </p>
              <p>Başarı: {(health.components.bot.success_rate * 100).toFixed(1)}%</p>
            </div>
          </div>

          {/* Circuit Breaker */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-dark-400" />
                <span className="font-medium">Devre Kesici</span>
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
              Tetikleme: {health.components.circuit_breaker.trips}
            </p>
          </div>

          {/* Notifications */}
          <div className="p-4 rounded-lg bg-dark-800 border border-dark-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Bell className="w-5 h-5 text-dark-400" />
                <span className="font-medium">Bildirimler</span>
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
        </div>
      </Card>

      {/* Error Breakdown */}
      {metrics.errors_by_type && Object.keys(metrics.errors_by_type).length > 0 && (
        <Card>
          <h2 className="text-xl font-semibold mb-4">Hata Dağılımı</h2>
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

      {/* System Metrics */}
      <Card>
        <h2 className="text-xl font-semibold mb-4">Sistem Metrikleri</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-dark-400 mb-1">Toplam Kontrol</p>
            <p className="font-medium text-xl">{health.metrics.total_checks.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">Bulunan Slotlar</p>
            <p className="font-medium text-xl">{health.metrics.slots_found.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">Alınan Randevular</p>
            <p className="font-medium text-xl">
              {health.metrics.appointments_booked.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-dark-400 mb-1">Aktif Kullanıcılar</p>
            <p className="font-medium text-xl">{health.metrics.active_users.toLocaleString()}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default SystemHealth;
