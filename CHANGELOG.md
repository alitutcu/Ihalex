# İhalex Sürüm Geçmişi

## v1.1.1 — Marka Arayüzü (2026-07-16)

- İHALEX bannerı sadeleştirildi; logo tek fontta birleştirildi ve yalnızca
  `İ` noktası ile `X` kırmızı olarak korundu.
- Bannerın mobil ve masaüstü boşlukları dengelenerek marka görünümü yenilendi.
- Muhammen bedelin ihale başlangıç değeri olduğu dikkate alınarak tahmini ihale
  sonucu kira modeli yatırım skoruna ve risk hesabına bağlandı.
- Okul türüne göre kantin kullanım oranları daha temkinli değerlerle güncellendi.
- Eski worker sürümlerinin güncel analiz motoru sonuçlarını geri almasını
  engelleyen veritabanı koruması eklendi.
- Analiz motoru sürümü `1.1.9` olarak kaydedildi.

## v1.1.0 — Şeffaf Analiz Çekirdeği (2026-07-16)

- Toplu MEB ilanlarındaki ek belgeler okul bazında ayrı kayıtlara bağlandı.
- Okul adı, okul türü, öğrenci sayısı ve aylık muhammen bedel analiz için zorunlu yapıldı.
- Aylık ve yıllık muhammen bedeller ayrı saklanmaya başlandı; finansal analiz aylık değeri kullanıyor.
- İlkokul, ortaokul ve lise öğrenci harcama kapasitesi katsayıları eklendi.
- AI analiz kartlarında aktif ilanlar önceliklendirildi; okul adları özel
  karakterlerden arındırılarak tek kuralla normalleştirildi.
- 120 saatlik part-time çalışan modeli, öğrenci kademeleri ve okul türü
  katsayısıyla dinamik personel maliyeti hesaplaması eklendi.
- Aylık/yıllık ciro, 180 fiilî eğitim günü ve yüzde 25 hedef net kâr
  varsayımları tek analiz motorunda birleştirildi.
- Bölgesel veri katmanı nötr katsayılarla ve gelecekte resmî veri kaynağı
  bağlanabilecek şekilde eklendi.
- Ciro, gider, net kâr, risk, yatırım skoru ve maksimum teklif matematiği açıklanabilir hâle getirildi.
- Belge verisini değiştirmeyen, geçmişi tutulan yönetici düzeltme katmanı eklendi.
- İlan, ham duyuru, belge ve analiz kayıtları için kalıcı saklama politikası uygulandı.
- Yönetim paneline MEB kaynak listesi, taranan okul verileri, resmî belge
  bağlantılı zorunlu alan denetimi, AI hesaplama ve sürüm geçmişi eklendi.
