import { useState, useCallback } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Upload, FileText, Download, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { API_BASE_URL } from '@/utils/constants';
import { tokenManager } from '@/utils/tokenManager';

interface CSVImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

interface ImportResult {
  imported: number;
  failed: number;
  errors: string[];
  message: string;
}

export function CSVImportModal({ isOpen, onClose, onImportComplete }: CSVImportModalProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setImportResult(null);
      } else {
        toast.error('Lütfen sadece CSV dosyası seçin');
      }
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setImportResult(null);
      } else {
        toast.error('Lütfen sadece CSV dosyası seçin');
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error('Lütfen bir CSV dosyası seçin');
      return;
    }

    setIsUploading(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const token = tokenManager.getToken();
      const response = await axios.post<ImportResult>(
        `${API_BASE_URL}/api/users/import`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
            ...(token && { Authorization: `Bearer ${token}` }),
          },
        }
      );

      setImportResult(response.data);
      
      if (response.data.imported > 0) {
        toast.success(`${response.data.imported} VFS hesabı başarıyla eklendi`);
        onImportComplete();
      }
      
      if (response.data.failed > 0) {
        toast.warning(`${response.data.failed} hesap eklenemedi`);
      }
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error(error instanceof Error ? error.message : 'CSV yüklenirken hata oluştu');
      }
      console.error('CSV import error:', error);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownloadSample = () => {
    const headers = 'email,password,phone';
    const sample1 = 'user1@example.com,VfsPassword123,5551234567';
    const sample2 = 'user2@example.com,SecurePass456,5559876543';
    const sample3 = 'user3@example.com,MyPassword789,5554567890';
    const content = `${headers}\n${sample1}\n${sample2}\n${sample3}`;
    
    const blob = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'vfs-accounts-template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Örnek CSV dosyası indirildi');
  };

  const handleClose = () => {
    setSelectedFile(null);
    setImportResult(null);
    setIsDragging(false);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="CSV ile Toplu VFS Hesabı Yükle" size="lg">
      <div className="space-y-4">
        {/* Drag & Drop Area */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center transition-colors
            ${isDragging ? 'border-primary-500 bg-primary-500/10' : 'border-dark-600 hover:border-dark-500'}
          `}
        >
          <div className="flex flex-col items-center gap-4">
            <Upload className={`w-12 h-12 ${isDragging ? 'text-primary-400' : 'text-dark-400'}`} />
            
            {selectedFile ? (
              <div className="flex items-center gap-2 text-primary-400">
                <FileText className="w-5 h-5" />
                <span className="font-medium">{selectedFile.name}</span>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-dark-200 font-medium">CSV dosyasını sürükleyip bırakın</p>
                <p className="text-dark-400 text-sm">veya</p>
              </div>
            )}

            <label className="cursor-pointer">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
              />
              <span className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-dark-600 bg-dark-800 hover:bg-dark-700 text-dark-200 h-10 px-4 py-2">
                Dosya Seç
              </span>
            </label>
          </div>
        </div>

        {/* CSV Format Info */}
        <div className="bg-dark-800 rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-2 text-dark-200">
            <FileText className="w-4 h-4" />
            <span className="font-medium">CSV Formatı:</span>
          </div>
          <code className="block text-xs text-dark-400 font-mono overflow-x-auto">
            email,password,phone
          </code>
          <p className="text-sm text-dark-400 mt-2">
            Not: İlk satır başlık satırı olmalı, hesap verileri ikinci satırdan itibaren başlamalıdır.
          </p>
        </div>

        {/* Download Sample */}
        <Button
          type="button"
          variant="secondary"
          onClick={handleDownloadSample}
          leftIcon={<Download className="w-4 h-4" />}
          className="w-full"
        >
          Örnek CSV İndir
        </Button>

        {/* Import Result */}
        {importResult && (
          <div className="bg-dark-800 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2 font-medium">
              {importResult.imported > 0 && importResult.failed === 0 ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : importResult.failed > 0 && importResult.imported === 0 ? (
                <XCircle className="w-5 h-5 text-red-400" />
              ) : (
                <AlertCircle className="w-5 h-5 text-yellow-400" />
              )}
              <span>{importResult.message}</span>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-400" />
                <span>Başarılı: {importResult.imported}</span>
              </div>
              <div className="flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-400" />
                <span>Başarısız: {importResult.failed}</span>
              </div>
            </div>

            {importResult.errors.length > 0 && (
              <div className="space-y-1 text-sm">
                <p className="text-dark-400 font-medium">Hatalar:</p>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {importResult.errors.map((error, index) => (
                    <p key={index} className="text-red-400 text-xs">
                      • {error}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={handleClose} className="flex-1">
            {importResult ? 'Kapat' : 'İptal'}
          </Button>
          {!importResult && (
            <Button
              type="button"
              variant="primary"
              onClick={handleUpload}
              className="flex-1"
              isLoading={isUploading}
              disabled={!selectedFile}
            >
              Yükle
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
