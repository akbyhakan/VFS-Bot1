import { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { CreditCard, Webhook, Copy, Check, Trash2, Edit, Save, X, Plus, Zap, Upload, FileText, Globe, Timer } from 'lucide-react';
import { usePaymentCard } from '@/hooks/usePaymentCard';
import { webhookApi } from '@/services/paymentCard';
import { proxyApi, type ProxyStats } from '@/services/proxy';
import { getBotSettings, updateBotSettings, type BotSettingsResponse } from '@/services/bot';
import type { WebhookUrls } from '@/types/payment';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { validateCardForm, formatCardNumber } from '@/utils/validators/creditCard';
import { logger } from '@/utils/logger';
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
  
  // Bot settings state
  const [botSettings, setBotSettings] = useState<BotSettingsResponse | null>(null);
  const [cooldownMinutes, setCooldownMinutes] = useState<number>(10);
  const [cooldownSaving, setCooldownSaving] = useState(false);
  const [cooldownLoaded, setCooldownLoaded] = useState(false);
  const [initialCooldown, setInitialCooldown] = useState<number>(10);
  
  // Form state
  const [formData, setFormData] = useState({
    card_holder_name: '',
    card_number: '',
    expiry_month: '',
    expiry_year: '',
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    // Load webhook URLs
    webhookApi.getWebhookUrls().then(setWebhookUrls).catch((error: unknown) => {
      logger.error('Failed to load webhook URLs:', error);
    });
    
    // Load proxy stats
    loadProxyStats();
    
    // Load bot settings
    loadBotSettings();
  }, []);

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

  const loadProxyStats = async () => {
    try {
      const stats = await proxyApi.getProxyStats();
      setProxyStats(stats);
    } catch (error: unknown) {
      logger.error('Failed to load proxy stats:', error);
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
    } catch (error: unknown) {
      const message = error instanceof Error && 'response' in error 
        ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail 
        : 'Proxy yüklenemedi';
      toast.error(message || 'Proxy yüklenemedi');
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
    } catch (error: unknown) {
      logger.error('Failed to clear proxies:', error);
      toast.error('Proxy listesi temizlenemedi');
    }
  };

  const handleSaveCooldown = async () => {
    try {
      setCooldownSaving(true);
      await updateBotSettings({ cooldown_minutes: cooldownMinutes });
      setInitialCooldown(cooldownMinutes);
      toast.success('Cooldown süresi güncellendi');
      // Reload settings to confirm
      await loadBotSettings();
    } catch (error: unknown) {
      logger.error('Failed to update cooldown:', error);
      toast.error('Cooldown süresi güncellenemedi');
    } finally {
      setCooldownSaving(false);
    }
  };

  // Helper function for slider gradient
  const getSliderGradient = (value: number, min: number, max: number) => {
    const percentage = ((value - min) / (max - min)) * 100;
    return `linear-gradient(to right, #7c3aed 0%, #7c3aed ${percentage}%, #374151 ${percentage}%, #374151 100%)`;
  };

  const handleEdit = () => {
    if (card) {
      setFormData({
        card_holder_name: card.card_holder_name,
        card_number: '',
        expiry_month: card.expiry_month,
        expiry_year: card.expiry_year,
      });
    } else {
      setFormData({
        card_holder_name: '',
        card_number: '',
        expiry_month: '',
        expiry_year: '',
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
                <Button
                  variant="primary"
                  leftIcon={<Plus className="w-5 h-5" />}
                  onClick={handleEdit}
                >
                  Yeni Kart Ekle
                </Button>
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
                  <Button
                    variant="primary"
                    leftIcon={<Edit className="w-4 h-4" />}
                    onClick={handleEdit}
                  >
                    Düzenle
                  </Button>
                  <Button
                    variant="danger"
                    leftIcon={<Trash2 className="w-4 h-4" />}
                    onClick={handleDelete}
                    isLoading={deleting}
                  >
                    {deleting ? 'Siliniyor...' : 'Sil'}
                  </Button>
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
                  {formErrors.expiryMonth && (
                    <div className="col-span-2">
                      <p className="text-red-500 text-xs mt-1">{formErrors.expiryMonth}</p>
                    </div>
                  )}
                </div>
                <div className="flex gap-2 mt-4">
                  <Button
                    variant="primary"
                    leftIcon={<Save className="w-4 h-4" />}
                    onClick={handleSave}
                    isLoading={saving}
                  >
                    {saving ? 'Kaydediliyor...' : 'Kaydet'}
                  </Button>
                  {card && (
                    <Button
                      variant="secondary"
                      leftIcon={<X className="w-4 h-4" />}
                      onClick={handleCancel}
                    >
                      İptal
                    </Button>
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
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => copyToClipboard(webhookUrls.appointment_webhook, 'appointment')}
                      title="Kopyala"
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
                  <label className="block text-sm text-dark-400 mb-1">Ödeme OTP Webhook</label>
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
                      title="Kopyala"
                    >
                      {copiedField === 'payment' ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Webhook Test Butonu */}
                <div className="pt-4 border-t border-dark-700">
                  <Button
                    variant="outline"
                    leftIcon={<Zap className="w-4 h-4" />}
                    className="w-full" // Note: Button doesn't have fullWidth prop yet
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
                  >
                    Webhook Bağlantısını Test Et
                  </Button>
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
              <Timer className="w-5 h-5" />
              Bot Ayarları
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!cooldownLoaded ? (
              <p className="text-dark-400 text-sm">Yükleniyor...</p>
            ) : (
              <div className="space-y-4">
                {/* Cooldown Setting */}
                <div>
                  <label className="block text-sm font-medium text-white mb-3">
                    Cooldown Süresi: {cooldownMinutes} dakika
                  </label>
                  <input
                    type="range"
                    min="5"
                    max="60"
                    step="1"
                    value={cooldownMinutes}
                    onChange={(e) => setCooldownMinutes(Number(e.target.value))}
                    className="w-full h-2 bg-dark-600 rounded-lg appearance-none cursor-pointer slider-thumb"
                    style={{
                      background: getSliderGradient(cooldownMinutes, 5, 60)
                    }}
                  />
                  <div className="flex justify-between text-xs text-dark-400 mt-1">
                    <span>5 dk</span>
                    <span>60 dk</span>
                  </div>
                  <p className="text-dark-400 text-sm mt-3">
                    Hesap kullanımı sonrası bekleme süresi
                  </p>
                </div>

                {/* Display other settings (read-only) */}
                {botSettings && (
                  <div className="pt-4 border-t border-dark-700 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-dark-400">Karantina Süresi:</span>
                      <span className="text-white">{botSettings.quarantine_minutes} dakika</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-dark-400">Maksimum Başarısızlık:</span>
                      <span className="text-white">{botSettings.max_failures}</span>
                    </div>
                  </div>
                )}

                {/* Save Button */}
                {cooldownMinutes !== initialCooldown && (
                  <Button
                    variant="primary"
                    leftIcon={<Save className="w-4 h-4" />}
                    onClick={handleSaveCooldown}
                    isLoading={cooldownSaving}
                    className="w-full" // Note: Button doesn't have fullWidth prop yet
                  >
                    {cooldownSaving ? 'Kaydediliyor...' : 'Kaydet'}
                  </Button>
                )}
              </div>
            )}
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
              <Button
                variant="primary"
                onClick={() => fileInputRef.current?.click()}
                isLoading={proxyUploading}
              >
                {proxyUploading ? 'Yükleniyor...' : 'Dosya Seç'}
              </Button>
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
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearProxies}
                  title="Temizle"
                >
                  <Trash2 className="w-5 h-5" />
                </Button>
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
