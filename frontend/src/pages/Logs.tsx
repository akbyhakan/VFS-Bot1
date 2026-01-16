import { useLogs } from '@/hooks/useApi';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Loading } from '@/components/common/Loading';
import { cn, getLogLevelColor } from '@/utils/helpers';
import { FileText } from 'lucide-react';
import DOMPurify from 'dompurify';

/**
 * Sanitize log content to prevent XSS attacks
 */
const sanitizeLog = (log: string): string => {
  return DOMPurify.sanitize(log, { ALLOWED_TAGS: [] });
};

export function Logs() {
  const { data, isLoading } = useLogs(500);

  if (isLoading) {
    return <Loading fullScreen text="Loglar yükleniyor..." />;
  }

  const logs = data?.logs || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Loglar</h1>
        <p className="text-dark-400">Tüm bot aktivitelerini görüntüleyin</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Log Kayıtları
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-dark-900 rounded-lg p-4 max-h-[600px] overflow-y-auto font-mono text-xs">
            {logs.length === 0 ? (
              <p className="text-dark-500 text-center py-8">Henüz log kaydı yok</p>
            ) : (
              logs.map((log, index) => {
                // Parse log entry to extract level
                const sanitizedLog = sanitizeLog(log);
                const levelMatch = sanitizedLog.match(/\[(DEBUG|INFO|WARNING|ERROR|SUCCESS)\]/);
                const level = levelMatch ? levelMatch[1] : 'INFO';

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
