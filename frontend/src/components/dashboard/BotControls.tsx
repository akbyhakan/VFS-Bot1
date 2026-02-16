import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Play, Square, RotateCcw, Search } from 'lucide-react';
import { useBotStore } from '@/store/botStore';
import { useStartBot, useStopBot, useRestartBot, useCheckNow } from '@/hooks/useApi';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

export function BotControls() {
  const running = useBotStore((state) => state.running);
  const startBot = useStartBot();
  const stopBot = useStopBot();
  const restartBot = useRestartBot();
  const checkNow = useCheckNow();
  const { t } = useTranslation();

  const handleStart = async () => {
    try {
      await startBot.mutateAsync({ action: 'start' });
      toast.success(t('botControls.startSuccess'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('botControls.startError'));
    }
  };

  const handleStop = async () => {
    try {
      await stopBot.mutateAsync();
      toast.success(t('botControls.stopSuccess'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('botControls.stopError'));
    }
  };

  const handleRestart = async () => {
    try {
      await restartBot.mutateAsync();
      toast.success(t('botControls.restartSuccess'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('botControls.restartError'));
    }
  };

  const handleManualCheck = async () => {
    try {
      await checkNow.mutateAsync();
      toast.success(t('botControls.checkSuccess'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('botControls.checkError'));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t('botControls.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:flex md:flex-wrap gap-3">
          <Button
            variant="primary"
            onClick={handleStart}
            disabled={running || startBot.isPending}
            isLoading={startBot.isPending}
            leftIcon={<Play className="w-4 h-4" />}
            className="flex-1"
          >
            {t('botControls.start')}
          </Button>
          <Button
            variant="danger"
            onClick={handleStop}
            disabled={!running || stopBot.isPending}
            isLoading={stopBot.isPending}
            leftIcon={<Square className="w-4 h-4" />}
            className="flex-1"
          >
            {t('botControls.stop')}
          </Button>
          <Button
            variant="secondary"
            onClick={handleRestart}
            disabled={!running || restartBot.isPending}
            isLoading={restartBot.isPending}
            leftIcon={<RotateCcw className="w-4 h-4" />}
            className="flex-1"
          >
            {t('botControls.restart')}
          </Button>
          <Button
            variant="outline"
            onClick={handleManualCheck}
            disabled={!running || checkNow.isPending}
            isLoading={checkNow.isPending}
            leftIcon={<Search className="w-4 h-4" />}
            className="flex-1"
          >
            {t('botControls.checkNow')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
