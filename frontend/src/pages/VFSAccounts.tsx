import { useState, useMemo, useEffect } from 'react';
import { logger } from '@/utils/logger';
import { useTranslation } from 'react-i18next';
import { useVFSAccounts, useCreateVFSAccount, useUpdateVFSAccount, useDeleteVFSAccount, useToggleVFSAccountStatus } from '@/hooks/useApi';
import { useCreateWebhook, useDeleteWebhook } from '@/hooks/useWebhook';
import { useVFSAccountStats } from '@/hooks/useVFSAccountStats';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Table } from '@/components/ui/Table';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Loading } from '@/components/common/Loading';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { CSVImportModal } from '@/components/vfs-accounts/CSVImportModal';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { Plus, Pencil, Trash2, Power, Search, Download, X, Eye, EyeOff, Upload, Link2, Copy, Check, Users } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { vfsAccountSchema, createVFSAccountSchema, type VFSAccountFormData } from '@/utils/validators';
import { toast } from 'sonner';
import type { VFSAccount, CreateVFSAccountRequest } from '@/types/user';
import { cn, formatDate } from '@/utils/helpers';
import { webhookApi } from '@/services/webhook';

export function VFSAccounts() {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCSVImportModalOpen, setIsCSVImportModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<VFSAccount | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [webhooks, setWebhooks] = useState<Record<number, string>>({});
  const [copiedWebhook, setCopiedWebhook] = useState<number | null>(null);

  const { isOpen: isConfirmOpen, options: confirmOptions, confirm, handleConfirm, handleCancel } = useConfirmDialog();

  const { data: users, isLoading, refetch } = useVFSAccounts();
  const createUser = useCreateVFSAccount();
  const updateUser = useUpdateVFSAccount();
  const deleteUser = useDeleteVFSAccount();
  const toggleStatus = useToggleVFSAccountStatus();
  const createWebhookMutation = useCreateWebhook();
  const deleteWebhookMutation = useDeleteWebhook();
  const stats = useVFSAccountStats(users);

  // Load webhooks for all users
  useEffect(() => {
    if (users) {
      const loadWebhooks = async () => {
        for (const user of users) {
          try {
            const data = await webhookApi.getWebhook(user.id);
            if (data.webhook && data.webhook !== null) {
              setWebhooks(prev => ({ ...prev, [user.id]: data.webhook!.webhook_url }));
            }
          } catch (error) {
            // Silently ignore errors for individual webhook fetches
            logger.error(`Failed to load webhook for user ${user.id}:`, error);
          }
        }
      };
      loadWebhooks();
    }
  }, [users]);

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    if (!searchQuery) return users;
    
    const query = searchQuery.toLowerCase();
    return users.filter(user => 
      user.email.toLowerCase().includes(query) ||
      user.phone.includes(query)
    );
  }, [users, searchQuery]);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<VFSAccountFormData>({
    resolver: zodResolver(editingUser ? vfsAccountSchema : createVFSAccountSchema),
  });

  const openCreateModal = () => {
    setEditingUser(null);
    setShowPassword(false);
    reset({
      email: '',
      password: '',
      phone: '',
      is_active: true,
    });
    setIsModalOpen(true);
  };

  const openEditModal = (user: VFSAccount) => {
    setEditingUser(user);
    setShowPassword(false);
    reset({ ...user, password: '' }); // Don't populate password field
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingUser(null);
    setShowPassword(false);
    reset();
  };

  const onSubmit = async (data: VFSAccountFormData) => {
    try {
      if (editingUser) {
        // Only include password if it was filled in
        const updateData = { ...data };
        if (!updateData.password || updateData.password === '') {
          delete updateData.password;
        }
        await updateUser.mutateAsync({ id: editingUser.id, ...updateData });
        toast.success(t('users.accountUpdated'));
      } else {
        await createUser.mutateAsync(data as CreateVFSAccountRequest);
        toast.success(t('users.accountCreated'));
      }
      closeModal();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('users.operationFailed'));
    }
  };

  const handleDelete = async (user: VFSAccount) => {
    const confirmed = await confirm({
      title: t('users.deactivateAccountTitle'),
      message: t('users.deactivateAccountMessage', { email: user.email }),
      confirmText: t('users.deactivateAccountConfirm'),
      cancelText: t('users.deleteAccountCancel'),
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      await deleteUser.mutateAsync(user.id);
      toast.success(t('users.accountDeactivated'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('users.deactivateFailed'));
    }
  };

  const handleToggleStatus = async (user: VFSAccount) => {
    try {
      await toggleStatus.mutateAsync({ id: user.id, is_active: !user.is_active });
      toast.success(user.is_active ? t('users.accountDeactivated') : t('users.accountActivated'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('users.operationFailed'));
    }
  };

  const handleExport = () => {
    if (!filteredUsers.length) return;
    
    const headers = [t('users.email'), t('users.phone'), t('users.status'), t('users.added')];
    const rows = filteredUsers.map(user => [
      user.email,
      user.phone,
      user.is_active ? t('users.active') : t('users.inactive'),
      new Date(user.created_at).toLocaleDateString('tr-TR')
    ]);
    
    const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vfs-hesaplar-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(t('users.exportSuccess'));
  };

  const handleCreateWebhook = async (userId: number) => {
    try {
      const data = await createWebhookMutation.mutateAsync(userId);
      setWebhooks(prev => ({ ...prev, [userId]: data.webhook_url }));
      
      // Show success toast with full URL
      const fullUrl = `${window.location.origin}${data.webhook_url}`;
      toast.success(
        t('users.webhookCreated'),
        { duration: 5000 }
      );
      
      // Auto-copy to clipboard
      navigator.clipboard.writeText(fullUrl);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('users.webhookCreateFailed');
      toast.error(errorMessage);
    }
  };

  const handleCopyWebhook = (userId: number, url: string) => {
    const fullUrl = `${window.location.origin}${url}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedWebhook(userId);
    setTimeout(() => setCopiedWebhook(null), 2000);
    toast.success(t('users.webhookCopied'));
  };

  const handleDeleteWebhook = async (userId: number) => {
    try {
      await deleteWebhookMutation.mutateAsync(userId);
      setWebhooks(prev => {
        const newWebhooks = { ...prev };
        delete newWebhooks[userId];
        return newWebhooks;
      });
      toast.success(t('users.webhookDeleted'));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('users.webhookDeleteFailed');
      toast.error(errorMessage);
    }
  };

  if (isLoading) {
    return <Loading fullScreen text={t('users.loading')} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">{t('users.title')}</h1>
          <p className="text-dark-400">{t('users.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="secondary" 
            onClick={handleExport}
            disabled={!filteredUsers.length}
            leftIcon={<Download className="w-4 h-4" />}
          >
            {t('users.export')}
          </Button>
          <Button 
            variant="secondary" 
            onClick={() => setIsCSVImportModalOpen(true)}
            leftIcon={<Upload className="w-4 h-4" />}
          >
            {t('users.csvImport')}
          </Button>
          <Button variant="primary" onClick={openCreateModal} leftIcon={<Plus className="w-4 h-4" />}>
            {t('users.newAccount')}
          </Button>
        </div>
      </div>

      {/* Account Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-3 bg-dark-800 rounded-lg text-center border border-dark-700">
          <div className="flex items-center justify-center gap-2 mb-1">
            <Users className="w-4 h-4 text-dark-400" />
          </div>
          <p className="text-2xl font-bold">{stats.total_accounts}</p>
          <p className="text-xs text-dark-400">{t('users.totalAccounts')}</p>
        </div>
        <div className="p-3 bg-dark-800 rounded-lg text-center border border-dark-700">
          <p className="text-2xl font-bold text-green-400">{stats.active_accounts}</p>
          <p className="text-xs text-dark-400">{t('users.activeAccounts')}</p>
        </div>
        <div className="p-3 bg-dark-800 rounded-lg text-center border border-dark-700">
          <p className="text-2xl font-bold text-red-400">{stats.inactive_accounts}</p>
          <p className="text-xs text-dark-400">{t('users.inactiveAccounts')}</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('users.accountList')}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="mb-4">
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t('users.searchPlaceholder')}
                className="w-full pl-10 pr-10 py-2 bg-dark-800 border border-dark-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-200"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            {searchQuery && (
              <p className="text-sm text-dark-400 mt-2">
                {t('users.accountsFound', { count: filteredUsers.length })}
              </p>
            )}
          </div>
          
          <Table
            data={filteredUsers}
            columns={[
              { key: 'email', header: t('users.email') },
              { key: 'phone', header: t('users.phone') },
              {
                key: 'is_active',
                header: t('users.status'),
                render: (user) => (
                  <span
                    className={cn(
                      'badge',
                      user.is_active ? 'badge-success' : 'badge-error'
                    )}
                  >
                    {user.is_active ? t('users.active') : t('users.inactive')}
                  </span>
                ),
              },
              {
                key: 'created_at',
                header: t('users.added'),
                render: (user) => formatDate(user.created_at, 'PP'),
              },
              {
                key: 'webhook',
                header: t('users.webhook'),
                render: (user) => {
                  const webhookUrl = webhooks[user.id];
                  
                  if (!webhookUrl) {
                    return (
                      <button
                        onClick={() => handleCreateWebhook(user.id)}
                        disabled={createWebhookMutation.isPending}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 transition-colors"
                      >
                        <Link2 className="w-3 h-3" />
                        {createWebhookMutation.isPending ? t('users.creatingWebhook') : t('users.createWebhook')}
                      </button>
                    );
                  }
                  
                  return (
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-dark-400 font-mono truncate max-w-[100px]" title={webhookUrl}>
                        {webhookUrl.split('/').pop()?.slice(0, 8)}...
                      </span>
                      <button
                        onClick={() => handleCopyWebhook(user.id, webhookUrl)}
                        className="p-1 text-dark-400 hover:text-primary-400 transition-colors"
                        title="Kopyala"
                      >
                        {copiedWebhook === user.id ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                      </button>
                      <button
                        onClick={() => handleDeleteWebhook(user.id)}
                        className="p-1 text-dark-400 hover:text-red-400 transition-colors"
                        title="Sil"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  );
                },
              },
              {
                key: 'actions',
                header: t('users.actions'),
                render: (user) => (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleStatus(user)}
                      className="text-yellow-400 hover:text-yellow-300 transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-yellow-400"
                      aria-label={user.is_active ? t('users.deactivateAccount', { email: user.email }) : t('users.activateAccount', { email: user.email })}
                      title={user.is_active ? t('users.deactivate') : t('users.activate')}
                    >
                      <Power className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => openEditModal(user)}
                      className="text-blue-400 hover:text-blue-300 transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-blue-400"
                      aria-label={t('users.editAccountLabel', { email: user.email })}
                      title={t('users.editAccount')}
                    >
                      <Pencil className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(user)}
                      className="text-red-400 hover:text-red-300 transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-red-400"
                      aria-label={t('users.deleteAccountLabel', { email: user.email })}
                      title={t('users.deleteAccount')}
                    >
                      <Trash2 className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </div>
                ),
              },
            ]}
            keyExtractor={(user) => user.id}
            emptyMessage={t('users.noAccounts')}
          />
        </CardContent>
      </Card>

      {/* User Form Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title={editingUser ? t('users.editAccountTitle') : t('users.newAccountTitle')}
        size="lg"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <Input 
            label={t('users.emailLabel')} 
            type="email" 
            error={errors.email?.message} 
            {...register('email')} 
            placeholder={t('users.emailPlaceholder')}
          />
          
          <div className="relative">
            <Input 
              label={t('users.passwordLabel')} 
              type={showPassword ? "text" : "password"}
              error={errors.password?.message} 
              {...register('password')} 
              placeholder={editingUser ? t('users.passwordPlaceholderEdit') : t('users.passwordPlaceholder')}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-8 text-dark-400 hover:text-dark-200 transition-colors"
              aria-label={showPassword ? t('users.hidePassword') : t('users.showPassword')}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <Input 
            label={t('users.phoneLabel')} 
            error={errors.phone?.message} 
            {...register('phone')} 
            placeholder={t('users.phonePlaceholder')}
          />

          <div className="flex items-center gap-2">
            <input type="checkbox" id="is_active" {...register('is_active')} className="w-4 h-4" />
            <label htmlFor="is_active" className="text-sm">{t('users.activeLabel')}</label>
          </div>

          <div className="flex gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={closeModal} className="flex-1">
              {t('users.cancelBtn')}
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="flex-1"
              isLoading={createUser.isPending || updateUser.isPending}
            >
              {editingUser ? t('users.updateBtn') : t('users.saveBtn')}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Confirm Dialog */}
      {confirmOptions && (
        <ConfirmDialog
          isOpen={isConfirmOpen}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          title={confirmOptions.title}
          message={confirmOptions.message}
          confirmText={confirmOptions.confirmText}
          cancelText={confirmOptions.cancelText}
          variant={confirmOptions.variant}
          isLoading={deleteUser.isPending}
        />
      )}

      {/* CSV Import Modal */}
      <CSVImportModal
        isOpen={isCSVImportModalOpen}
        onClose={() => setIsCSVImportModalOpen(false)}
        onImportComplete={() => {
          // Refresh the users list
          refetch();
        }}
      />
    </div>
  );
}

export default VFSAccounts;
