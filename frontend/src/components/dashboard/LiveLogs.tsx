import { useBotStore } from '@/store/botStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { cn, getLogLevelColor } from '@/utils/helpers';
import { useEffect, useRef } from 'react';
import { FixedSizeList } from 'react-window';

export function LiveLogs() {
  const logs = useBotStore((state) => state.logs);
  const clearLogs = useBotStore((state) => state.clearLogs);
  const listRef = useRef<FixedSizeList>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (listRef.current && logs.length > 0) {
      listRef.current.scrollToItem(logs.length - 1, 'end');
    }
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
        <div className="bg-dark-900 rounded-lg p-4">
          {logs.length === 0 ? (
            <p className="text-dark-500 text-center py-8">Log mesajı bekleniyor...</p>
          ) : (
            <FixedSizeList
              ref={listRef}
              height={288}
              itemCount={logs.length}
              itemSize={24}
              width="100%"
              className="font-mono text-xs scrollbar-thin scrollbar-thumb-dark-700 scrollbar-track-dark-900"
            >
              {({ index, style }: { index: number; style: React.CSSProperties }) => {
                const log = logs[index];
                return (
                  <div
                    style={style}
                    className={cn(
                      'py-1 hover:bg-dark-800/50 transition-colors',
                      getLogLevelColor(log.level)
                    )}
                  >
                    <span className="text-dark-500">[{log.timestamp}]</span>{' '}
                    <span className="font-semibold">[{log.level}]</span> {log.message}
                  </div>
                );
              }}
            </FixedSizeList>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
