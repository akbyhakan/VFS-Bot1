import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Loading } from '@/components/common/Loading';
import { RefreshCw, CheckCircle, XCircle, Clock, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import {
  useDropdownSyncStatuses,
  useTriggerCountrySync,
  useTriggerAllSync,
} from '@/hooks/useDropdownSync';
import type { DropdownSyncStatus } from '@/hooks/useDropdownSync';

// Country names mapping (English names for display)
const COUNTRY_NAMES: Record<string, string> = {
  fra: '🇫🇷 France',
  nld: '🇳🇱 Netherlands',
  aut: '🇦🇹 Austria',
  bel: '🇧🇪 Belgium',
  cze: '🇨🇿 Czech Republic',
  pol: '🇵🇱 Poland',
  swe: '🇸🇪 Sweden',
  che: '🇨🇭 Switzerland',
  fin: '🇫🇮 Finland',
  est: '🇪🇪 Estonia',
  lva: '🇱🇻 Latvia',
  ltu: '🇱🇹 Lithuania',
  lux: '🇱🇺 Luxembourg',
  mlt: '🇲🇹 Malta',
  nor: '🇳🇴 Norway',
  dnk: '🇩🇰 Denmark',
  isl: '🇮🇸 Iceland',
  svn: '🇸🇮 Slovenia',
  hrv: '🇭🇷 Croatia',
  bgr: '🇧🇬 Bulgaria',
  svk: '🇸🇰 Slovakia',
};

/**
 * Format timestamp to relative time (e.g., "2 hours ago")
 */
function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return 'Never';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  
  if (diffSeconds < 60) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

/**
 * Get status icon and color
 */
function getStatusDisplay(status: DropdownSyncStatus['sync_status']) {
  switch (status) {
    case 'completed':
      return {
        icon: <CheckCircle className="h-5 w-5 text-green-500" />,
        text: 'Completed',
        color: 'text-green-500',
      };
    case 'syncing':
      return {
        icon: <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />,
        text: 'Syncing...',
        color: 'text-blue-500',
      };
    case 'failed':
      return {
        icon: <XCircle className="h-5 w-5 text-red-500" />,
        text: 'Failed',
        color: 'text-red-500',
      };
    case 'pending':
    default:
      return {
        icon: <Clock className="h-5 w-5 text-yellow-500" />,
        text: 'Pending',
        color: 'text-yellow-500',
      };
  }
}

export default function DropdownManagement() {
  const { t } = useTranslation();
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  
  const { data: statuses, isLoading } = useDropdownSyncStatuses();
  const triggerCountrySync = useTriggerCountrySync();
  const triggerAllSync = useTriggerAllSync();

  const handleSyncCountry = async (countryCode: string) => {
    try {
      await triggerCountrySync.mutateAsync(countryCode);
      toast.success(t('dropdownManagement.syncTriggered', `Sync triggered for ${COUNTRY_NAMES[countryCode] || countryCode}`));
    } catch (error) {
      toast.error(t('dropdownManagement.syncFailed', 'Failed to trigger sync'));
    }
  };

  const handleSyncAll = async () => {
    try {
      await triggerAllSync.mutateAsync();
      toast.success(t('dropdownManagement.syncAllTriggered', 'Sync triggered for all countries'));
    } catch (error) {
      toast.error(t('dropdownManagement.syncAllFailed', 'Failed to trigger sync for all countries'));
    }
  };

  if (isLoading) return <Loading />;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              {t('dropdownManagement.title', 'VFS Dropdown Management')}
            </CardTitle>
            <Button
              onClick={handleSyncAll}
              disabled={triggerAllSync.isPending}
              className="flex items-center gap-2"
            >
              {triggerAllSync.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t('dropdownManagement.syncing', 'Syncing...')}
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4" />
                  {t('dropdownManagement.syncAll', 'Sync All Countries')}
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Info Banner */}
            <div className="bg-blue-900/20 border border-blue-700 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-blue-400 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-blue-100">
                    {t('dropdownManagement.autoSchedule', 'Automatic Update: Every Saturday at 03:00 (Turkey Time)')}
                  </p>
                  <p className="text-xs text-blue-300 mt-1">
                    {t(
                      'dropdownManagement.autoScheduleDesc',
                      'Dropdown data is automatically synchronized weekly to ensure up-to-date information from VFS website.'
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* Countries Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-600">
                    <th className="text-left py-3 px-4 text-sm font-medium text-dark-300">
                      {t('dropdownManagement.country', 'Country')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-dark-300">
                      {t('dropdownManagement.status', 'Status')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-dark-300">
                      {t('dropdownManagement.lastSynced', 'Last Synced')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-dark-300">
                      {t('dropdownManagement.action', 'Action')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {statuses?.map((status) => {
                    const display = getStatusDisplay(status.sync_status);
                    const isSyncing = status.sync_status === 'syncing';
                    
                    return (
                      <tr
                        key={status.country_code}
                        className="border-b border-dark-700 hover:bg-dark-800/50 transition-colors"
                      >
                        <td className="py-3 px-4">
                          <span className="text-sm font-medium">
                            {COUNTRY_NAMES[status.country_code] || status.country_code.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            {display.icon}
                            <span className={`text-sm ${display.color}`}>
                              {display.text}
                            </span>
                          </div>
                          {status.error_message && (
                            <p className="text-xs text-red-400 mt-1" title={status.error_message}>
                              {status.error_message.length > 50
                                ? `${status.error_message.substring(0, 50)}...`
                                : status.error_message}
                            </p>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-sm text-dark-300">
                            {formatRelativeTime(status.last_synced_at)}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleSyncCountry(status.country_code)}
                            disabled={isSyncing || triggerCountrySync.isPending}
                            className="flex items-center gap-2"
                          >
                            {isSyncing ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <RefreshCw className="h-3 w-3" />
                            )}
                            {t('dropdownManagement.sync', 'Sync')}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Empty state */}
            {!statuses || statuses.length === 0 && (
              <div className="text-center py-12">
                <Clock className="h-12 w-12 text-dark-500 mx-auto mb-3" />
                <p className="text-dark-400">
                  {t('dropdownManagement.noData', 'No dropdown data available. Click "Sync All Countries" to get started.')}
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
