"""Okul kantinleri için açıklanabilir çalışan ihtiyacı ve işçilik maliyeti servisi."""

from __future__ import annotations

import math
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping


PERSONEL_MOTOR_SURUMU = "1.0.0"

OKUL_TIPI_PERSONEL_KATSAYILARI = {
    "ilkokul": 0.80,
    "ortaokul": 1.00,
    "lise": 1.20,
    "meslek_lisesi": 1.20,
    "karma": 1.00,
}

# 2026 resmî brüt asgari ücret ve indirimsiz işveren prim oranları.
VARSAYILAN_PERSONEL_PARAMETRELERI = {
    "ogrenci_basina_calisan": 300,
    "asgari_ucret": 33_030.00,
    "net_asgari_ucret": 28_075.50,
    "brut_maas": 33_030.00,
    "aylik_calisma_saati": 120.0,
    "tam_zamanli_aylik_saat": 225.0,
    "sgk_isveren_orani": 0.2175,
    "issizlik_isveren_orani": 0.02,
    "yemek_maliyeti": 0.0,
    "yol_maliyeti": 0.0,
    "diger_yan_haklar": 0.0,
    "otomatik_personel_hesapla": True,
    "manuel_calisan_sayisi": None,
}


class PersonelMaliyetHatasi(ValueError):
    """Personel hesabı girdileri geçersiz olduğunda oluşur."""


