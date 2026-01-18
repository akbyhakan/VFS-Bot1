import { useState, useMemo } from 'react';
import { useLogs } from '@/hooks/useApi';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Loading } from '@/components/common/Loading';
import { cn, getLogLevelColor } from '@/utils/helpers';
import { FileText, Search, Filter, Download, X, RefreshCw, Trash2 } from 'lucide-react';
import DOMPurify from 'dompurify';
import { toast } from 'sonner';

type LogLevel = 'ALL' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';

const LOG_LEVELS: LogLevel[] = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'SUCCESS'];

/**
 * Sanitize log content to prevent XSS attacks
 */
const sanitizeLog = (log: string): string => {
  return DOMPurify.sanitize(log, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'code'],
    ALLOWED_ATTR: [],
  });
};

/**
 * Extract log level from log string
 */
const extractLogLevel = (log: string): string => {
  const match = log.match(/\[(DEBUG|INFO|WARNING|ERROR|SUCCESS)\]/);
  return match ? match[1] : 'INFO';
};

export function Logs() {
  const { data, isLoading, refetch, isRefetching } = useLogs(500);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLevel, setSelectedLevel] = useState<LogLevel>('ALL');
  const [localLogs, setLocalLogs] = useState<string[] | null>(null);

  // Use local logs if cleared, otherwise use API data
  const apiLogs = data?.logs || [];
  const logs = localLogs !== null ? localLogs : apiLogs;

  // Filter and search logs
  const filteredLogs = useMemo(() => {
    let result = logs;

    // Filter by level
    if (selectedLevel !== 'ALL') {
      result = result.filter((log) => {
        const level = extractLogLevel(log);
        return level === selectedLevel;
      });
    }

    // Search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((log) =>
        log.toLowerCase().includes(query)
      );
    }

    return result;
  }, [logs, selectedLevel, searchQuery]);

  const hasFilters = searchQuery !== '' || selectedLevel !== 'ALL';

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedLevel('ALL');
  };

  const handleRefresh = () => {
    setLocalLogs(null);
    refetch();
    toast.success('Loglar yenileniyor...');
  };

  const handleClear = () => {
    setLocalLogs([]);
    toast.success('Loglar temizlendi (sadece görünüm)');
  };

  const handleExport = () => {
    const content = filteredLogs.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    // Generate filename with current date in YYYY-MM-DD format
    const dateStr = new Date().toISOString().split('T')[0];
    link.download = `logs-${dateStr}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return <Loading fullScreen text="Loglar yükleniyor..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">Loglar</h1>
          <p className="text-dark-400">Tüm bot aktivitelerini görüntüleyin</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleClear}
            className="flex items-center gap-2 px-4 py-2 bg-dark-700 text-dark-200 rounded-lg hover:bg-dark-600 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Temizle
          </button>
          <button
            onClick={handleRefresh}
            disabled={isRefetching}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />
            {isRefetching ? 'Yenileniyor...' : 'Yenile'}
          </button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Log Kayıtları
              {hasFilters && (
                <span className="text-xs text-dark-400 font-normal">
                  ({filteredLogs.length} / {logs.length})
                </span>
              )}
            </CardTitle>
            <button
              onClick={handleExport}
              disabled={filteredLogs.length === 0}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-dark-700 text-dark-200 rounded hover:bg-dark-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Logları indir"
            >
              <Download className="w-4 h-4" />
              İndir
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-wrap gap-4 mb-4">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Log ara..."
                className="w-full pl-10 pr-4 py-2 bg-dark-800 border border-dark-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-200"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Level filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-dark-400" />
              <select
                value={selectedLevel}
                onChange={(e) => setSelectedLevel(e.target.value as LogLevel)}
                className="px-3 py-2 bg-dark-800 border border-dark-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {LOG_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level === 'ALL' ? 'Tüm Seviyeler' : level}
                  </option>
                ))}
              </select>
            </div>

            {/* Clear filters */}
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="px-3 py-2 text-sm text-dark-400 hover:text-dark-200 transition-colors"
              >
                Filtreleri Temizle
              </button>
            )}
          </div>

          {/* Logs */}
          <div className="bg-dark-900 rounded-lg p-4 max-h-[600px] overflow-y-auto font-mono text-xs">
            {filteredLogs.length === 0 ? (
              <p className="text-dark-500 text-center py-8">
                {hasFilters ? 'Filtreye uygun log bulunamadı' : 'Henüz log kaydı yok'}
              </p>
            ) : (
              filteredLogs.map((log, index) => {
                const sanitizedLog = sanitizeLog(log);
                const level = extractLogLevel(sanitizedLog);

                return (
                  <div
                    key={index}
                    className={cn(
                      'py-1 hover:bg-dark-800/50 transition-colors border-l-2 pl-2 mb-1',
                      getLogLevelColor(level)
                    )}
                    style={{ borderLeftColor: 'currentColor' }}
                  >
                    {sanitizedLog}
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default Logs;
