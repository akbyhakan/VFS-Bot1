import { StatsCard } from '@/components/dashboard/StatsCard';
import { LiveLogs } from '@/components/dashboard/LiveLogs';
import { BotControls } from '@/components/dashboard/BotControls';
import { HealthBanner } from '@/components/dashboard/HealthBanner';
import { ReadOnlyBanner } from '@/components/dashboard/ReadOnlyBanner';
import { SlotAnalytics } from '@/components/dashboard/SlotAnalytics';
import { useBotStore } from '@/store/botStore';
import { useBotStatus } from '@/hooks/useApi';
import { Target, Calendar, Users as UsersIcon, Clock, RefreshCw } from 'lucide-react';
import { formatNumber, formatRelativeTime } from '@/utils/helpers';
import { Button } from '@/components/ui/Button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

export function Dashboard() {
  const { t } = useTranslation();
  const { data: status, refetch, isRefetching } = useBotStatus();
  const stats = useBotStore((state) => state.stats);
  const lastCheck = useBotStore((state) => state.last_check);

  // Use data from store (updated via WebSocket) or fallback to API data
  const displayStats = status?.stats || stats;
  const displayLastCheck = status?.last_check || lastCheck;

  const handleRefresh = () => {
    refetch();
    toast.success(t('dashboard.refreshData'));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">{t('dashboard.title')}</h1>
          <p className="text-dark-400">{t('dashboard.subtitle')}</p>
        </div>
        <Button
          variant="secondary"
          onClick={handleRefresh}
          disabled={isRefetching}
          leftIcon={<RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />}
        >
          {isRefetching ? t('dashboard.refreshing') : t('dashboard.refresh')}
        </Button>
      </div>

      {/* Health Banner */}
      <HealthBanner />

      {/* Read-Only Mode Banner */}
      <ReadOnlyBanner />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title={t('dashboard.slotsFound')}
          value={formatNumber(displayStats.slots_found)}
          icon={Target}
          color="primary"
        />
        <StatsCard
          title={t('dashboard.appointmentsBooked')}
          value={formatNumber(displayStats.appointments_booked)}
          icon={Calendar}
          color="blue"
        />
        <StatsCard
          title={t('dashboard.activeUsers')}
          value={formatNumber(displayStats.active_users)}
          icon={UsersIcon}
          color="yellow"
        />
        <StatsCard
          title={t('dashboard.lastCheck')}
          value={displayLastCheck ? formatRelativeTime(displayLastCheck) : t('dashboard.never')}
          icon={Clock}
          color="red"
        />
      </div>

      {/* Bot Controls */}
      <BotControls />

      {/* Slot Analytics */}
      <SlotAnalytics />

      {/* Live Logs */}
      <LiveLogs />
    </div>
  );
}

export default Dashboard;
