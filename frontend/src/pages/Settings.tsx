import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Settings as SettingsIcon } from 'lucide-react';

export function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Ayarlar</h1>
        <p className="text-dark-400">Bot ve bildirim ayarlarını yapılandırın</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
