import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { PaymentCardSection } from '@/components/settings/PaymentCardSection';
import { WebhookUrlsSection } from '@/components/settings/WebhookUrlsSection';
import { BotSettingsSection } from '@/components/settings/BotSettingsSection';
import { ProxyManagementSection } from '@/components/settings/ProxyManagementSection';

export function Settings() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">{t('settings.pageTitle')}</h1>
        <p className="text-dark-400">{t('settings.pageSubtitle')}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PaymentCardSection />
        <WebhookUrlsSection />
        <BotSettingsSection />

        {/* Notification Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('settings.notificationSettings')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm">
              {t('settings.notificationDesc')}
            </p>
          </CardContent>
        </Card>

        {/* Anti-Detection Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('settings.antiDetection')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm">
              {t('settings.antiDetectionDesc')}
            </p>
          </CardContent>
        </Card>

        <ProxyManagementSection />
      </div>
    </div>
  );
}

export default Settings;
