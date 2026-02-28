import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Globe, Upload, FileText, Trash2 } from 'lucide-react';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { toast } from 'sonner';
import { useProxyStats, useUploadProxy, useClearProxies } from '@/hooks/useProxy';

export function ProxyManagementSection() {
  const { t } = useTranslation();
  const { data: proxyStats } = useProxyStats();
  const uploadProxy = useUploadProxy();
  const clearProxiesMutation = useClearProxies();
  const [proxyFileName, setProxyFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { isOpen: isConfirmOpen, options: confirmOptions, confirm, handleConfirm, handleCancel: handleConfirmCancel } = useConfirmDialog();

  const uploadProxyFile = async (file: File) => {
    try {
      const result = await uploadProxy.mutateAsync(file);
      setProxyFileName(result.filename);
      toast.success(t('settings.proxyUploaded', { count: result.count }));
    } catch (error: unknown) {
      const message = error instanceof Error && 'response' in error
        ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : t('settings.proxyUploadFailed');
      toast.error(message || t('settings.proxyUploadFailed'));
    }
  };

  const handleProxyFileSelect = (file: File) => {
    if (!file.name.endsWith('.csv')) {
      toast.error(t('settings.selectCsvFile'));
      return;
    }
    uploadProxyFile(file);
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
    if (files.length > 0) handleProxyFileSelect(files[0]);
  };

  const handleClearProxies = async () => {
    const confirmed = await confirm({
      title: t('settings.clearProxiesTitle'),
      message: t('settings.clearProxiesMessage'),
      confirmText: t('settings.clearProxiesConfirm'),
      cancelText: t('settings.clearProxiesCancel'),
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await clearProxiesMutation.mutateAsync();
      setProxyFileName(null);
      toast.success(t('settings.proxiesCleared'));
    } catch (error: unknown) {
      toast.error(t('settings.proxiesClearFailed'));
    }
  };

  return (
    <>
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Globe className="w-5 h-5" />
            {t('settings.proxyManagement')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-dark-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-white">{proxyStats?.total || 0}</div>
              <div className="text-sm text-dark-400">{t('settings.proxyTotal')}</div>
            </div>
            <div className="bg-dark-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-green-500">{proxyStats?.active || 0}</div>
              <div className="text-sm text-dark-400">{t('settings.proxyActive')}</div>
            </div>
            <div className="bg-dark-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-amber-500">{proxyStats?.inactive || 0}</div>
              <div className="text-sm text-dark-400">{t('settings.proxyInactive')}</div>
            </div>
            <div className="bg-dark-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-red-500">{proxyStats?.failed || 0}</div>
              <div className="text-sm text-dark-400">{t('settings.proxyFailed')}</div>
            </div>
          </div>

          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              isDragging ? 'border-primary-500 bg-primary-900/20' : 'border-dark-600 hover:border-dark-500'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Upload className="w-12 h-12 text-dark-500 mx-auto mb-4" />
            <p className="text-dark-300 mb-2">{t('settings.dragDropCSV')}</p>
            <p className="text-dark-400 text-sm mb-4">{t('settings.or')}</p>
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
              isLoading={uploadProxy.isPending}
            >
              {uploadProxy.isPending ? t('settings.uploading') : t('settings.selectFile')}
            </Button>
            <p className="text-dark-400 text-xs mt-4">{t('settings.proxyFormat')}</p>
          </div>

          {proxyFileName && proxyStats && proxyStats.total > 0 && (
            <div className="bg-dark-800 rounded-lg p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-primary-500" />
                <div>
                  <p className="font-medium text-white">{proxyFileName}</p>
                  <p className="text-sm text-dark-400">
                    {t('settings.proxiesLoaded', { count: proxyStats.total })}
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={handleClearProxies} title={t('settings.clearProxies')}>
                <Trash2 className="w-5 h-5" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

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
        />
      )}
    </>
  );
}
