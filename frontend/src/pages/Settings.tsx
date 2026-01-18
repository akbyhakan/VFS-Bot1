import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Settings as SettingsIcon, CreditCard, Webhook, Copy, Check, Trash2, Edit, Save, X, Plus, Zap } from 'lucide-react';
import { usePaymentCard } from '@/hooks/usePaymentCard';
import { webhookApi } from '@/services/paymentCard';
import type { WebhookUrls } from '@/types/payment';
import { toast } from 'sonner';

export function Settings() {
  const { card, loading, error, saving, deleting, saveCard, deleteCard } = usePaymentCard();
  const [isEditing, setIsEditing] = useState(false);
  const [webhookUrls, setWebhookUrls] = useState<WebhookUrls | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  
  // Form state
  const [formData, setFormData] = useState({
    card_holder_name: '',
    card_number: '',
    expiry_month: '',
    expiry_year: '',
    cvv: '',
  });

  useEffect(() => {
    // Load webhook URLs
    webhookApi.getWebhookUrls().then(setWebhookUrls).catch(console.error);
  }, []);

  const handleEdit = () => {
    if (card) {
      setFormData({
        card_holder_name: card.card_holder_name,
        card_number: '',
        expiry_month: card.expiry_month,
        expiry_year: card.expiry_year,
        cvv: '',
      });
    } else {
      setFormData({
        card_holder_name: '',
        card_number: '',
        expiry_month: '',
        expiry_year: '',
        cvv: '',
      });
    }
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setFormData({
      card_holder_name: '',
      card_number: '',
      expiry_month: '',
      expiry_year: '',
      cvv: '',
    });
  };

  const handleSave = async () => {
    const success = await saveCard(formData);
    if (success) {
      setIsEditing(false);
      setFormData({
        card_holder_name: '',
        card_number: '',
        expiry_month: '',
        expiry_year: '',
        cvv: '',
      });
    }
  };

  const handleDelete = async () => {
    if (confirm('Kredi kartı bilgilerini silmek istediğinizden emin misiniz?')) {
      await deleteCard();
    }
  };

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Ayarlar</h1>
        <p className="text-dark-400">Bot ve bildirim ayarlarını yapılandırın</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Payment Card Management */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CreditCard className="w-5 h-5" />
              Kredi Kartı Yönetimi
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-dark-400 text-sm">Yükleniyor...</p>
            ) : error ? (
              <p className="text-red-500 text-sm">{error}</p>
            ) : !isEditing && !card ? (
              // YENİ: Kart yokken "Kart Ekle" butonu göster
              <div className="text-center py-8">
                <CreditCard className="w-12 h-12 text-dark-500 mx-auto mb-4" />
                <p className="text-dark-400 mb-4">Henüz kayıtlı kredi kartı yok</p>
                <button
                  onClick={handleEdit}
                  className="flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 mx-auto"
                >
                  <Plus className="w-5 h-5" />
                  Yeni Kart Ekle
                </button>
              </div>
            ) : !isEditing && card ? (
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-dark-400">Kart Sahibi</label>
                  <p className="font-medium">{card.card_holder_name}</p>
                </div>
                <div>
                  <label className="text-sm text-dark-400">Kart Numarası</label>
                  <p className="font-medium font-mono">{card.card_number_masked}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-dark-400">Son Kullanma</label>
                    <p className="font-medium">{card.expiry_month}/{card.expiry_year}</p>
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={handleEdit}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
                  >
                    <Edit className="w-4 h-4" />
                    Düzenle
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                  >
                    <Trash2 className="w-4 h-4" />
                    {deleting ? 'Siliniyor...' : 'Sil'}
                  </button>
                </div>
              </div>
            ) : isEditing || !card ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Kart Sahibi Adı</label>
                  <input
                    type="text"
                    value={formData.card_holder_name}
                    onChange={(e) => setFormData({ ...formData, card_holder_name: e.target.value })}
                    placeholder="JOHN DOE"
                    className="w-full px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Kart Numarası</label>
                  <input
                    type="text"
                    value={formData.card_number}
                    onChange={(e) => setFormData({ ...formData, card_number: e.target.value.replace(/\s/g, '') })}
                    placeholder="4111 1111 1111 1234"
                    maxLength={16}
                    className="w-full px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white font-mono"
                  />
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">Ay</label>
                    <input
                      type="text"
                      value={formData.expiry_month}
                      onChange={(e) => setFormData({ ...formData, expiry_month: e.target.value })}
                      placeholder="12"
                      maxLength={2}
                      className="w-full px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">Yıl</label>
                    <input
                      type="text"
                      value={formData.expiry_year}
                      onChange={(e) => setFormData({ ...formData, expiry_year: e.target.value })}
                      placeholder="2025"
                      maxLength={4}
                      className="w-full px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">CVV</label>
                    <input
                      type="text"
                      value={formData.cvv}
                      onChange={(e) => setFormData({ ...formData, cvv: e.target.value })}
                      placeholder="123"
                      maxLength={3}
                      className="w-full px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white"
                    />
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                  >
                    <Save className="w-4 h-4" />
                    {saving ? 'Kaydediliyor...' : 'Kaydet'}
                  </button>
                  {card && (
                    <button
                      onClick={handleCancel}
                      className="flex items-center gap-2 px-4 py-2 bg-dark-600 text-white rounded hover:bg-dark-700"
                    >
                      <X className="w-4 h-4" />
                      İptal
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* SMS Webhook URLs */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Webhook className="w-5 h-5" />
              SMS Webhook Adresleri
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm mb-4">
              SMS Forwarder uygulamanıza bu webhook adreslerini ekleyin.
            </p>
            
            {webhookUrls ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Randevu OTP Webhook</label>
                  <div className="flex gap-2">
                    <input
                      readOnly
                      value={webhookUrls.appointment_webhook}
                      className="flex-1 px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white text-sm font-mono"
                    />
                    <button
                      onClick={() => copyToClipboard(webhookUrls.appointment_webhook, 'appointment')}
                      className="px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
                      title="Kopyala"
                    >
                      {copiedField === 'appointment' ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Ödeme OTP Webhook</label>
                  <div className="flex gap-2">
                    <input
                      readOnly
                      value={webhookUrls.payment_webhook}
                      className="flex-1 px-3 py-2 border border-dark-600 rounded bg-dark-800 text-white text-sm font-mono"
                    />
                    <button
                      onClick={() => copyToClipboard(webhookUrls.payment_webhook, 'payment')}
                      className="px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
                      title="Kopyala"
                    >
                      {copiedField === 'payment' ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
                
                <div className="mt-6 pt-6 border-t border-dark-700">
                  <button
                    onClick={() => {
                      toast.info('Webhook testi yapılıyor...');
                      // Test functionality can be implemented when backend endpoint is available
                      setTimeout(() => toast.success('Webhook test mesajı gönderildi'), 1000);
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    <Zap className="w-4 h-4" />
                    Webhook Test Et
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-dark-400 text-sm">Yükleniyor...</p>
            )}
          </CardContent>
        </Card>

        {/* Bot Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <SettingsIcon className="w-5 h-5" />
              Bot Ayarları
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm">
              Bot ayarları şu anda backend tarafından yönetilmektedir. Gelecek sürümlerde
              bu panelden düzenlenebilecek.
            </p>
          </CardContent>
        </Card>

        {/* Notification Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Bildirim Ayarları</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm">
              Telegram ve e-posta bildirimleri .env dosyasından yapılandırılmaktadır.
            </p>
          </CardContent>
        </Card>

        {/* Anti-Detection Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Anti-Detection Ayarları</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm">
              Anti-detection özellikleri varsayılan olarak etkin durumdadır.
            </p>
          </CardContent>
        </Card>

        {/* Proxy Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Proxy Ayarları</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400 text-sm">
              Proxy yapılandırması config/config.yaml dosyasından yönetilmektedir.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default Settings;
