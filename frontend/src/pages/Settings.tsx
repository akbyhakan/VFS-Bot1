import { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Settings as SettingsIcon, CreditCard, Webhook, Copy, Check, Trash2, Edit, Save, X, Plus, Zap, Upload, FileText, Globe } from 'lucide-react';
import { usePaymentCard } from '@/hooks/usePaymentCard';
import { webhookApi } from '@/services/paymentCard';
import { proxyApi, type ProxyStats } from '@/services/proxy';
import type { WebhookUrls } from '@/types/payment';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { validateCardForm, formatCardNumber } from '@/utils/validators/creditCard';
import { toast } from 'sonner';

export function Settings() {
  const { card, loading, error, saving, deleting, saveCard, deleteCard } = usePaymentCard();
  const [isEditing, setIsEditing] = useState(false);
  const [webhookUrls, setWebhookUrls] = useState<WebhookUrls | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const { isOpen: isConfirmOpen, options: confirmOptions, confirm, handleConfirm, handleCancel: handleConfirmCancel } = useConfirmDialog();
  
  // Proxy state
  const [proxyStats, setProxyStats] = useState<ProxyStats | null>(null);
  const [proxyUploading, setProxyUploading] = useState(false);
  const [proxyFileName, setProxyFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Form state
  const [formData, setFormData] = useState({
    card_holder_name: '',
    card_number: '',
    expiry_month: '',
    expiry_year: '',
    cvv: '',
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    // Load webhook URLs
    webhookApi.getWebhookUrls().then(setWebhookUrls).catch(console.error);
    
    // Load proxy stats
    loadProxyStats();
  }, []);

  const loadProxyStats = async () => {
    try {
      const stats = await proxyApi.getProxyStats();
      setProxyStats(stats);
    } catch (error) {
      console.error('Failed to load proxy stats:', error);
    }
  };

  const handleProxyFileSelect = (file: File) => {
    if (!file.name.endsWith('.csv')) {
      toast.error('Lütfen .csv uzantılı bir dosya seçin');
      return;
    }
    uploadProxyFile(file);
  };

  const uploadProxyFile = async (file: File) => {
    try {
      setProxyUploading(true);
      const result = await proxyApi.uploadProxyCSV(file);
      setProxyFileName(result.filename);
      toast.success(`${result.count} proxy başarıyla yüklendi`);
      
      // Reload stats
      await loadProxyStats();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Proxy yüklenemedi');
    } finally {
      setProxyUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleProxyFileSelect(files[0]);
    }
  };

  const handleClearProxies = async () => {
    const confirmed = await confirm({
      title: 'Proxy Listesini Temizle',
      message: 'Tüm proxy listesini temizlemek istediğinizden emin misiniz?',
      confirmText: 'Temizle',
      cancelText: 'İptal',
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      await proxyApi.clearProxies();
      setProxyFileName(null);
      toast.success('Proxy listesi temizlendi');
      await loadProxyStats();
    } catch (error: any) {
      toast.error('Proxy listesi temizlenemedi');
    }
  };

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
    // Validate form
    const validation = validateCardForm(formData);
    
    if (!validation.isValid) {
      setFormErrors(validation.errors);
      toast.error('Lütfen form hatalarını düzeltin');
      return;
    }
    
    setFormErrors({});
    
    const success = await saveCard({
      ...formData,
      card_number: formData.card_number.replace(/\s/g, ''), // Remove spaces
    });
    
    if (success) {
      setIsEditing(false);
      setFormData({
        card_holder_name: '',
        card_number: '',
        expiry_month: '',
        expiry_year: '',
        cvv: '',
      });
      toast.success('Kart bilgileri kaydedildi');
    }
  };

  const handleDelete = async () => {
    const confirmed = await confirm({
      title: 'Kredi Kartını Sil',
      message: 'Kayıtlı kredi kartı bilgilerini silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.',
      confirmText: 'Sil',
      cancelText: 'İptal',
      variant: 'danger',
    });

    if (!confirmed) return;
    await deleteCard();
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
              // Kart yokken "Yeni Kart Ekle" butonu göster
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
                    onChange={(e) => {
                      setFormData({ ...formData, card_holder_name: e.target.value });
                      const newErrors = { ...formErrors };
                      delete newErrors.cardholderName;
                      setFormErrors(newErrors);
                    }}
                    placeholder="JOHN DOE"
                    className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${
                      formErrors.cardholderName ? 'border-red-500' : 'border-dark-600'
                    }`}
                  />
                  {formErrors.cardholderName && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.cardholderName}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Kart Numarası</label>
                  <input
                    type="text"
                    value={formatCardNumber(formData.card_number)}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\s/g, '');
                      if (/^\d*$/.test(value) && value.length <= 19) {
                        setFormData({ ...formData, card_number: value });
                        const newErrors = { ...formErrors };
                        delete newErrors.cardNumber;
                        setFormErrors(newErrors);
                      }
                    }}
                    placeholder="4111 1111 1111 1234"
                    maxLength={23}
                    autoComplete="cc-number"
                    inputMode="numeric"
                    className={`w-full px-3 py-2 border rounded bg-dark-800 text-white font-mono ${
                      formErrors.cardNumber ? 'border-red-500' : 'border-dark-600'
                    }`}
                  />
                  {formErrors.cardNumber && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.cardNumber}</p>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">Ay</label>
                    <input
                      type="text"
                      value={formData.expiry_month}
                      onChange={(e) => {
                        const value = e.target.value;
                        if (/^\d{0,2}$/.test(value)) {
                          setFormData({ ...formData, expiry_month: value });
                          const newErrors = { ...formErrors };
                          delete newErrors.expiryMonth;
                          setFormErrors(newErrors);
                        }
                      }}
                      placeholder="12"
                      maxLength={2}
                      inputMode="numeric"
                      className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${
                        formErrors.expiryMonth ? 'border-red-500' : 'border-dark-600'
                      }`}
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">Yıl</label>
                    <input
                      type="text"
                      value={formData.expiry_year}
                      onChange={(e) => {
                        const value = e.target.value;
                        if (/^\d{0,4}$/.test(value)) {
                          setFormData({ ...formData, expiry_year: value });
                          const newErrors = { ...formErrors };
                          delete newErrors.expiryYear;
                          setFormErrors(newErrors);
                        }
                      }}
                      placeholder="2025"
                      maxLength={4}
                      inputMode="numeric"
                      className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${
                        formErrors.expiryYear ? 'border-red-500' : 'border-dark-600'
                      }`}
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-dark-400 mb-1">CVV</label>
                    <input
                      type="password"
                      value={formData.cvv}
                      onChange={(e) => {
                        const value = e.target.value;
                        if (/^\d{0,4}$/.test(value)) {
                          setFormData({ ...formData, cvv: value });
                          const newErrors = { ...formErrors };
                          delete newErrors.cvv;
                          setFormErrors(newErrors);
                        }
                      }}
                      placeholder="•••"
                      maxLength={4}
                      autoComplete="cc-csc"
                      inputMode="numeric"
                      className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${
                        formErrors.cvv ? 'border-red-500' : 'border-dark-600'
                      }`}
                    />
                    {formErrors.cvv && (
                      <p className="text-red-500 text-xs mt-1">{formErrors.cvv}</p>
                    )}
                  </div>
                  {formErrors.expiryMonth && (
                    <div className="col-span-2">
                      <p className="text-red-500 text-xs mt-1">{formErrors.expiryMonth}</p>
                    </div>
                  )}
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

                {/* Webhook Test Butonu */}
                <div className="pt-4 border-t border-dark-700">
                  <button
                    onClick={async () => {
                      try {
                        const response = await fetch('/api/webhook/test', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                        });
                        if (response.ok) {
                          toast.success('Webhook bağlantısı başarılı!');
                        } else {
                          toast.error('Webhook bağlantısı başarısız');
                        }
                      } catch (error) {
                        toast.info('Webhook test edilemedi - Lütfen backend\'i kontrol edin');
                      }
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-dark-700 text-white rounded hover:bg-dark-600 w-full justify-center"
                  >
                    <Zap className="w-4 h-4" />
                    Webhook Bağlantısını Test Et
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
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Globe className="w-5 h-5" />
              🌐 Proxy Yönetimi (NetNut)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Statistics */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-dark-800 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-white">
                  {proxyStats?.total || 0}
                </div>
                <div className="text-sm text-dark-400">Toplam</div>
              </div>
              <div className="bg-dark-800 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-green-500">
                  {proxyStats?.active || 0}
                </div>
                <div className="text-sm text-dark-400">Aktif</div>
              </div>
              <div className="bg-dark-800 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-red-500">
                  {proxyStats?.failed || 0}
                </div>
                <div className="text-sm text-dark-400">Başarısız</div>
              </div>
            </div>

            {/* File Upload Area */}
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging
                  ? 'border-primary-500 bg-primary-900/20'
                  : 'border-dark-600 hover:border-dark-500'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Upload className="w-12 h-12 text-dark-500 mx-auto mb-4" />
              <p className="text-dark-300 mb-2">
                CSV dosyasını sürükleyip bırakın
              </p>
              <p className="text-dark-400 text-sm mb-4">veya</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleProxyFileSelect(file);
                }}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={proxyUploading}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {proxyUploading ? 'Yükleniyor...' : 'Dosya Seç'}
              </button>
              <p className="text-dark-400 text-xs mt-4">
                Format: endpoint (server:port:user:pass)
              </p>
            </div>

            {/* Uploaded File Info */}
            {proxyFileName && proxyStats && proxyStats.total > 0 && (
              <div className="bg-dark-800 rounded-lg p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-primary-500" />
                  <div>
                    <p className="font-medium text-white">{proxyFileName}</p>
                    <p className="text-sm text-dark-400">
                      {proxyStats.total} proxy yüklendi
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleClearProxies}
                  className="p-2 text-red-500 hover:bg-red-900/20 rounded"
                  title="Temizle"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Confirm Dialog */}
      {confirmOptions && (
        <ConfirmDialog
          isOpen={isConfirmOpen}
          onConfirm={handleConfirm}
          onCancel={handleConfirmCancel}
          title={confirmOptions.title}
          message={confirmOptions.message}
          confirmText={confirmOptions.confirmText}
          cancelText={confirmOptions.cancelText}
          variant={confirmOptions.variant}
          isLoading={deleting}
        />
      )}
    </div>
  );
}

export default Settings;
