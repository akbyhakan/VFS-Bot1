import { useBotStore } from '@/store/botStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { cn, getLogLevelColor } from '@/utils/helpers';
import { useEffect, useRef } from 'react';

export function LiveLogs() {
  const logs = useBotStore((state) => state.logs);
  const clearLogs = useBotStore((state) => state.clearLogs);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <Card className="h-96">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">📋 Canlı Loglar</CardTitle>
          <button
            onClick={clearLogs}
            className="px-3 py-1.5 text-xs text-dark-400 hover:text-dark-200 hover:bg-dark-700 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500"
            aria-label="Tüm logları temizle"
          >
            Temizle
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="bg-dark-900 rounded-lg p-4 h-72 overflow-y-auto font-mono text-xs">
          {logs.length === 0 ? (
            <p className="text-dark-500 text-center py-8">Log mesajı bekleniyor...</p>
          ) : (
            <>
              {logs.map((log, index) => (
                <div
                  key={index}
                  className={cn(
                    'py-1 hover:bg-dark-800/50 transition-colors',
                    getLogLevelColor(log.level)
                  )}
                >
                  <span className="text-dark-500">[{log.timestamp}]</span>{' '}
                  <span className="font-semibold">[{log.level}]</span> {log.message}
                </div>
              ))}
              <div ref={logsEndRef} />
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
