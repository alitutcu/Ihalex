"""İhalex sürüm kimliği ve yönetim panelinde gösterilen kalıcı sürüm geçmişi."""

from __future__ import annotations


GUNCEL_SURUM = {
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


SURUM_GECMISI = (GUNCEL_SURUM,)
