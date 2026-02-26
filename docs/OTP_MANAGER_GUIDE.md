# OTP Manager Kullanım Rehberi

## Genel Bakış

OTP Manager, VFS otomasyonu için merkezi bir OTP (One-Time Password) yönetim sistemidir. Bu sistem:

- 100-150+ farklı sanal e-posta adresi için **tek bir IMAP bağlantısı** kullanır
- Hem **e-posta** hem de **SMS** kaynaklı OTP'leri yönetir
- **Thread-safe** tasarımla eşzamanlı bot oturumlarını destekler
- **Event-driven** mimari ile düşük gecikme süresi sağlar
- Otomatik session cleanup ile kaynak yönetimini optimize eder

## Mimari

### Modüler Yapı

OTP Manager artık modüler bir yapıya sahiptir. Monolitik tek dosya yerine, her bileşen kendi dosyasında bulunmaktadır:

```
src/services/otp_manager/
├── __init__.py           # Public API — tüm sınıfları ve fonksiyonları re-export eder
├── models.py             # OTPSource, SessionState, OTPEntry, BotSession, IMAPConfig
├── pattern_matcher.py    # HTMLTextExtractor, OTPPatternMatcher
├── session_registry.py   # SessionRegistry
├── email_processor.py    # EmailProcessor
├── imap_listener.py      # IMAPListener
├── sms_handler.py        # SMSWebhookHandler
└── manager.py            # OTPManager class + get_otp_manager() singleton
```


### Temel Bileşenler

1. **OTPManager**: Ana yönetici sınıf
2. **IMAPListener**: Catch-all mailbox'ı dinleyen thread
3. **EmailProcessor**: E-postaları işleyen ve OTP çıkaran bileşen
4. **SessionRegistry**: Bot oturumlarını yöneten thread-safe registry
5. **SMSWebhookHandler**: SMS OTP'lerini işleyen handler

### Veri Akışı

```
Email OTP Flow:
VFS Email → Catch-all Mailbox → IMAPListener → EmailProcessor → SessionRegistry → Bot Session

SMS OTP Flow:
SMS Provider → Webhook → SMSWebhookHandler → SessionRegistry → Bot Session

Manual OTP Flow:
User Input → OTPManager.manual_otp_input() → SessionRegistry → Bot Session
```

## Kurulum

### 1. Gerekli Paketler

Tüm gerekli paketler `pyproject.toml` dosyasında mevcuttur:
```bash
pip install -e .
```

### 2. Çevresel Değişkenler

`.env` dosyanıza aşağıdaki değişkenleri ekleyin:

```env
# OTP Manager Configuration
OTP_MANAGER_EMAIL=akby.hakan@vizecep.com
OTP_MANAGER_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
OTP_MANAGER_TIMEOUT=120
OTP_MANAGER_SESSION_TIMEOUT=600
```

### 3. Microsoft 365 App Password Oluşturma

