import { Lock } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { useBotStore } from '@/store/botStore';
import { useTranslation } from 'react-i18next';

export function ReadOnlyBanner() {
  const { t } = useTranslation();
  const read_only = useBotStore((state) => state.read_only);

  if (!read_only) {
    return null;
  }

  return (
    <Card
      className="animate-fade-in mb-6 border-2 border-orange-500/50 bg-orange-500/5"
      role="alert"
      aria-live="polite"
      aria-label="Read-only mode active"
    >
      <div className="flex items-start gap-4">
        <div className="p-2 rounded-lg flex-shrink-0 bg-orange-500/10">
          <Lock className="w-6 h-6 text-orange-500" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-orange-400 mb-2">
            {t('readOnlyBanner.title')}
          </h3>
          <p className="text-dark-300 text-sm">{t('readOnlyBanner.message')}</p>
        </div>
      </div>
    </Card>
  );
}