def _para_yuvarla(deger: int | float) -> float:
    return float(Decimal(str(deger)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _sayi(deger: object, alan: str, *, pozitif: bool = False) -> float:
    try:
        sayi = float(deger)
    except (TypeError, ValueError) as hata:
        raise PersonelMaliyetHatasi(f"{alan} sayısal olmalıdır") from hata
    if not math.isfinite(sayi) or sayi < (0.000001 if pozitif else 0):
        raise PersonelMaliyetHatasi(f"{alan} geçerli bir değer olmalıdır")
    return sayi


def _oran(deger: object, alan: str) -> float:
    oran = _sayi(deger, alan)
    if oran > 1:
        raise PersonelMaliyetHatasi(f"{alan} 0 ile 1 arasında olmalıdır")
    return oran


def _okul_tipi_anahtari(okul_tipi: object) -> str:
    metin = unicodedata.normalize(
        "NFKD", str(okul_tipi or "").strip().casefold()
    ).replace("ı", "i")
    metin = "".join(harf for harf in metin if not unicodedata.combining(harf))
    if "meslek lises" in metin or "mesleki ve teknik" in metin:
        return "meslek_lisesi"
    if "ilkokul" in metin:
        return "ilkokul"
    if "ortaokul" in metin:
        return "ortaokul"
    if "lise" in metin:
        return "lise"
    if "karma" in metin:
        return "karma"
    anahtar = metin.replace(" ", "_")
    if anahtar in OKUL_TIPI_PERSONEL_KATSAYILARI:
        return anahtar
    raise PersonelMaliyetHatasi("Okul tipi personel hesabı için doğrulanmalıdır")


def baz_personel_sayisi_hesapla(
    ogrenci_sayisi: int | float,
    ogrenci_basina_calisan: int | float = 300,
) -> int:
    ogrenci = _sayi(ogrenci_sayisi, "Öğrenci sayısı", pozitif=True)
    kapasite = _sayi(
        ogrenci_basina_calisan, "Çalışan başına öğrenci", pozitif=True
    )
    return max(1, math.ceil(ogrenci / kapasite))


def onerilen_calisan_sayisi_hesapla(
    ogrenci_sayisi: int | float,
    okul_tipi: object,
    *,
    ogrenci_basina_calisan: int | float = 300,
    okul_tipi_katsayisi: float | None = None,
) -> dict[str, object]:
    tip = _okul_tipi_anahtari(okul_tipi)
    katsayi = _sayi(
        OKUL_TIPI_PERSONEL_KATSAYILARI[tip]
        if okul_tipi_katsayisi is None else okul_tipi_katsayisi,
        "Okul tipi katsayısı",
        pozitif=True,
    )
    baz = baz_personel_sayisi_hesapla(ogrenci_sayisi, ogrenci_basina_calisan)
    onerilen = max(1, math.ceil(baz * katsayi))
    return {
        "ogrenci_sayisi": int(float(ogrenci_sayisi)),
        "ogrenci_basina_calisan": float(ogrenci_basina_calisan),
        "okul_tipi": tip,
        "okul_tipi_katsayisi": round(katsayi, 4),
        "baz_personel_sayisi": baz,
        "onerilen_calisan_sayisi": onerilen,
    }


def kisi_basi_personel_maliyeti_hesapla(
    *,
    asgari_ucret: int | float = 33_030.00,
    net_asgari_ucret: int | float = 28_075.50,
    brut_maas: int | float = 33_030.00,
    aylik_calisma_saati: int | float = 120,
    tam_zamanli_aylik_saat: int | float = 225,
    sgk_isveren_orani: float = 0.2175,
    issizlik_isveren_orani: float = 0.02,
    yemek_maliyeti: int | float = 0,
    yol_maliyeti: int | float = 0,
    diger_yan_haklar: int | float = 0,
) -> dict[str, float]:
    asgari = _sayi(asgari_ucret, "Asgari ücret", pozitif=True)
    net_asgari = _sayi(net_asgari_ucret, "Net asgari ücret", pozitif=True)
    tam_brut = _sayi(brut_maas, "Tam zamanlı brüt maaş", pozitif=True)
    if tam_brut < asgari:
        raise PersonelMaliyetHatasi("Brüt maaş asgari ücretin altında olamaz")
    calisma_saati = _sayi(
        aylik_calisma_saati, "Aylık çalışma saati", pozitif=True
    )
    tam_saat = _sayi(
        tam_zamanli_aylik_saat, "Tam zamanlı aylık saat", pozitif=True
    )
    if calisma_saati > tam_saat:
        raise PersonelMaliyetHatasi(
            "Part-time çalışma saati tam zamanlı aylık saati aşamaz"
        )
    calisma_orani = calisma_saati / tam_saat
    brut = _para_yuvarla(tam_brut * calisma_orani)
    tahmini_net = _para_yuvarla(
        net_asgari * calisma_orani * (tam_brut / asgari)
    )
    sgk_orani = _oran(sgk_isveren_orani, "SGK işveren oranı")
    issizlik_orani = _oran(
        issizlik_isveren_orani, "İşsizlik sigortası işveren oranı"
    )
    yemek = _sayi(yemek_maliyeti, "Yemek maliyeti")
    yol = _sayi(yol_maliyeti, "Yol maliyeti")
    diger = _sayi(diger_yan_haklar, "Diğer yan haklar")
    sgk = _para_yuvarla(brut * sgk_orani)
    issizlik = _para_yuvarla(brut * issizlik_orani)
    yan_hak = _para_yuvarla(yemek + yol + diger)
    net_maas_sgk = _para_yuvarla(tahmini_net + sgk)
    kisi_basi = _para_yuvarla(brut + sgk + issizlik + yan_hak)
    return {
        "asgari_ucret": round(asgari, 2),
        "net_asgari_ucret": round(net_asgari, 2),
        "tam_zamanli_brut_maas": round(tam_brut, 2),
        "aylik_calisma_saati": round(calisma_saati, 2),
        "tam_zamanli_aylik_saat": round(tam_saat, 2),
        "calisma_orani": round(calisma_orani, 6),
        "brut_maas": brut,
        "tahmini_net_maas": tahmini_net,
        "sgk_isveren_orani": round(sgk_orani, 6),
        "sgk_maliyeti": sgk,
        "issizlik_isveren_orani": round(issizlik_orani, 6),
        "issizlik_sigortasi": issizlik,
        "yemek_maliyeti": round(yemek, 2),
        "yol_maliyeti": round(yol, 2),
        "diger_yan_haklar": round(diger, 2),
        "yan_hak_maliyeti": yan_hak,
        "net_maas_sgk_toplami": net_maas_sgk,
        "kisi_basi_personel_maliyeti": kisi_basi,
    }


def personel_maliyet_raporu_olustur(
    ogrenci_sayisi: int | float,
    okul_tipi: object,
    parametreler: Mapping[str, object] | None = None,
) -> dict[str, object]:
    ayarlar = {**VARSAYILAN_PERSONEL_PARAMETRELERI, **dict(parametreler or {})}
    ihtiyac = onerilen_calisan_sayisi_hesapla(
        ogrenci_sayisi,
        okul_tipi,
        ogrenci_basina_calisan=ayarlar["ogrenci_basina_calisan"],
        okul_tipi_katsayisi=ayarlar.get("okul_tipi_katsayisi"),
    )
    maliyet = kisi_basi_personel_maliyeti_hesapla(
        asgari_ucret=ayarlar["asgari_ucret"],
        net_asgari_ucret=ayarlar["net_asgari_ucret"],
        brut_maas=ayarlar["brut_maas"],
        aylik_calisma_saati=ayarlar["aylik_calisma_saati"],
        tam_zamanli_aylik_saat=ayarlar["tam_zamanli_aylik_saat"],
        sgk_isveren_orani=ayarlar["sgk_isveren_orani"],
        issizlik_isveren_orani=ayarlar["issizlik_isveren_orani"],
        yemek_maliyeti=ayarlar["yemek_maliyeti"],
        yol_maliyeti=ayarlar["yol_maliyeti"],
        diger_yan_haklar=ayarlar["diger_yan_haklar"],
    )
    otomatik = bool(ayarlar["otomatik_personel_hesapla"])
    if otomatik:
        kullanilan = int(ihtiyac["onerilen_calisan_sayisi"])
        mod = "otomatik"
    else:
        manuel = ayarlar.get("manuel_calisan_sayisi")
        kullanilan = int(_sayi(manuel, "Manuel çalışan sayısı", pozitif=True))
        mod = "manuel"
    toplam = _para_yuvarla(
        kullanilan * float(maliyet["kisi_basi_personel_maliyeti"])
    )
    return {
        "personel_motor_surumu": PERSONEL_MOTOR_SURUMU,
        **ihtiyac,
        **maliyet,
        "personel_hesaplama_modu": mod,
        "otomatik_personel_hesapla": otomatik,
        "manuel_calisan_sayisi": None if otomatik else kullanilan,
        "kullanilan_calisan_sayisi": kullanilan,
        "toplam_personel_gideri": toplam,
        "gelecek_optimizasyon_alanlari": [
            "ogrenci_gunluk_alisveris_orani", "ortalama_sepet_tutari",
            "teneffus_yogunlugu", "kantin_alani_m2", "urun_cesit_sayisi",
            "okul_giris_cikis_saatleri", "vardiya_sistemi",
        ],
    }


__all__ = [
    "PERSONEL_MOTOR_SURUMU", "PersonelMaliyetHatasi",
    "OKUL_TIPI_PERSONEL_KATSAYILARI", "VARSAYILAN_PERSONEL_PARAMETRELERI",
    "baz_personel_sayisi_hesapla", "onerilen_calisan_sayisi_hesapla",
    "kisi_basi_personel_maliyeti_hesapla", "personel_maliyet_raporu_olustur",
]
