# İhalex mobil kabuğu

Android projesi Capacitor 8 ile hazırlanmıştır. Mobil uygulama, yalnızca HTTPS ile
sunulan İhalex web adresini `?embedded=1` görünümünde açar. Resmî MEB bağlantıları
uygulamanın güvenilir alan listesine eklenmez; dış bağlantı olarak ele alınır.

## Web adresini bağlama

PowerShell oturumunda herkese açık HTTPS adresini tanımlayın:

```powershell
$env:IHALEX_WEB_URL = "https://ornek-ihalex-adresi"
pnpm sync android
```

`IHALEX_WEB_URL` değeri HTTP olursa yapılandırma güvenlik gereği derlenmez. Android
projesi `android/` klasöründedir. Mağaza sürümünden önce uygulama imzalama, alan adı
doğrulama, gizlilik metni ve güvenlik testi ayrıca tamamlanmalıdır.
