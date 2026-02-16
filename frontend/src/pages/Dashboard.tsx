import { StatsCard } from '@/components/dashboard/StatsCard';
import { LiveLogs } from '@/components/dashboard/LiveLogs';
import { BotControls } from '@/components/dashboard/BotControls';
import { HealthBanner } from '@/components/dashboard/HealthBanner';
import { useBotStore } from '@/store/botStore';
import { useBotStatus } from '@/hooks/useApi';
import { Target, Calendar, Users as UsersIcon, Clock, RefreshCw } from 'lucide-react';
import { formatNumber, formatRelativeTime } from '@/utils/helpers';
import { Button } from '@/components/ui/Button';
import { toast } from 'sonner';

export function Dashboard() {
  const { data: status, refetch, isRefetching } = useBotStatus();
  const stats = useBotStore((state) => state.stats);
  const lastCheck = useBotStore((state) => state.last_check);

  // Use data from store (updated via WebSocket) or fallback to API data
  const displayStats = status?.stats || stats;
  const displayLastCheck = status?.last_check || lastCheck;

  const handleRefresh = () => {
    refetch();
    toast.success('Veriler yenileniyor...');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">Kontrol Paneli</h1>
          <p className="text-dark-400">Bot performansını ve istatistikleri görüntüleyin</p>
        </div>
        <Button
          variant="secondary"
          onClick={handleRefresh}
          disabled={isRefetching}
          leftIcon={<RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />}
        >
          {isRefetching ? 'Yenileniyor...' : 'Yenile'}
        </Button>
      </div>

      {/* Health Banner */}
      <HealthBanner />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Bulunan Slotlar"
          value={formatNumber(displayStats.slots_found)}
          icon={Target}
          color="primary"
        />
        <StatsCard
          title="Alınan Randevular"
          value={formatNumber(displayStats.appointments_booked)}
          icon={Calendar}
          color="blue"
        />
        <StatsCard
          title="Aktif Kullanıcılar"
          value={formatNumber(displayStats.active_users)}
          icon={UsersIcon}
          color="yellow"
        />
        <StatsCard
          title="Son Kontrol"
          value={displayLastCheck ? formatRelativeTime(displayLastCheck) : 'Hiç'}
          icon={Clock}
          color="red"
        />
      </div>

      {/* Bot Controls */}
      <BotControls />

      {/* Live Logs */}
      <LiveLogs />
    </div>
  );
}

export default Dashboard;
