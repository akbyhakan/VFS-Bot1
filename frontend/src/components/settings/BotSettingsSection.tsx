import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Timer, Save } from 'lucide-react';
import { getBotSettings, updateBotSettings, type BotSettingsResponse, type BotSettingsUpdate } from '@/services/bot';
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
  const [quarantineMinutes, setQuarantineMinutes] = useState<number>(30);
  const [maxFailures, setMaxFailures] = useState<number>(3);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [initialCooldown, setInitialCooldown] = useState<number>(10);
  const [initialQuarantine, setInitialQuarantine] = useState<number>(30);
  const [initialMaxFailures, setInitialMaxFailures] = useState<number>(3);

  const loadBotSettings = async () => {
    try {
      const settings = await getBotSettings();
      setBotSettings(settings);
      setCooldownMinutes(settings.cooldown_minutes);
      setInitialCooldown(settings.cooldown_minutes);
      setQuarantineMinutes(settings.quarantine_minutes);
      setInitialQuarantine(settings.quarantine_minutes);
      setMaxFailures(settings.max_failures);
      setInitialMaxFailures(settings.max_failures);
      setLoaded(true);
    } catch (error: unknown) {
      logger.error('Failed to load bot settings:', error);
      setLoaded(true);
    }
  };

  useEffect(() => {
    loadBotSettings();
  }, []);

  const hasChanges =
    cooldownMinutes !== initialCooldown ||
    quarantineMinutes !== initialQuarantine ||
    maxFailures !== initialMaxFailures;

  const handleSave = async () => {
    try {
      setSaving(true);
      const update: BotSettingsUpdate = { cooldown_minutes: cooldownMinutes };
      if (quarantineMinutes !== initialQuarantine) {
        update.quarantine_minutes = quarantineMinutes;
      }
      if (maxFailures !== initialMaxFailures) {
        update.max_failures = maxFailures;
      }
      await updateBotSettings(update);
      setInitialCooldown(cooldownMinutes);
      setInitialQuarantine(quarantineMinutes);
      setInitialMaxFailures(maxFailures);
      toast.success(t('settings.settingsUpdated'));
      await loadBotSettings();
    } catch (error: unknown) {
      logger.error('Failed to update bot settings:', error);
      toast.error(t('settings.settingsUpdateFailed'));
    } finally {
      setSaving(false);
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
        {!loaded ? (
          <p className="text-dark-400 text-sm">{t('settings.loading')}</p>
        ) : (
          <div className="space-y-6">
            {/* Cooldown Duration Slider */}
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
              <p className="text-dark-400 text-sm mt-2">
                {t('settings.cooldownDesc')}
              </p>
            </div>

            {/* Quarantine Duration Slider */}
            <div className="pt-4 border-t border-dark-700">
              <label className="block text-sm font-medium text-white mb-3">
                {t('settings.quarantineDuration', { minutes: quarantineMinutes })}
              </label>
              <input
                type="range"
                min="5"
                max="120"
                step="5"
                value={quarantineMinutes}
                onChange={(e) => setQuarantineMinutes(Number(e.target.value))}
                className="w-full h-2 bg-dark-600 rounded-lg appearance-none cursor-pointer slider-thumb"
                style={{ background: getSliderGradient(quarantineMinutes, 5, 120) }}
              />
              <div className="flex justify-between text-xs text-dark-400 mt-1">
                <span>5 {t('settings.minutes')}</span>
                <span>120 {t('settings.minutes')}</span>
              </div>
              <p className="text-dark-400 text-sm mt-2">
                {t('settings.quarantineDesc')}
              </p>
            </div>

            {/* Max Failures Input */}
            <div className="pt-4 border-t border-dark-700">
              <label className="block text-sm font-medium text-white mb-3">
                {t('settings.maxFailuresLabel', { count: maxFailures })}
              </label>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={maxFailures}
                onChange={(e) => setMaxFailures(Number(e.target.value))}
                className="w-full h-2 bg-dark-600 rounded-lg appearance-none cursor-pointer slider-thumb"
                style={{ background: getSliderGradient(maxFailures, 1, 10) }}
              />
              <div className="flex justify-between text-xs text-dark-400 mt-1">
                <span>1</span>
                <span>10</span>
              </div>
              <p className="text-dark-400 text-sm mt-2">
                {t('settings.maxFailuresDesc')}
              </p>
            </div>

            {hasChanges && (
              <Button
                variant="primary"
                leftIcon={<Save className="w-4 h-4" />}
                onClick={handleSave}
                isLoading={saving}
                fullWidth
              >
                {saving ? t('settings.saving') : t('settings.save')}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
