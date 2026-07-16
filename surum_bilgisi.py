"""İhalex sürüm kimliği ve yönetim panelinde gösterilen kalıcı sürüm geçmişi."""

from __future__ import annotations


SURUM_V1_1_0 = {
    "surum_kodu": "v1.1.0",
    "surum_adi": "Şeffaf Analiz Çekirdeği",
    "yayin_tarihi": "2026-07-16",
    "analiz_motoru_surumu": "1.1.5",
    "git_etiketi": "v1.1.0-seffaf-analiz-cekirdegi",
    "aciklama": (
        "Okul bazlı belge ayrıştırma, zorunlu okul adı/türü ve öğrenci verisi, "
        "aylık-yıllık muhammen ayrımı, okul türü harcama katsayısı, şeffaf "
        "matematik dökümü, 120 saatlik dinamik çalışan maliyeti, yüzde 25 net "
        "kâr hedefi, aktif ilan önceliği, manuel yönetici düzeltmeleri, kalıcı "
        "arşiv ve resmî bağlantılı MEB kaynak denetim ekranı."
    ),
}


GUNCEL_SURUM = {
    "surum_kodu": "v1.1.1",
    "surum_adi": "Marka Arayüzü",
    "yayin_tarihi": "2026-07-16",
    "analiz_motoru_surumu": "1.1.9",
    "git_etiketi": "v1.1.1-marka-arayuzu",
    "aciklama": (
        "İHALEX marka bannerı ve mobil görünümü sadeleştirildi; tek fontlu logo, "
        "kırmızı İ noktası ve X kullanıldı. İhale sonucu kira tahmini, yatırım "
        "skoru ve okul türüne göre daha temkinli kantin kullanım oranları "
        "güncellendi. Eski worker sürümlerinin yeni analiz sonuçlarını geri "
        "almasını önleyen koruma eklendi."
    ),
}


SURUM_GECMISI = (GUNCEL_SURUM, SURUM_V1_1_0)
