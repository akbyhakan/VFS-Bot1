import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/utils/constants';

export function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="glass max-w-md w-full p-8 text-center">
        <AlertTriangle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
        <h1 className="text-4xl font-bold mb-2">404</h1>
        <p className="text-dark-400 mb-6">
          Aradığınız sayfa bulunamadı
        </p>
        <Button variant="primary" onClick={() => navigate(ROUTES.DASHBOARD)}>
          Ana Sayfaya Dön
        </Button>
      </div>
    </div>
  );
}
