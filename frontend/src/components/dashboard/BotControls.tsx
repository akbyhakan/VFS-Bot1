import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Play, Square } from 'lucide-react';
import { useBotStore } from '@/store/botStore';
import { useStartBot, useStopBot } from '@/hooks/useApi';
import { toast } from 'sonner';

export function BotControls() {
  const running = useBotStore((state) => state.running);
  const startBot = useStartBot();
  const stopBot = useStopBot();

  const handleStart = async () => {
    try {
      await startBot.mutateAsync({ action: 'start' });
      toast.success('Bot başarıyla başlatıldı');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Bot başlatılamadı');
    }
  };

  const handleStop = async () => {
    try {
      await stopBot.mutateAsync();
      toast.success('Bot durduruldu');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Bot durdurulamadı');
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Bot Kontrolleri</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-3">
          <Button
            variant="primary"
            onClick={handleStart}
            disabled={running || startBot.isPending}
            isLoading={startBot.isPending}
            leftIcon={<Play className="w-4 h-4" />}
            className="flex-1"
          >
            Başlat
          </Button>
          <Button
            variant="danger"
            onClick={handleStop}
            disabled={!running || stopBot.isPending}
            isLoading={stopBot.isPending}
            leftIcon={<Square className="w-4 h-4" />}
            className="flex-1"
          >
            Durdur
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
