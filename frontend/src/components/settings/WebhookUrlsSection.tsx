import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Webhook, Copy, Check, Zap } from 'lucide-react';
import { api } from '@/services/api';
import { toast } from 'sonner';
import { useWebhookUrls } from '@/hooks/useWebhook';

export function WebhookUrlsSection() {
  const { t } = useTranslation();
  const { data: webhookUrls } = useWebhookUrls();
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Webhook className="w-5 h-5" />
          {t('settings.smsWebhooks')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-dark-400 text-sm mb-4">
          {t('settings.smsWebhookDesc')}
        </p>

        {webhookUrls ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">{t('settings.appointmentOTP')}</label>
              <div className="flex gap-2">
                <input
                  readOnly
                  value={webhookUrls.appointment_webhook}
                  className="flex-1 px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white text-sm font-mono"
                />
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => copyToClipboard(webhookUrls.appointment_webhook, 'appointment')}
                  title={t('settings.copy')}
                >
                  {copiedField === 'appointment' ? (
                    <Check className="w-4 h-4" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>

            <div>
              <label className="block text-sm text-dark-400 mb-1">{t('settings.paymentOTP')}</label>
              <div className="flex gap-2">
                <input
                  readOnly
                  value={webhookUrls.payment_webhook}
                  className="flex-1 px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white text-sm font-mono"
                />
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => copyToClipboard(webhookUrls.payment_webhook, 'payment')}
                  title={t('settings.copy')}
                >
                  {copiedField === 'payment' ? (
                    <Check className="w-4 h-4" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="pt-4 border-t border-dark-700">
              <Button
                variant="outline"
                leftIcon={<Zap className="w-4 h-4" />}
                fullWidth
                onClick={async () => {
                  try {
                    await api.post('/api/webhook/test');
                    toast.success(t('settings.webhookSuccess'));
                  } catch (error) {
                    toast.error(t('settings.webhookFailed'));
                  }
                }}
              >
                {t('settings.testWebhook')}
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-dark-400 text-sm">{t('settings.loading')}</p>
        )}
      </CardContent>
    </Card>
  );
}
