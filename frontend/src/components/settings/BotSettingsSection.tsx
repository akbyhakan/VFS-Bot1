import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Timer, Save } from 'lucide-react';
import { getBotSettings, updateBotSettings, type BotSettingsResponse } from '@/services/bot';
import { logger } from '@/utils/logger';
import { toast } from 'sonner';

const getSliderGradient = (value: number, min: number, max: number) => {
  const percentage = ((value - min) / (max - min)) * 100;
  return `linear-gradient(to right, #7c3aed 0%, #7c3aed ${percentage}%, #374151 ${percentage}%, #374151 100%)`;
};

export function BotSettingsSection() {
  const { t } = useTranslation();
  const [botSettings, setBotSettings] = useState<BotSettingsResponse | null>(null);
  const [cooldownMinutes, setCooldownMinutes] = useState<number>(10);
  const [cooldownSaving, setCooldownSaving] = useState(false);
  const [cooldownLoaded, setCooldownLoaded] = useState(false);
  const [initialCooldown, setInitialCooldown] = useState<number>(10);

  const loadBotSettings = async () => {
    try {
      const settings = await getBotSettings();
      setBotSettings(settings);
      setCooldownMinutes(settings.cooldown_minutes);
      setInitialCooldown(settings.cooldown_minutes);
      setCooldownLoaded(true);
    } catch (error: unknown) {
      logger.error('Failed to load bot settings:', error);
      setCooldownLoaded(true);
    }
  };

  useEffect(() => {
    loadBotSettings();
  }, []);

  const handleSaveCooldown = async () => {
    try {
      setCooldownSaving(true);
      await updateBotSettings({ cooldown_minutes: cooldownMinutes });
      setInitialCooldown(cooldownMinutes);
      toast.success(t('settings.cooldownUpdated'));
      await loadBotSettings();
    } catch (error: unknown) {
      logger.error('Failed to update cooldown:', error);
      toast.error(t('settings.cooldownUpdateFailed'));
    } finally {
      setCooldownSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Timer className="w-5 h-5" />
          {t('settings.botSettings')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!cooldownLoaded ? (
          <p className="text-dark-400 text-sm">{t('settings.loading')}</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white mb-3">
                {t('settings.cooldownDuration', { minutes: cooldownMinutes })}
              </label>
              <input
                type="range"
                min="5"
                max="60"
                step="1"
                value={cooldownMinutes}
                onChange={(e) => setCooldownMinutes(Number(e.target.value))}
                className="w-full h-2 bg-dark-600 rounded-lg appearance-none cursor-pointer slider-thumb"
                style={{ background: getSliderGradient(cooldownMinutes, 5, 60) }}
              />
              <div className="flex justify-between text-xs text-dark-400 mt-1">
                <span>5 {t('settings.minutes')}</span>
                <span>60 {t('settings.minutes')}</span>
              </div>
              <p className="text-dark-400 text-sm mt-3">
                {t('settings.cooldownDesc')}
              </p>
            </div>

            {botSettings && (
              <div className="pt-4 border-t border-dark-700 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-dark-400">{t('settings.quarantineDuration')}:</span>
                  <span className="text-white">{botSettings.quarantine_minutes} {t('settings.minutes')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-dark-400">{t('settings.maxFailures')}:</span>
                  <span className="text-white">{botSettings.max_failures}</span>
                </div>
              </div>
            )}

            {cooldownMinutes !== initialCooldown && (
              <Button
                variant="primary"
                leftIcon={<Save className="w-4 h-4" />}
                onClick={handleSaveCooldown}
                isLoading={cooldownSaving}
                fullWidth
              >
                {cooldownSaving ? t('settings.saving') : t('settings.save')}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
