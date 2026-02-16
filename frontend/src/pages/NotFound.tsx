import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/utils/constants';
import { useTranslation } from 'react-i18next';

export function NotFound() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="glass max-w-md w-full p-8 text-center">
        <AlertTriangle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
        <h1 className="text-4xl font-bold mb-2">{t('notFound.title')}</h1>
        <p className="text-dark-400 mb-6">
          {t('notFound.message')}
        </p>
        <Button variant="primary" onClick={() => navigate(ROUTES.DASHBOARD)}>
          {t('notFound.backToHome')}
        </Button>
      </div>
    </div>
  );
}

export default NotFound;