1. [account.microsoft.com/security](https://account.microsoft.com/security) adresine gidin
2. "Advanced security options" → "App passwords" seçeneğine tıklayın
3. "Create a new app password" ile yeni bir şifre oluşturun
4. Oluşturulan şifreyi `OTP_MANAGER_APP_PASSWORD` değişkenine ekleyin

## Kullanım

### Temel Kullanım

```python
from src.services.otp_manager import OTPManager

# 1. OTP Manager'ı başlat
manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

# 2. Bot oturumu kaydet
session_id = manager.register_session(
    target_email="hollanda_vize@vizecep.com",
    phone_number="+905551234567",
    country="Netherlands"
)

# 3. OTP bekle (Email veya SMS hangisi gelirse)
otp = manager.wait_for_otp(session_id, timeout=120)
print(f"Received OTP: {otp}")

# 4. Temizlik
manager.unregister_session(session_id)
manager.stop()
```

### Singleton Pattern Kullanımı

Uygulamanızda tek bir global instance kullanmak için:

```python
from src.services.otp_manager import get_otp_manager

# İlk çağrıda email ve password gerekli
manager = get_otp_manager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

# Sonraki çağrılarda parametresiz kullanılabilir
manager = get_otp_manager()
```

### Gelişmiş Konfigürasyon

```python
from src.services.otp_manager import OTPManager, IMAPConfig

# Custom IMAP config
imap_config = IMAPConfig(
    host="outlook.office365.com",
    port=993,
    folder="INBOX"
)

# Custom OTP patterns
custom_patterns = [
    r"PIN[:\s]+(\d{4})",  # 4-digit PIN
    r"verification[:\s]+(\d{8})"  # 8-digit code
]

manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx",
    imap_config=imap_config,
    otp_timeout_seconds=180,  # 3 dakika
    session_timeout_seconds=900,  # 15 dakika
    max_email_age_seconds=600,  # 10 dakika
    custom_patterns=custom_patterns
)
```

## API Referansı

### OTPManager

#### `__init__(email, app_password, **kwargs)`

OTP Manager'ı oluşturur.

**Parametreler:**
- `email` (str): Microsoft 365 catch-all mailbox adresi
- `app_password` (str): Microsoft 365 App Password
- `imap_config` (IMAPConfig, optional): IMAP yapılandırması
- `otp_timeout_seconds` (int): OTP bekleme timeout süresi (varsayılan: 120)
- `session_timeout_seconds` (int): Session otomatik sonlanma süresi (varsayılan: 600)
- `max_email_age_seconds` (int): İşlenecek e-posta maksimum yaşı (varsayılan: 300)
- `custom_patterns` (List[str], optional): Özel OTP regex pattern'leri

#### `start()`

OTP Manager'ı başlatır (IMAP listener ve cleanup scheduler).

```python
manager.start()
```

#### `stop()`

OTP Manager'ı durdurur.

```python
manager.stop()
```

#### `register_session(target_email=None, phone_number=None, country=None, metadata=None)`

Yeni bir bot oturumu kaydeder.

**Parametreler:**
- `target_email` (str, optional): Hedef e-posta adresi (ör: "bot55@vizecep.com")
- `phone_number` (str, optional): Telefon numarası (ör: "+905551234567")
- `country` (str, optional): Ülke kodu (ör: "Netherlands")
- `metadata` (dict, optional): Ek metadata

**Dönüş:** Session ID (str)

**Not:** En az `target_email` veya `phone_number` belirtilmelidir.

```python
session_id = manager.register_session(
    target_email="bot55@vizecep.com",
    phone_number="+905551234567",
    country="Netherlands",
    metadata={"purpose": "tourist_visa"}
)
```

#### `unregister_session(session_id)`

Bir oturumu kaydından çıkarır.

**Parametreler:**
- `session_id` (str): Session ID

```python
manager.unregister_session(session_id)
```

#### `wait_for_otp(session_id, timeout=None)`

OTP kodunu bekler (e-posta veya SMS).

**Parametreler:**
- `session_id` (str): Session ID
- `timeout` (int, optional): Timeout süresi (saniye)

**Dönüş:** OTP kodu (str) veya None (timeout)

```python
otp = manager.wait_for_otp(session_id, timeout=120)
if otp:
    print(f"OTP received: {otp}")
else:
    print("OTP timeout")
```

#### `process_sms_webhook(phone_number, message)`

SMS webhook'unu işler ve OTP'yi ilgili oturuma yönlendirir.

**Parametreler:**
- `phone_number` (str): Telefon numarası
- `message` (str): SMS mesaj içeriği

**Dönüş:** OTP kodu (str) veya None

```python
otp = manager.process_sms_webhook("+905551234567", "Your code is 123456")
```

#### `manual_otp_input(session_id, otp_code)`

Manuel OTP girişi yapar.

**Parametreler:**
- `session_id` (str): Session ID
- `otp_code` (str): OTP kodu

**Dönüş:** True (başarılı) veya False

```python
success = manager.manual_otp_input(session_id, "123456")
```

#### `health_check()`

OTP Manager sağlık durumunu döner.

**Dönüş:** Sağlık metrikleri (dict)

```python
health = manager.health_check()
print(f"Status: {health['status']}")
print(f"Active sessions: {health['active_sessions']}")
```

## Örnek Senaryolar

### Senaryo 1: Sadece E-posta OTP

```python
manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

session_id = manager.register_session(
    target_email="netherlands_bot@vizecep.com"
)

otp = manager.wait_for_otp(session_id)
print(f"Email OTP: {otp}")

manager.unregister_session(session_id)
manager.stop()
```

### Senaryo 2: Sadece SMS OTP

```python
manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

session_id = manager.register_session(
    phone_number="+905551234567"
)

# Webhook üzerinden SMS geldiğinde otomatik işlenir
otp = manager.wait_for_otp(session_id)
print(f"SMS OTP: {otp}")

manager.unregister_session(session_id)
manager.stop()
```

### Senaryo 3: Hibrit (E-posta + SMS)

```python
manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

session_id = manager.register_session(
    target_email="bot@vizecep.com",
    phone_number="+905551234567"
)

# Hangisi önce gelirse onu kullan
otp = manager.wait_for_otp(session_id)
print(f"OTP: {otp}")

manager.unregister_session(session_id)
manager.stop()
```

### Senaryo 4: Manuel Fallback

```python
manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

session_id = manager.register_session(
    target_email="bot@vizecep.com"
)

# Otomatik OTP bekle (timeout: 60 saniye)
otp = manager.wait_for_otp(session_id, timeout=60)

if not otp:
    # Manuel input fallback
    print("OTP timeout, manual input required")
    manual_otp = input("Enter OTP: ")
    manager.manual_otp_input(session_id, manual_otp)
    otp = manual_otp

print(f"OTP: {otp}")
manager.unregister_session(session_id)
manager.stop()
```

### Senaryo 5: Çoklu Bot Oturumları

```python
manager = OTPManager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

# 100+ bot için session kaydet
sessions = {}
for i in range(100):
    session_id = manager.register_session(
        target_email=f"bot{i}@vizecep.com",
        phone_number=f"+9055512345{i:02d}"
    )
    sessions[i] = session_id

# Her bot için paralel OTP bekle
import concurrent.futures

def wait_otp(bot_id, session_id):
    otp = manager.wait_for_otp(session_id)
    return (bot_id, otp)

with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
    futures = [
        executor.submit(wait_otp, i, session_id)
        for i, session_id in sessions.items()
    ]
    
    for future in concurrent.futures.as_completed(futures):
        bot_id, otp = future.result()
        print(f"Bot {bot_id} received OTP: {otp}")

# Cleanup
for session_id in sessions.values():
    manager.unregister_session(session_id)

manager.stop()
```

## SMS Webhook Entegrasyonu

Mevcut `src/services/otp_webhook.py` ile entegrasyon:

```python
from src.services.otp_manager import get_otp_manager
from src.services.otp_manager.otp_webhook import get_otp_service

# OTP Manager'ı başlat
otp_manager = get_otp_manager(
    email="akby.hakan@vizecep.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
otp_manager.start()

# SMS webhook geldiğinde
async def handle_sms_webhook(phone_number: str, message: str):
    otp_service = get_otp_service()
    await otp_service.process_sms(phone_number, message)
    
    # Yeni OTP Manager'a da gönder
    otp_manager.process_sms_webhook(phone_number, message)
```

## Performans ve Limitler

### Performans Metrikleri

- **IMAP Poll Interval**: 3 saniye (ayarlanabilir)
- **OTP Teslim Süresi**: <5 saniye (ortalama)
- **Maksimum Eşzamanlı Session**: 150+ (test edildi)
- **Thread Safety**: Full thread-safe tasarım
- **Memory Usage**: ~10MB (100 session için)

### Limitler

- **IMAP Bağlantı**: Tek bağlantı (Microsoft 365 limitleri)
- **Session Timeout**: Varsayılan 600 saniye (ayarlanabilir)
- **OTP Timeout**: Varsayılan 120 saniye (ayarlanabilir)
- **Email Age**: Maksimum 300 saniye (ayarlanabilir)

## Hata Yönetimi

### IMAP Bağlantı Hatası

```python
try:
    manager.start()
except Exception as e:
    logger.error(f"IMAP connection failed: {e}")
    # Fallback to manual OTP input
```

### Session Timeout

```python
otp = manager.wait_for_otp(session_id, timeout=120)
if not otp:
    logger.warning(f"OTP timeout for session {session_id}")
    # Handle timeout (retry, manual input, etc.)
```

### OTP Extraction Failure

OTP Manager, regex pattern'leri kullanarak OTP çıkarır. Çıkarma başarısız olursa:

```python
# Custom pattern ekle
custom_patterns = [
    r"Your PIN is (\d{4})",
    r"Security code: (\d{8})"
]

manager = OTPManager(
    email="...",
    app_password="...",
    custom_patterns=custom_patterns
)
```

## Güvenlik

### App Password Yönetimi

- **Asla** app password'ü kod içinde hardcode etmeyin
- `.env` dosyasını `.gitignore`'a ekleyin
- Production'da environment variable kullanın
- Düzenli olarak app password'ü rotate edin

### Session Güvenliği

- Session ID'ler UUID v4 kullanılarak oluşturulur
- Session'lar otomatik olarak expire olur
- Thread-safe tasarım race condition'ları önler

## Logging

OTP Manager, `loguru` kullanır:

```python
from loguru import logger

# Loguru handles log levels via environment or logger.add()
# Default log level can be controlled by environment variable
# LOGURU_LEVEL=DEBUG for debug mode
```

## Sorun Giderme

### Problem: IMAP bağlantı hatası

**Çözüm:**
1. App password'ün doğru olduğundan emin olun
2. Microsoft 365 hesabınızda IMAP'in aktif olduğunu kontrol edin
3. Firewall/proxy ayarlarını kontrol edin

### Problem: OTP alınamıyor

**Çözüm:**
1. Target email adresinin doğru olduğunu kontrol edin
2. Email'in catch-all mailbox'a yönlendirildiğini doğrulayın
3. Email header'larını (To, Delivered-To, X-Original-To) kontrol edin

### Problem: Session timeout

**Çözüm:**
1. `session_timeout_seconds` parametresini artırın
2. Session'ı düzenli olarak refresh edin
3. Cleanup scheduler'ı ayarlayın

## Test

Test'leri çalıştırın:

```bash
# Tüm OTP Manager testleri
pytest tests/test_otp_manager.py -v

# Sadece unit testler
pytest tests/test_otp_manager.py -v -m unit

# Coverage ile
pytest tests/test_otp_manager.py --cov=src.services.otp_manager
```

## Lisans

Bu modül VFS-Bot1 projesinin bir parçasıdır ve aynı lisans altındadır.
