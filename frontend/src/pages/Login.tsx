import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuth } from '@/hooks/useAuth';
import { useRateLimit } from '@/hooks/useRateLimit';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { loginSchema, type LoginFormData } from '@/utils/validators';
import { ROUTES } from '@/utils/constants';
import { Activity, Lock, User } from 'lucide-react';
import { toast } from 'sonner';

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, error, clearError } = useAuth();
  
  // Rate limiting: 5 attempts, 30 second lockout
  const rateLimit = useRateLimit({
    maxAttempts: 5,
    windowMs: 30000,
    lockoutMs: 30000,
  });

  const from = (location.state as { from?: Location })?.from?.pathname || ROUTES.DASHBOARD;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
      rememberMe: false,
    },
  });

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  useEffect(() => {
    if (error) {
      toast.error(error);
      clearError();
    }
  }, [error, clearError]);

  const onSubmit = async (data: LoginFormData) => {
    if (rateLimit.isLocked) {
      toast.error(`Çok fazla başarısız deneme. Lütfen ${rateLimit.remainingTime} saniye bekleyin.`);
      return;
    }

    try {
      await login(
        { username: data.username, password: data.password },
        data.rememberMe || false
      );
      toast.success('Giriş başarılı');
      rateLimit.resetAttempts();
    } catch (error) {
      rateLimit.recordAttempt();
      // Error already handled by auth store and displayed via toast
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-dark-950">
      {/* Background effects */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary-600/20 rounded-full blur-[128px] animate-pulse" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-[128px] animate-pulse" style={{ animationDelay: '1s' }} />

      <Card className="w-full max-w-md glass-hover relative z-10 border-white/10">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-primary-500/10 rounded-full">
              <Activity className="w-12 h-12 text-primary-500" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gradient mb-2">VFS-Bot Dashboard</h1>
          <p className="text-dark-400">Otomatik Randevu Takip Sistemi</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <Input
            label="Kullanıcı Adı"
            type="text"
            leftIcon={<User className="w-4 h-4" />}
            error={errors.username?.message}
            {...register('username')}
          />

          <Input
            label="Şifre"
            type="password"
            leftIcon={<Lock className="w-4 h-4" />}
            error={errors.password?.message}
            {...register('password')}
          />

          <div className="flex items-center">
            <input
              type="checkbox"
              id="rememberMe"
              className="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-600 focus:ring-primary-500"
              {...register('rememberMe')}
            />
            <label htmlFor="rememberMe" className="ml-2 text-sm text-dark-300">
              Beni hatırla
            </label>
          </div>

          <Button
            type="submit"
            variant="primary"
            fullWidth
            isLoading={isSubmitting}
            disabled={!!rateLimit.isLocked}
          >
            {rateLimit.isLocked 
              ? `Bekleyin (${rateLimit.remainingTime}s)` 
              : 'Giriş Yap'}
          </Button>

          {rateLimit.isLocked && (
            <div className="text-center text-sm text-warning-400" role="alert">
              Çok fazla başarısız deneme. Lütfen bekleyin.
            </div>
          )}
        </form>

        <div className="mt-6 text-center text-xs text-dark-500">
          <p>VFS-Bot v2.0.0</p>
        </div>
      </Card>
    </div>
  );
}
