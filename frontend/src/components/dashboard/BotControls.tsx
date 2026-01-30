import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Play, Square, RotateCcw, Search } from 'lucide-react';
import { useBotStore } from '@/store/botStore';
import { useStartBot, useStopBot, useRestartBot, useCheckNow } from '@/hooks/useApi';
import { toast } from 'sonner';

export function BotControls() {
  const running = useBotStore((state) => state.running);
  const startBot = useStartBot();
  const stopBot = useStopBot();
  const restartBot = useRestartBot();
  const checkNow = useCheckNow();

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

  const handleRestart = async () => {
    try {
      await restartBot.mutateAsync();
      toast.success('Bot yeniden başlatıldı');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Bot yeniden başlatılamadı');
    }
  };

  const handleManualCheck = async () => {
    try {
      await checkNow.mutateAsync();
      toast.success('Manuel kontrol başlatıldı');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Manuel kontrol başlatılamadı');
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
          <Button
            variant="secondary"
            onClick={handleRestart}
            disabled={!running || restartBot.isPending}
            isLoading={restartBot.isPending}
            leftIcon={<RotateCcw className="w-4 h-4" />}
            className="flex-1"
          >
            Yeniden Başlat
          </Button>
          <Button
            variant="outline"
            onClick={handleManualCheck}
            disabled={!running || checkNow.isPending}
            isLoading={checkNow.isPending}
            leftIcon={<Search className="w-4 h-4" />}
            className="flex-1"
          >
            Şimdi Kontrol Et
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
