import { useState, useMemo } from 'react';
import { useUsers, useCreateUser, useUpdateUser, useDeleteUser, useToggleUserStatus } from '@/hooks/useApi';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Table } from '@/components/ui/Table';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Loading } from '@/components/common/Loading';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { CSVImportModal } from '@/components/users/CSVImportModal';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { Plus, Pencil, Trash2, Power, Search, Download, X, Eye, EyeOff, Upload } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { userSchema, createUserSchema, type UserFormData } from '@/utils/validators';
import { toast } from 'sonner';
import type { User, CreateUserRequest } from '@/types/user';
import { cn, formatDate } from '@/utils/helpers';

export function Users() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCSVImportModalOpen, setIsCSVImportModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const { isOpen: isConfirmOpen, options: confirmOptions, confirm, handleConfirm, handleCancel } = useConfirmDialog();

  const { data: users, isLoading, refetch } = useUsers();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();
  const toggleStatus = useToggleUserStatus();

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    if (!searchQuery) return users;
    
    const query = searchQuery.toLowerCase();
    return users.filter(user => 
      user.first_name.toLowerCase().includes(query) ||
      user.last_name.toLowerCase().includes(query) ||
      user.email.toLowerCase().includes(query) ||
      user.phone.includes(query) ||
      user.center_name.toLowerCase().includes(query)
    );
  }, [users, searchQuery]);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<UserFormData>({
    resolver: zodResolver(editingUser ? userSchema : createUserSchema),
  });

  const openCreateModal = () => {
    setEditingUser(null);
    setShowPassword(false);
    reset({
      email: '',
      password: '',
      phone: '',
      first_name: '',
      last_name: '',
      center_name: '',
      visa_category: '',
      visa_subcategory: '',
      is_active: true,
    });
    setIsModalOpen(true);
  };

  const openEditModal = (user: User) => {
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

  const onSubmit = async (data: UserFormData) => {
    try {
      if (editingUser) {
        // Only include password if it was filled in
        const updateData = { ...data };
        if (!updateData.password || updateData.password === '') {
          delete updateData.password;
        }
        await updateUser.mutateAsync({ id: editingUser.id, ...updateData });
        toast.success('Kullanıcı güncellendi');
      } else {
        await createUser.mutateAsync(data as CreateUserRequest);
        toast.success('Kullanıcı oluşturuldu');
      }
      closeModal();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'İşlem başarısız');
    }
  };

  const handleDelete = async (user: User) => {
    const confirmed = await confirm({
      title: 'Kullanıcıyı Sil',
      message: `"${user.first_name} ${user.last_name}" kullanıcısını silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.`,
      confirmText: 'Sil',
      cancelText: 'İptal',
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      await deleteUser.mutateAsync(user.id);
      toast.success('Kullanıcı silindi');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Silme başarısız');
    }
  };

  const handleToggleStatus = async (user: User) => {
    try {
      await toggleStatus.mutateAsync({ id: user.id, is_active: !user.is_active });
      toast.success(user.is_active ? 'Kullanıcı pasifleştirildi' : 'Kullanıcı aktifleştirildi');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'İşlem başarısız');
    }
  };

  const handleExport = () => {
    if (!filteredUsers.length) return;
    
    const headers = ['ID', 'Ad', 'Soyad', 'E-posta', 'Telefon', 'Merkez', 'Vize Kategorisi', 'Durum', 'Oluşturulma'];
    const rows = filteredUsers.map(user => [
      user.id,
      user.first_name,
      user.last_name,
      user.email,
      user.phone,
      user.center_name,
      user.visa_category,
      user.is_active ? 'Aktif' : 'Pasif',
      new Date(user.created_at).toLocaleDateString('tr-TR')
    ]);
    
    const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kullanicilar-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Kullanıcı listesi indirildi');
  };

  if (isLoading) {
    return <Loading fullScreen text="Kullanıcılar yükleniyor..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">Kullanıcı Yönetimi</h1>
          <p className="text-dark-400">VFS kullanıcılarını görüntüleyin ve yönetin</p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="secondary" 
            onClick={handleExport}
            disabled={!filteredUsers.length}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export
          </Button>
          <Button 
            variant="secondary" 
            onClick={() => setIsCSVImportModalOpen(true)}
            leftIcon={<Upload className="w-4 h-4" />}
          >
            CSV Import
          </Button>
          <Button variant="primary" onClick={openCreateModal} leftIcon={<Plus className="w-4 h-4" />}>
            Yeni Kullanıcı
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Kullanıcı Listesi</CardTitle>
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
                placeholder="İsim, e-posta, telefon veya merkez ile ara..."
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
                {filteredUsers.length} kullanıcı bulundu
              </p>
            )}
          </div>
          
          <Table
            data={filteredUsers}
            columns={[
              {
                key: 'first_name',
                header: 'Ad Soyad',
                render: (user) => `${user.first_name} ${user.last_name}`,
              },
              { key: 'email', header: 'E-posta' },
              { key: 'phone', header: 'Telefon' },
              { key: 'center_name', header: 'Merkez' },
              { key: 'visa_category', header: 'Vize Kategorisi' },
              {
                key: 'is_active',
                header: 'Durum',
                render: (user) => (
                  <span
                    className={cn(
                      'badge',
                      user.is_active ? 'badge-success' : 'badge-error'
                    )}
                  >
                    {user.is_active ? 'Aktif' : 'Pasif'}
                  </span>
                ),
              },
              {
                key: 'created_at',
                header: 'Oluşturulma',
                render: (user) => formatDate(user.created_at, 'PP'),
              },
              {
                key: 'actions',
                header: 'İşlemler',
                render: (user) => (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleStatus(user)}
                      className="text-yellow-400 hover:text-yellow-300 transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-yellow-400"
                      aria-label={user.is_active ? `${user.first_name} ${user.last_name} kullanıcısını pasifleştir` : `${user.first_name} ${user.last_name} kullanıcısını aktifleştir`}
                      title={user.is_active ? 'Pasifleştir' : 'Aktifleştir'}
                    >
                      <Power className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => openEditModal(user)}
                      className="text-blue-400 hover:text-blue-300 transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-blue-400"
                      aria-label={`${user.first_name} ${user.last_name} kullanıcısını düzenle`}
                      title="Düzenle"
                    >
                      <Pencil className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(user)}
                      className="text-red-400 hover:text-red-300 transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-red-400"
                      aria-label={`${user.first_name} ${user.last_name} kullanıcısını sil`}
                      title="Sil"
                    >
                      <Trash2 className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </div>
                ),
              },
            ]}
            keyExtractor={(user) => user.id}
            emptyMessage="Henüz kullanıcı bulunmuyor"
          />
        </CardContent>
      </Card>

      {/* User Form Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title={editingUser ? 'Kullanıcı Düzenle' : 'Yeni Kullanıcı'}
        size="lg"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input label="Ad" error={errors.first_name?.message} {...register('first_name')} />
            <Input label="Soyad" error={errors.last_name?.message} {...register('last_name')} />
          </div>

          <Input label="E-posta" type="email" error={errors.email?.message} {...register('email')} />
          
          {/* Password field with show/hide toggle */}
          <div className="relative">
            <Input 
              label="VFS Şifresi" 
              type={showPassword ? "text" : "password"}
              error={errors.password?.message} 
              {...register('password')} 
              placeholder={editingUser ? "Değiştirmek için yeni şifre girin (boş bırakılırsa değişmez)" : "VFS hesap şifresi"}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-8 text-dark-400 hover:text-dark-200 transition-colors"
              aria-label={showPassword ? "Şifreyi gizle" : "Şifreyi göster"}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <Input label="Telefon" error={errors.phone?.message} {...register('phone')} />
          <Input label="Merkez" error={errors.center_name?.message} {...register('center_name')} />

          <div className="grid grid-cols-2 gap-4">
            <Input label="Vize Kategorisi" error={errors.visa_category?.message} {...register('visa_category')} />
            <Input label="Alt Kategori" error={errors.visa_subcategory?.message} {...register('visa_subcategory')} />
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" id="is_active" {...register('is_active')} className="w-4 h-4" />
            <label htmlFor="is_active" className="text-sm">Aktif</label>
          </div>

          <div className="flex gap-3 pt-4">
            <Button type="button" variant="secondary" onClick={closeModal} className="flex-1">
              İptal
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="flex-1"
              isLoading={createUser.isPending || updateUser.isPending}
            >
              {editingUser ? 'Güncelle' : 'Oluştur'}
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

export default Users;
