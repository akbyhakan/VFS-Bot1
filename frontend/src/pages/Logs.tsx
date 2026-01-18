import { useState, useMemo } from 'react';
import { useLogs } from '@/hooks/useApi';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Loading } from '@/components/common/Loading';
import { cn, getLogLevelColor } from '@/utils/helpers';
import { FileText, RefreshCw, Trash2, Search, Filter, Download, X } from 'lucide-react';
import DOMPurify from 'dompurify';
import { toast } from 'sonner';

type LogLevel = 'ALL' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';

const LOG_LEVELS: LogLevel[] = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'SUCCESS'];

/**
 * Sanitize log content to prevent XSS attacks
 * Allows basic text formatting tags for legitimate log content
 */
const sanitizeLog = (log: string): string => {
  return DOMPurify.sanitize(log, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'code'],
    ALLOWED_ATTR: [],
  });
};

const extractLogLevel = (log: string): string => {
  const match = log.match(/\[(DEBUG|INFO|WARNING|ERROR|SUCCESS)\]/);
  return match ? match[1] : 'INFO';
};

export function Logs() {
  const { data, isLoading, refetch, isRefetching } = useLogs(500);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLevel, setSelectedLevel] = useState<LogLevel>('ALL');

  const filteredLogs = useMemo(() => {
    const logs = data?.logs || [];
    let result = logs;

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(log => sanitizeLog(log).toLowerCase().includes(query));
    }

    // Filter by log level
    if (selectedLevel !== 'ALL') {
      result = result.filter(log => {
        const level = extractLogLevel(log);
        return level === selectedLevel;
      });
    }

    return result;
  }, [data?.logs, searchQuery, selectedLevel]);

  const logs = data?.logs || [];

  const handleClearLogs = () => {
    // Note: Backend endpoint for clearing logs needs to be implemented
    if (confirm('Tüm logları temizlemek istediğinizden emin misiniz?\n\nNot: Bu özellik henüz backend tarafında implement edilmemiştir.')) {
      toast.info('Log temizleme özelliği yakında eklenecek');
    }
  };

  const handleDownloadLogs = () => {
    const logContent = filteredLogs.join('\n');
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Loglar indirildi');
  };

  const hasFilters = searchQuery || selectedLevel !== 'ALL';

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
          <Button
            variant="secondary"
            onClick={() => refetch()}
            disabled={isRefetching}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />}
          >
            {isRefetching ? 'Yenileniyor...' : 'Yenile'}
          </Button>
          <Button
            variant="secondary"
            onClick={handleDownloadLogs}
            disabled={filteredLogs.length === 0}
            leftIcon={<Download className="w-4 h-4" />}
          >
            İndir
          </Button>
          <Button
            variant="danger"
            onClick={handleClearLogs}
            leftIcon={<Trash2 className="w-4 h-4" />}
          >
            Temizle
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Log Kayıtları
              {hasFilters && (
                <span className="text-sm text-dark-400 font-normal">
                  ({filteredLogs.length} / {logs.length})
                </span>
              )}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="mb-4 space-y-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="text"
                placeholder="Loglarda ara..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-10 py-2 border border-dark-600 rounded bg-dark-800 text-white"
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

            {/* Level Filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-dark-400" />
              <div className="flex gap-2 flex-wrap">
                {LOG_LEVELS.map((level) => (
                  <button
                    key={level}
                    onClick={() => setSelectedLevel(level)}
                    className={cn(
                      'px-3 py-1 rounded text-sm transition-colors',
                      selectedLevel === level
                        ? 'bg-primary-600 text-white'
                        : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
                    )}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Logs Display */}
          <div className="bg-dark-900 rounded-lg p-4 max-h-[600px] overflow-y-auto font-mono text-xs">
            {filteredLogs.length === 0 ? (
              <p className="text-dark-500 text-center py-8">
                {hasFilters ? 'Filtrelere uygun log bulunamadı' : 'Henüz log kaydı yok'}
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
