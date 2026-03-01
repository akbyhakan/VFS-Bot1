import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { useSlotAnalytics } from '@/hooks/useApi';
import { useTranslation } from 'react-i18next';

const PERIOD_OPTIONS = [7, 14, 30] as const;

export function SlotAnalytics() {
  const { t } = useTranslation();
  const [days, setDays] = useState<(typeof PERIOD_OPTIONS)[number]>(7);
  const { data, isLoading } = useSlotAnalytics(days);

  const periodLabels: Record<(typeof PERIOD_OPTIONS)[number], string> = {
    7: t('slotAnalytics.period7'),
    14: t('slotAnalytics.period14'),
    30: t('slotAnalytics.period30'),
  };

  return (
    <Card>
      <CardHeader className="mb-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary-500" />
            {t('slotAnalytics.title')}
          </CardTitle>
          <div className="flex gap-2">
            {PERIOD_OPTIONS.map((p) => (
              <button
                key={p}
                onClick={() => setDays(p)}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  days === p
                    ? 'bg-primary-500 text-white'
                    : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
                }`}
              >
                {periodLabels[p]}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton variant="rectangular" height={160} className="w-full" />
            <div className="grid grid-cols-2 gap-4">
              <Skeleton variant="rectangular" height={120} />
              <Skeleton variant="rectangular" height={120} />
            </div>
          </div>
        ) : data?.message === 'Insufficient data' || !data ? (
          <div className="flex flex-col items-center justify-center py-12 text-dark-400">
            <TrendingUp className="w-12 h-12 mb-3 opacity-30" />
            <p>{t('slotAnalytics.noData')}</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Summary cards */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-dark-700/50 rounded-lg p-4">
                <p className="text-sm text-dark-400 mb-1">{t('slotAnalytics.totalSlots')}</p>
                <p className="text-2xl font-bold text-white">{data.total_slots_found}</p>
              </div>
              <div className="bg-dark-700/50 rounded-lg p-4">
                <p className="text-sm text-dark-400 mb-1">{t('slotAnalytics.avgPerDay')}</p>
                <p className="text-2xl font-bold text-white">{data.avg_slots_per_day}</p>
              </div>
            </div>

            {/* Best Hours chart */}
            {data.best_hours.length > 0 && (
              <div>
                <p className="text-sm font-medium text-dark-300 mb-3">
                  {t('slotAnalytics.bestHours')}
                </p>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={data.best_hours} margin={{ top: 4, right: 4, left: -20, bottom: 4 }}>
                    <XAxis dataKey="hour" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                    <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: '#1f2937', border: 'none', borderRadius: 8 }}
                      labelStyle={{ color: '#e5e7eb' }}
                      itemStyle={{ color: '#7c3aed' }}
                      formatter={(value: number) => [value, t('slotAnalytics.slots')]}
                    />
                    <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Best Days and Centres side by side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Best Days */}
              {data.best_days.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-dark-300 mb-3">
                    {t('slotAnalytics.bestDays')}
                  </p>
                  <ResponsiveContainer width="100%" height={120}>
                    <BarChart
                      data={data.best_days}
                      margin={{ top: 4, right: 4, left: -20, bottom: 4 }}
                    >
                      <XAxis dataKey="day" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ background: '#1f2937', border: 'none', borderRadius: 8 }}
                        labelStyle={{ color: '#e5e7eb' }}
                        itemStyle={{ color: '#7c3aed' }}
                        formatter={(value: number) => [value, t('slotAnalytics.slots')]}
                      />
                      <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Best Centres */}
              {data.best_centres.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-dark-300 mb-3">
                    {t('slotAnalytics.bestCentres')}
                  </p>
                  <ResponsiveContainer width="100%" height={120}>
                    <BarChart
                      data={data.best_centres}
                      margin={{ top: 4, right: 4, left: -20, bottom: 4 }}
                    >
                      <XAxis dataKey="centre" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                      <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ background: '#1f2937', border: 'none', borderRadius: 8 }}
                        labelStyle={{ color: '#e5e7eb' }}
                        itemStyle={{ color: '#7c3aed' }}
                        formatter={(value: number) => [value, t('slotAnalytics.slots')]}
                      />
                      <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
