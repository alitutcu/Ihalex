"""Kantin ve benzeri lokasyonlar için açıklanabilir yatırım analiz motoru.

Motor, belge verilerini ve kullanıcı tarafından değiştirilebilir varsayımları
birbirinden ayırır. Sonuçlar tahmindir; kesin gelir veya yatırım tavsiyesi değildir.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from typing import Mapping
import json
import math
import unicodedata

from personel_maliyet_servisi import (
    PersonelMaliyetHatasi,
    VARSAYILAN_PERSONEL_PARAMETRELERI,
    personel_maliyet_raporu_olustur,
)
from analiz_ogrenme_servisi import ogrenme_ornegi_kaydet
from okul_adi_servisi import okul_adi_temizle


MOTOR_SURUMU = "1.1.5"
OKUL_TURU_HARCAMA_KATSAYILARI = {
    "ilkokul": 0.80,
    "ortaokul": 1.00,
    "lise": 1.20,
    "meslek_lisesi": 1.20,
    "karma": 1.00,
}
OKUL_TURU_DONUSUM_ARALIKLARI = {
    "ilkokul": (0.30, 0.50),
    "ortaokul": (0.50, 0.70),
    "lise": (0.60, 0.85),
    "meslek_lisesi": (0.70, 0.90),
    "karma": (0.50, 0.70),
}
OKUL_TURU_DONUSUM_ORANLARI = {
    tur: round((aralik[0] + aralik[1]) / 2, 4)
    for tur, aralik in OKUL_TURU_DONUSUM_ARALIKLARI.items()
}
# Eski modül kullanıcıları için geriye dönük ad.
OKUL_TIPI_KATSAYILARI = OKUL_TURU_HARCAMA_KATSAYILARI
VARSAYILAN_PARAMETRELER = {
    **VARSAYILAN_PERSONEL_PARAMETRELERI,
    "ogrenci_donusum_orani": 0.55,
    "personel_donusum_orani": 0.65,
    # Ortaokul bazıdır: İlkokul 80, Ortaokul 100, Lise 120 TL/gün.
    "ortalama_ogrenci_harcamasi": 100.0,
    "ortalama_personel_harcamasi": 65.0,
    "aylik_okul_gunu": 20,
    # Hafta sonu, ara/sömestr/yaz tatili ve resmî tatiller dışarıda bırakılır.
    "yillik_egitim_gunu": 180,
    "urun_maliyet_orani": 0.45,
    "fire_orani": 0.03,
    "aylik_calisan_gideri": 45_000.0,
    "aylik_elektrik_su_gideri": 10_000.0,
    "aylik_diger_gider": 5_000.0,
    "hedef_net_kar_orani": 0.25,
    "azami_kira_ciro_orani": 0.20,
    "ekonomik_katsayi": 1.0,
    "gelir_katsayi": 1.0,
    "ticari_hareketlilik_katsayi": 1.0,
}


class AnalizVerisiHatasi(ValueError):
    """Yatırım analizi için zorunlu veya geçerli veri bulunmadığında oluşur."""


def _sayi(deger: object, alan: str, *, sifir_olabilir: bool = True) -> float:
    try:
        sayi = float(deger)
    except (TypeError, ValueError) as hata:
        raise AnalizVerisiHatasi(f"{alan} sayısal olmalıdır") from hata
    if not math.isfinite(sayi):
        raise AnalizVerisiHatasi(f"{alan} sonlu bir sayı olmalıdır")
    alt_sinir = 0 if sifir_olabilir else 0.000001
    if sayi < alt_sinir:
        raise AnalizVerisiHatasi(f"{alan} geçerli bir pozitif değer olmalıdır")
    return sayi


def _oran(deger: object, alan: str) -> float:
    oran = _sayi(deger, alan)
    if oran > 1:
        raise AnalizVerisiHatasi(f"{alan} 0 ile 1 arasında olmalıdır")
    return oran


def _sinirla(deger: float, alt: float = 0, ust: float = 100) -> float:
    return max(alt, min(ust, deger))


def _eksik_mi(deger: object) -> bool:
    if deger is None or str(deger).strip() == "":
        return True
    try:
        return not math.isfinite(float(deger))
    except (TypeError, ValueError):
        return False


def okul_tipi_belirle(okul_adi: object) -> str:
    metin = unicodedata.normalize(
        "NFKD", str(okul_adi or "").casefold()
    ).replace("ı", "i")
    metin = "".join(harf for harf in metin if not unicodedata.combining(harf))
    meslek_lisesi = (
        "meslek lises" in metin or "mesleki ve teknik" in metin
        or "mesleki teknik" in metin
    )
    bulunan = [
        tur for tur, anahtar in (
            ("ilkokul", "ilkokul"), ("ortaokul", "ortaokul")
        ) if anahtar in metin
    ]
    if meslek_lisesi:
        bulunan.append("meslek_lisesi")
    elif "lise" in metin:
        bulunan.append("lise")
    return bulunan[0] if len(bulunan) == 1 else ("karma" if bulunan else "bilinmiyor")


def _okul_turunu_normalize_et(okul_turu: object) -> str:
    tur = unicodedata.normalize(
        "NFKD", str(okul_turu or "").strip().casefold()
    ).replace("ı", "i")
    tur = "".join(harf for harf in tur if not unicodedata.combining(harf))
    tur_anahtari = tur.replace(" ", "_")
    if tur_anahtari in OKUL_TURU_HARCAMA_KATSAYILARI:
        return tur_anahtari
    belirlenen = okul_tipi_belirle(tur)
    if belirlenen == "bilinmiyor":
        raise AnalizVerisiHatasi("Okul türü doğrulanmalıdır")
    return belirlenen


def ciro_hesapla(
    ogrenci_sayisi: int | float,
    personel_sayisi: int | float = 0,
    *,
    okul_tipi: str = "bilinmiyor",
    ogrenci_donusum_orani: float = 0.55,
    personel_donusum_orani: float = 0.65,
    ortalama_ogrenci_harcamasi: float = 100.0,
    ortalama_personel_harcamasi: float = 65.0,
    okul_gunu: int = 20,
    yillik_egitim_gunu: int = 180,
    ekonomik_katsayi: float = 1.0,
    gelir_katsayi: float = 1.0,
    ticari_hareketlilik_katsayi: float = 1.0,
) -> dict[str, float]:
    ogrenci = _sayi(ogrenci_sayisi, "Öğrenci sayısı", sifir_olabilir=False)
    personel = _sayi(personel_sayisi, "Personel sayısı")
    ogrenci_orani = _oran(ogrenci_donusum_orani, "Öğrenci dönüşüm oranı")
    personel_orani = _oran(personel_donusum_orani, "Personel dönüşüm oranı")
    ogrenci_harcamasi = _sayi(
        ortalama_ogrenci_harcamasi, "Ortalama öğrenci harcaması", sifir_olabilir=False
    )
    personel_harcamasi = _sayi(
        ortalama_personel_harcamasi, "Ortalama personel harcaması", sifir_olabilir=False
    )
    gun = _sayi(okul_gunu, "Aylık okul günü", sifir_olabilir=False)
    yillik_gun = _sayi(
        yillik_egitim_gunu, "Yıllık eğitim günü", sifir_olabilir=False
    )
    if yillik_gun > 366:
        raise AnalizVerisiHatasi("Yıllık eğitim günü 366'yı aşamaz")
    ekonomik = _sayi(
        ekonomik_katsayi, "Ekonomik katsayı", sifir_olabilir=False
    )
    gelir = _sayi(
        gelir_katsayi, "Gelir katsayısı", sifir_olabilir=False
    )
    ticari = _sayi(
        ticari_hareketlilik_katsayi,
        "Ticari hareketlilik katsayısı",
        sifir_olabilir=False,
    )
    tip = _okul_turunu_normalize_et(okul_tipi)
    okul_katsayisi = OKUL_TURU_HARCAMA_KATSAYILARI[tip]

    gunluk_ogrenci = ogrenci * ogrenci_orani
    gunluk_personel = personel * personel_orani
    bolge_katsayisi = ekonomik * gelir * ticari
    gunluk_ogrenci_cirosu = (
        gunluk_ogrenci * ogrenci_harcamasi * okul_katsayisi * bolge_katsayisi
    )
    gunluk_personel_cirosu = gunluk_personel * personel_harcamasi * bolge_katsayisi
    gunluk_ciro = gunluk_ogrenci_cirosu + gunluk_personel_cirosu
    return {
        "gunluk_ogrenci_musteri": round(gunluk_ogrenci, 2),
        "gunluk_personel_musteri": round(gunluk_personel, 2),
        "gunluk_musteri": round(gunluk_ogrenci + gunluk_personel, 2),
        "tahmini_gunluk_ogrenci_cirosu": round(gunluk_ogrenci_cirosu, 2),
        "tahmini_gunluk_personel_cirosu": round(gunluk_personel_cirosu, 2),
        "tahmini_gunluk_ciro": round(gunluk_ciro, 2),
        "tahmini_aylik_ciro": round(gunluk_ciro * gun, 2),
        "tahmini_yillik_ciro": round(gunluk_ciro * yillik_gun, 2),
        "yillik_egitim_gunu": int(yillik_gun),
        "okul_turu": tip,
        "ogrenci_harcama_katsayisi": okul_katsayisi,
        "okul_tipi_katsayisi": okul_katsayisi,
        "katsayili_ogrenci_harcamasi": round(ogrenci_harcamasi * okul_katsayisi, 2),
    }


def gider_hesapla(
    aylik_ciro: int | float,
    aylik_kira: int | float,
    *,
    urun_maliyet_orani: float = 0.45,
    aylik_calisan_gideri: float = 45_000.0,
    aylik_elektrik_su_gideri: float = 10_000.0,
    fire_orani: float = 0.03,
    aylik_diger_gider: float = 5_000.0,
) -> dict[str, float]:
    ciro = _sayi(aylik_ciro, "Aylık ciro")
    kira = _sayi(aylik_kira, "Aylık kira")
    urun_orani = _oran(urun_maliyet_orani, "Ürün maliyet oranı")
    fire = _oran(fire_orani, "Fire oranı")
    calisan = _sayi(aylik_calisan_gideri, "Çalışan gideri")
    enerji = _sayi(aylik_elektrik_su_gideri, "Elektrik/su gideri")
    diger = _sayi(aylik_diger_gider, "Diğer gider")
    urun = ciro * urun_orani
    fire_tutari = ciro * fire
    toplam = urun + fire_tutari + calisan + enerji + diger + kira
    return {
        "urun_maliyeti": round(urun, 2),
        "personel_gideri": round(calisan, 2),
        "elektrik_su_gideri": round(enerji, 2),
        "fire_gideri": round(fire_tutari, 2),
        "diger_gider": round(diger, 2),
        "kira_gideri": round(kira, 2),
        "kira_haric_gider": round(toplam - kira, 2),
        "toplam_gider": round(toplam, 2),
    }


def net_kar_hesapla(aylik_ciro: int | float, toplam_gider: int | float) -> float:
    return round(
        _sayi(aylik_ciro, "Aylık ciro") - _sayi(toplam_gider, "Toplam gider"),
        2,
    )


def kira_orani_hesapla(aylik_kira: int | float, aylik_ciro: int | float) -> float:
    ciro = _sayi(aylik_ciro, "Aylık ciro", sifir_olabilir=False)
    kira = _sayi(aylik_kira, "Aylık kira")
    return round(kira / ciro * 100, 2)


def risk_skoru_hesapla(
    *,
    ogrenci_sayisi: int | float,
    kira_ciro_orani: float,
    net_kar_marji: float,
    ogrenci_donusum_orani: float,
    ekonomik_katsayi: float = 1.0,
    gelir_katsayi: float = 1.0,
    ticari_hareketlilik_katsayi: float = 1.0,
    eksik_kritik_veri: int = 0,
) -> dict[str, object]:
    ogrenci = _sayi(ogrenci_sayisi, "Öğrenci sayısı", sifir_olabilir=False)
    kira_orani = _sayi(kira_ciro_orani, "Kira/ciro oranı")
    donusum = _oran(ogrenci_donusum_orani, "Öğrenci dönüşüm oranı")
    ekonomik = _sayi(ekonomik_katsayi, "Ekonomik katsayı")
    gelir = _sayi(gelir_katsayi, "Gelir katsayısı")
    ticari = _sayi(ticari_hareketlilik_katsayi, "Ticari hareketlilik")

    bilesenler = {
        "taban_risk": 8.0,
        "ogrenci_riski": 15 if ogrenci < 200 else (8 if ogrenci < 400 else 0),
        "kira_ciro_riski": 0 if kira_orani <= 10 else (10 if kira_orani <= 15 else (
        22 if kira_orani <= 20 else (42 if kira_orani <= 30 else 65)
        )),
        "kar_marji_riski": 0 if net_kar_marji >= 15 else (10 if net_kar_marji >= 5 else (
        25 if net_kar_marji >= 0 else 45
        )),
        "donusum_varsayimi_riski": 8 if donusum > 0.70 else 0,
        "ekonomik_bolge_riski": max(0.0, (1.0 - ekonomik) * 30),
        "gelir_bolge_riski": max(0.0, (1.0 - gelir) * 30),
        "ticari_hareketlilik_riski": max(0.0, (1.0 - ticari) * 30),
        "eksik_veri_riski": max(0, int(eksik_kritik_veri)) * 8,
    }
    risk = sum(bilesenler.values())
    risk = round(_sinirla(risk), 2)
    if risk < 30:
        seviye = "Düşük"
    elif risk < 55:
        seviye = "Orta"
    elif risk < 75:
        seviye = "Yüksek"
    else:
        seviye = "Çok yüksek"
    return {"risk_skoru": risk, "risk": seviye, "bilesenler": bilesenler}


def yatirim_skoru_detayi_hesapla(
    *,
    net_kar_marji: float,
    kira_ciro_orani: float,
    risk_skoru: float,
    ogrenci_sayisi: int | float,
    ekonomik_katsayi: float = 1.0,
    gelir_katsayi: float = 1.0,
    ticari_hareketlilik_katsayi: float = 1.0,
) -> dict[str, object]:
    ogrenci = _sayi(ogrenci_sayisi, "Öğrenci sayısı", sifir_olabilir=False)
    bolge_ortalamasi = (
        float(ekonomik_katsayi) + float(gelir_katsayi)
        + float(ticari_hareketlilik_katsayi)
    ) / 3
    bilesenler = {
        "taban_puan": 50.0,
        "kar_marji_puani": 25 if net_kar_marji >= 25 else (
            18 if net_kar_marji >= 15 else (
                8 if net_kar_marji >= 8 else (0 if net_kar_marji >= 0 else -25)
            )
        ),
        "kira_ciro_puani": 15 if kira_ciro_orani <= 10 else (
            10 if kira_ciro_orani <= 15 else (3 if kira_ciro_orani <= 20 else -15)
        ),
        "ogrenci_puani": 10 if ogrenci >= 700 else (
            5 if ogrenci >= 400 else (-10 if ogrenci < 200 else 0)
        ),
        "bolge_puani": _sinirla((bolge_ortalamasi - 1) * 20, -10, 10),
        "risk_kesintisi": -float(risk_skoru) * 0.35,
    }
    ham_skor = sum(bilesenler.values())
    return {
        "yatirim_skoru": int(round(_sinirla(ham_skor))),
        "ham_skor": round(ham_skor, 2),
        "bilesenler": bilesenler,
        "bolge_ortalamasi": round(bolge_ortalamasi, 4),
    }


def yatirim_skoru_hesapla(
    *,
    net_kar_marji: float,
    kira_ciro_orani: float,
    risk_skoru: float,
    ogrenci_sayisi: int | float,
    ekonomik_katsayi: float = 1.0,
    gelir_katsayi: float = 1.0,
    ticari_hareketlilik_katsayi: float = 1.0,
) -> int:
    return int(yatirim_skoru_detayi_hesapla(
        net_kar_marji=net_kar_marji,
        kira_ciro_orani=kira_ciro_orani,
        risk_skoru=risk_skoru,
        ogrenci_sayisi=ogrenci_sayisi,
        ekonomik_katsayi=ekonomik_katsayi,
        gelir_katsayi=gelir_katsayi,
        ticari_hareketlilik_katsayi=ticari_hareketlilik_katsayi,
    )["yatirim_skoru"])


def maksimum_teklif_hesapla(
    aylik_ciro: int | float,
    kira_haric_gider: int | float,
    *,
    hedef_net_kar_orani: float = 0.25,
    azami_kira_ciro_orani: float = 0.20,
) -> float:
    ciro = _sayi(aylik_ciro, "Aylık ciro", sifir_olabilir=False)
    gider = _sayi(kira_haric_gider, "Kira hariç gider")
    hedef = _oran(hedef_net_kar_orani, "Hedef net kâr oranı")
    kira_tavani = _oran(azami_kira_ciro_orani, "Azami kira/ciro oranı")
    kar_korumali_tavan = ciro - gider - ciro * hedef
    oran_tavani = ciro * kira_tavani
    return round(max(0.0, min(kar_korumali_tavan, oran_tavani)), 2)


def _yorum_olustur(
    yatirim_skoru: int,
    risk: str,
    kira_orani: float,
    net_kar: float,
) -> str:
    if yatirim_skoru >= 75 and risk == "Düşük" and net_kar > 0:
        temel = "Bu kantin, girilen varsayımlar altında ekonomik olarak uygun görünüyor."
    elif yatirim_skoru >= 55 and net_kar > 0:
        temel = "Potansiyel olumlu; teklif öncesinde maliyet ve müşteri varsayımları doğrulanmalı."
    else:
        temel = "Mevcut varsayımlarla yatırım riski yüksek; kira ve işletme giderleri yeniden incelenmeli."
    return f"{temel} Tahmini kira/ciro oranı %{kira_orani:.1f}."


def analiz_raporu_olustur(
    ilan: Mapping[str, object],
    parametreler: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """İlan girdisinden JSON/SQLite uyumlu tam yatırım raporu üretir."""
    from bolge_veri_servisi import bolge_verisi_getir

    bolge = bolge_verisi_getir(
        str(ilan.get("il") or "Bilinmeyen"),
        str(ilan.get("ilce") or ""),
    )
    ayarlar = {
        **VARSAYILAN_PARAMETRELER,
        "ekonomik_katsayi": float(bolge["ekonomik_katsayi"]),
        "gelir_katsayi": float(bolge["gelir_katsayi"]),
        "ticari_hareketlilik_katsayi": float(
            bolge["ticari_hareketlilik_katsayi"]
        ),
        **dict(parametreler or {}),
    }
    okul_adi = okul_adi_temizle(ilan.get("okul_adi")) or ""
    if not okul_adi or okul_adi == "Okul adı doğrulanıyor":
        raise AnalizVerisiHatasi("Okul adı doğrulanmalıdır")
    ogrenci = _sayi(ilan.get("ogrenci_sayisi"), "Öğrenci sayısı", sifir_olabilir=False)
    personel_ham = ilan.get("personel_sayisi")
    personel = _sayi(0 if _eksik_mi(personel_ham) else personel_ham, "Personel sayısı")
    aylik_kira = _sayi(
        ilan.get("muhammen_bedel_aylik"),
        "Aylık muhammen kira bedeli",
        sifir_olabilir=False,
    )
    okul_tipi = _okul_turunu_normalize_et(
        ilan.get("okul_turu") or ilan.get("okul_tipi") or okul_tipi_belirle(okul_adi)
    )
    if not parametreler or _eksik_mi(parametreler.get("ogrenci_donusum_orani")):
        ayarlar["ogrenci_donusum_orani"] = OKUL_TURU_DONUSUM_ORANLARI[okul_tipi]
    try:
        personel_maliyet_analizi = personel_maliyet_raporu_olustur(
            ogrenci,
            okul_tipi,
            {
                anahtar: ayarlar[anahtar]
                for anahtar in VARSAYILAN_PERSONEL_PARAMETRELERI
                if anahtar in ayarlar
            },
        )
    except PersonelMaliyetHatasi as hata:
        raise AnalizVerisiHatasi(str(hata)) from hata
    ciro = ciro_hesapla(
        ogrenci,
        personel,
        okul_tipi=okul_tipi,
        ogrenci_donusum_orani=float(ayarlar["ogrenci_donusum_orani"]),
        personel_donusum_orani=float(ayarlar["personel_donusum_orani"]),
        ortalama_ogrenci_harcamasi=float(ayarlar["ortalama_ogrenci_harcamasi"]),
        ortalama_personel_harcamasi=float(ayarlar["ortalama_personel_harcamasi"]),
        okul_gunu=int(ayarlar["aylik_okul_gunu"]),
        yillik_egitim_gunu=int(ayarlar["yillik_egitim_gunu"]),
        ekonomik_katsayi=float(ayarlar["ekonomik_katsayi"]),
        gelir_katsayi=float(ayarlar["gelir_katsayi"]),
        ticari_hareketlilik_katsayi=float(ayarlar["ticari_hareketlilik_katsayi"]),
    )
    gider = gider_hesapla(
        ciro["tahmini_aylik_ciro"],
        aylik_kira,
        urun_maliyet_orani=float(ayarlar["urun_maliyet_orani"]),
        aylik_calisan_gideri=float(
            personel_maliyet_analizi["toplam_personel_gideri"]
        ),
        aylik_elektrik_su_gideri=float(ayarlar["aylik_elektrik_su_gideri"]),
        fire_orani=float(ayarlar["fire_orani"]),
        aylik_diger_gider=float(ayarlar["aylik_diger_gider"]),
    )
    net_kar = net_kar_hesapla(ciro["tahmini_aylik_ciro"], gider["toplam_gider"])
    kira_orani = kira_orani_hesapla(aylik_kira, ciro["tahmini_aylik_ciro"])
    net_marj = round(net_kar / ciro["tahmini_aylik_ciro"] * 100, 2)
    eksik = sum(_eksik_mi(ilan.get(alan)) for alan in (
        "personel_sayisi", "kantin_alani_m2"
    ))
    risk = risk_skoru_hesapla(
        ogrenci_sayisi=ogrenci,
        kira_ciro_orani=kira_orani,
        net_kar_marji=net_marj,
        ogrenci_donusum_orani=float(ayarlar["ogrenci_donusum_orani"]),
        ekonomik_katsayi=float(ayarlar["ekonomik_katsayi"]),
        gelir_katsayi=float(ayarlar["gelir_katsayi"]),
        ticari_hareketlilik_katsayi=float(ayarlar["ticari_hareketlilik_katsayi"]),
        eksik_kritik_veri=eksik,
    )
    yatirim_detayi = yatirim_skoru_detayi_hesapla(
        net_kar_marji=net_marj,
        kira_ciro_orani=kira_orani,
        risk_skoru=float(risk["risk_skoru"]),
        ogrenci_sayisi=ogrenci,
        ekonomik_katsayi=float(ayarlar["ekonomik_katsayi"]),
        gelir_katsayi=float(ayarlar["gelir_katsayi"]),
        ticari_hareketlilik_katsayi=float(ayarlar["ticari_hareketlilik_katsayi"]),
    )
    yatirim_skoru = int(yatirim_detayi["yatirim_skoru"])
    maksimum = maksimum_teklif_hesapla(
        ciro["tahmini_aylik_ciro"],
        gider["kira_haric_gider"],
        hedef_net_kar_orani=float(ayarlar["hedef_net_kar_orani"]),
        azami_kira_ciro_orani=float(ayarlar["azami_kira_ciro_orani"]),
    )
    yorum = _yorum_olustur(yatirim_skoru, str(risk["risk"]), kira_orani, net_kar)
    return {
        "motor_surumu": MOTOR_SURUMU,
        "analiz_tarihi": datetime.now().isoformat(timespec="seconds"),
        "yatirim_skoru": yatirim_skoru,
        "risk": risk["risk"],
        "risk_skoru": risk["risk_skoru"],
        "tahmini_ciro": ciro["tahmini_aylik_ciro"],
        "tahmini_aylik_ciro": ciro["tahmini_aylik_ciro"],
        "tahmini_yillik_ciro": ciro["tahmini_yillik_ciro"],
        "net_kar": net_kar,
        "net_kar_marji": net_marj,
        "kira_orani": kira_orani,
        "maksimum_kira": maksimum,
        "gunluk_musteri": ciro["gunluk_musteri"],
        "onerilen_calisan_sayisi": personel_maliyet_analizi[
            "onerilen_calisan_sayisi"
        ],
        "kullanilan_calisan_sayisi": personel_maliyet_analizi[
            "kullanilan_calisan_sayisi"
        ],
        "toplam_personel_gideri": personel_maliyet_analizi[
            "toplam_personel_gideri"
        ],
        "okul_turu": okul_tipi,
        "ogrenci_harcama_katsayisi": ciro["ogrenci_harcama_katsayisi"],
        "yorum": yorum,
        "ciro_detayi": ciro,
        "gider_detayi": gider,
        "personel_maliyet_analizi": personel_maliyet_analizi,
        "risk_detayi": risk,
        "yatirim_skoru_detayi": yatirim_detayi,
        "maksimum_teklif_detayi": {
            "hedef_net_kar_orani": float(ayarlar["hedef_net_kar_orani"]),
            "kar_korumali_tavan": round(
                ciro["tahmini_aylik_ciro"]
                - gider["kira_haric_gider"]
                - ciro["tahmini_aylik_ciro"]
                * float(ayarlar["hedef_net_kar_orani"]),
                2,
            ),
            "oran_tavani": round(
                ciro["tahmini_aylik_ciro"]
                * float(ayarlar["azami_kira_ciro_orani"]),
                2,
            ),
            "secilen_tavan": maksimum,
        },
        "girdiler": {
            "ogrenci_sayisi": int(ogrenci),
            "personel_sayisi": int(personel),
            "okul_adi": okul_adi,
            "okul_turu": okul_tipi,
            "okul_tipi": okul_tipi,
            "aylik_kira": aylik_kira,
            "muhammen_bedel_aylik": aylik_kira,
            "muhammen_bedel_yillik": float(
                aylik_kira * 9 if _eksik_mi(ilan.get("muhammen_bedel_yillik"))
                else ilan.get("muhammen_bedel_yillik")
            ),
            "il": str(ilan.get("il") or ""),
            "ilce": str(ilan.get("ilce") or ""),
        },
        "varsayimlar": ayarlar,
        "okul_turu_analizi": {
            "okul_turu": okul_tipi,
            "ogrenci_harcama_katsayisi": ciro["ogrenci_harcama_katsayisi"],
            "ogrenci_donusum_orani": float(ayarlar["ogrenci_donusum_orani"]),
            "ogrenci_donusum_araligi": list(
                OKUL_TURU_DONUSUM_ARALIKLARI[okul_tipi]
            ),
            "varsayilan_ogrenci_harcamasi": float(
                ayarlar["ortalama_ogrenci_harcamasi"]
            ),
            "katsayili_ogrenci_harcamasi": ciro["katsayili_ogrenci_harcamasi"],
        },
        "bolgesel_veri": {
            "veri_durumu": bolge["veri_durumu"],
            "ekonomik_katsayi": float(bolge["ekonomik_katsayi"]),
            "gelir_katsayi": float(bolge["gelir_katsayi"]),
            "ticari_hareketlilik_katsayi": float(
                bolge["ticari_hareketlilik_katsayi"]
            ),
            "veri_kaynagi": str(bolge["veri_kaynagi"]),
        },
        "uyari": (
            "Bu rapor belge verileri ve değiştirilebilir varsayımlarla üretilmiş tahmindir; "
            "yatırım tavsiyesi değildir. Muhammen bedel aylık kira kabul edilmiştir."
        ),
    }


def analiz_matematigi_olustur(rapor: Mapping[str, object]) -> list[dict[str, object]]:
    """Kalıcı rapordaki bütün temel matematiği insan tarafından okunur adımlara çevirir."""
    girdi = dict(rapor.get("girdiler", {}))
    varsayim = dict(rapor.get("varsayimlar", {}))
    ciro = dict(rapor.get("ciro_detayi", {}))
    gider = dict(rapor.get("gider_detayi", {}))
    okul = dict(rapor.get("okul_turu_analizi", {}))
    personel_maliyeti = dict(rapor.get("personel_maliyet_analizi", {}))
    adimlar: list[dict[str, object]] = [
        {
            "Aşama": "Günlük öğrenci müşterisi",
            "Formül": "Öğrenci sayısı × öğrenci dönüşüm oranı",
            "Hesap": f"{girdi.get('ogrenci_sayisi', 0)} × {float(varsayim.get('ogrenci_donusum_orani', 0)):.4f}",
            "Sonuç": float(ciro.get("gunluk_ogrenci_musteri", 0)),
        },
        {
            "Aşama": "Günlük personel müşterisi",
            "Formül": "Personel sayısı × personel dönüşüm oranı",
            "Hesap": f"{girdi.get('personel_sayisi', 0)} × {float(varsayim.get('personel_donusum_orani', 0)):.4f}",
            "Sonuç": float(ciro.get("gunluk_personel_musteri", 0)),
        },
        {
            "Aşama": "Katsayılı öğrenci harcaması",
            "Formül": "Baz öğrenci harcaması × okul türü katsayısı",
            "Hesap": (
                f"{float(okul.get('varsayilan_ogrenci_harcamasi', 0)):.2f} × "
                f"{float(okul.get('ogrenci_harcama_katsayisi', 0)):.2f}"
            ),
            "Sonuç": float(okul.get("katsayili_ogrenci_harcamasi", 0)),
        },
        {
            "Aşama": "Günlük toplam ciro",
            "Formül": "Öğrenci cirosu + personel cirosu (bölgesel katsayılar dahil)",
            "Hesap": (
                f"{float(ciro.get('tahmini_gunluk_ogrenci_cirosu', 0)):.2f} + "
                f"{float(ciro.get('tahmini_gunluk_personel_cirosu', 0)):.2f}"
            ),
            "Sonuç": float(ciro.get("tahmini_gunluk_ciro", 0)),
        },
        {
            "Aşama": "Aylık ciro",
            "Formül": "Günlük ciro × aylık okul günü",
            "Hesap": (
                f"{float(ciro.get('tahmini_gunluk_ciro', 0)):.2f} × "
                f"{int(varsayim.get('aylik_okul_gunu', 0))}"
            ),
            "Sonuç": float(ciro.get("tahmini_aylik_ciro", 0)),
        },
        {
            "Aşama": "Yıllık ciro",
            "Formül": "Günlük ciro × yıllık fiilî eğitim günü",
            "Hesap": (
                f"{float(ciro.get('tahmini_gunluk_ciro', 0)):.2f} × "
                f"{int(varsayim.get('yillik_egitim_gunu', 180))}"
            ),
            "Sonuç": float(ciro.get("tahmini_yillik_ciro", 0)),
        },
        {
            "Aşama": "Baz çalışan sayısı",
            "Formül": "CEILING(öğrenci sayısı ÷ kademe kapasitesi)",
            "Hesap": (
                f"CEILING({girdi.get('ogrenci_sayisi', 0)} ÷ "
                f"{float(personel_maliyeti.get('ogrenci_basina_calisan', 300)):.0f})"
            ),
            "Sonuç": int(personel_maliyeti.get("baz_personel_sayisi", 0)),
        },
        {
            "Aşama": "Kullanılan çalışan sayısı",
            "Formül": "CEILING(baz çalışan × okul tipi katsayısı) veya manuel sayı",
            "Hesap": (
                f"{personel_maliyeti.get('baz_personel_sayisi', 0)} × "
                f"{float(personel_maliyeti.get('okul_tipi_katsayisi', 1)):.2f} · "
                f"{personel_maliyeti.get('personel_hesaplama_modu', 'otomatik')}"
            ),
            "Sonuç": int(personel_maliyeti.get("kullanilan_calisan_sayisi", 0)),
        },
        {
            "Aşama": "Kişi başı personel maliyeti",
            "Formül": "Brüt maaş + SGK + işsizlik + yemek + yol + yan hak",
            "Hesap": " + ".join(
                f"{float(personel_maliyeti.get(alan, 0)):.2f}"
                for alan in (
                    "brut_maas", "sgk_maliyeti", "issizlik_sigortasi",
                    "yemek_maliyeti", "yol_maliyeti", "diger_yan_haklar",
                )
            ),
            "Sonuç": float(
                personel_maliyeti.get("kisi_basi_personel_maliyeti", 0)
            ),
        },
        {
            "Aşama": "Toplam personel gideri",
            "Formül": "Kullanılan çalışan × kişi başı personel maliyeti",
            "Hesap": (
                f"{personel_maliyeti.get('kullanilan_calisan_sayisi', 0)} × "
                f"{float(personel_maliyeti.get('kisi_basi_personel_maliyeti', 0)):.2f}"
            ),
            "Sonuç": float(personel_maliyeti.get("toplam_personel_gideri", 0)),
        },
        {
            "Aşama": "Toplam gider",
            "Formül": "Ürün + personel + elektrik/su + fire + diğer + aylık kira",
            "Hesap": " + ".join(
                f"{float(gider.get(alan, 0)):.2f}" for alan in (
                    "urun_maliyeti", "personel_gideri", "elektrik_su_gideri",
                    "fire_gideri", "diger_gider", "kira_gideri",
                )
            ),
            "Sonuç": float(gider.get("toplam_gider", 0)),
        },
        {
            "Aşama": "Net kâr",
            "Formül": "Aylık ciro − toplam gider",
            "Hesap": (
                f"{float(rapor.get('tahmini_ciro', 0)):.2f} − "
                f"{float(gider.get('toplam_gider', 0)):.2f}"
            ),
            "Sonuç": float(rapor.get("net_kar", 0)),
        },
        {
            "Aşama": "Kira / ciro oranı",
            "Formül": "Aylık kira ÷ aylık ciro × 100",
            "Hesap": (
                f"{float(girdi.get('aylik_kira', 0)):.2f} ÷ "
                f"{float(rapor.get('tahmini_ciro', 0)):.2f} × 100"
            ),
            "Sonuç": float(rapor.get("kira_orani", 0)),
        },
    ]
    for ad, deger in dict(rapor.get("risk_detayi", {})).get("bilesenler", {}).items():
        adimlar.append({
            "Aşama": f"Risk · {ad}", "Formül": "Risk bileşeni",
            "Hesap": str(round(float(deger), 4)), "Sonuç": float(deger),
        })
    for ad, deger in dict(rapor.get("yatirim_skoru_detayi", {})).get("bilesenler", {}).items():
        adimlar.append({
            "Aşama": f"Yatırım skoru · {ad}", "Formül": "Skor bileşeni",
            "Hesap": str(round(float(deger), 4)), "Sonuç": float(deger),
        })
    teklif = dict(rapor.get("maksimum_teklif_detayi", {}))
    adimlar.extend([
        {
            "Aşama": "Kâr korumalı kira tavanı",
            "Formül": "Ciro − kira hariç gider − hedef net kâr",
            "Hesap": str(teklif.get("kar_korumali_tavan", 0)),
            "Sonuç": float(teklif.get("kar_korumali_tavan", 0)),
        },
        {
            "Aşama": "Oransal kira tavanı",
            "Formül": "Aylık ciro × azami kira/ciro oranı",
            "Hesap": str(teklif.get("oran_tavani", 0)),
            "Sonuç": float(teklif.get("oran_tavani", 0)),
        },
        {
            "Aşama": "Önerilen maksimum teklif",
            "Formül": "min(kâr korumalı tavan, oransal tavan)",
            "Hesap": str(teklif.get("secilen_tavan", 0)),
            "Sonuç": float(teklif.get("secilen_tavan", 0)),
        },
    ])
    return adimlar


def analizi_kaydet(aday_id: int, rapor: Mapping[str, object]) -> None:
    """Raporu mevcut ilan tablosuna dokunmadan yeni analiz tablosuna yazar."""
    from veritabani import baglan, tablo_olustur

    tablo_olustur()
    simdi = datetime.now().isoformat(timespec="seconds")
    personel = dict(rapor.get("personel_maliyet_analizi", {}))
    with closing(baglan()) as conn, conn:
        conn.execute("""
            INSERT INTO kantin_yatirim_analizleri(
                aday_id, motor_surumu, girdi_json, varsayim_json, sonuc_json,
                tahmini_aylik_ciro, tahmini_yillik_ciro,
                ogrenci_sayisi, okul_tipi, okul_tipi_katsayisi,
                baz_personel_sayisi, onerilen_calisan_sayisi,
                brut_maas, aylik_calisma_saati, tahmini_net_maas,
                sgk_maliyeti, net_maas_sgk_toplami, yan_hak_maliyeti,
                kisi_basi_personel_maliyeti, toplam_personel_gideri,
                personel_hesaplama_modu, manuel_calisan_sayisi,
                tahmini_net_kar, kira_ciro_orani,
                risk_skoru, risk_seviyesi, yatirim_skoru,
                maksimum_teklif, yorum, olusturma_tarihi, guncelleme_tarihi
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(aday_id) DO UPDATE SET
                motor_surumu=excluded.motor_surumu,
                girdi_json=excluded.girdi_json,
                varsayim_json=excluded.varsayim_json,
                sonuc_json=excluded.sonuc_json,
                tahmini_aylik_ciro=excluded.tahmini_aylik_ciro,
                tahmini_yillik_ciro=excluded.tahmini_yillik_ciro,
                ogrenci_sayisi=excluded.ogrenci_sayisi,
                okul_tipi=excluded.okul_tipi,
                okul_tipi_katsayisi=excluded.okul_tipi_katsayisi,
                baz_personel_sayisi=excluded.baz_personel_sayisi,
                onerilen_calisan_sayisi=excluded.onerilen_calisan_sayisi,
                brut_maas=excluded.brut_maas,
                aylik_calisma_saati=excluded.aylik_calisma_saati,
                tahmini_net_maas=excluded.tahmini_net_maas,
                sgk_maliyeti=excluded.sgk_maliyeti,
                net_maas_sgk_toplami=excluded.net_maas_sgk_toplami,
                yan_hak_maliyeti=excluded.yan_hak_maliyeti,
                kisi_basi_personel_maliyeti=excluded.kisi_basi_personel_maliyeti,
                toplam_personel_gideri=excluded.toplam_personel_gideri,
                personel_hesaplama_modu=excluded.personel_hesaplama_modu,
                manuel_calisan_sayisi=excluded.manuel_calisan_sayisi,
                tahmini_net_kar=excluded.tahmini_net_kar,
                kira_ciro_orani=excluded.kira_ciro_orani,
                risk_skoru=excluded.risk_skoru,
                risk_seviyesi=excluded.risk_seviyesi,
                yatirim_skoru=excluded.yatirim_skoru,
                maksimum_teklif=excluded.maksimum_teklif,
                yorum=excluded.yorum,
                guncelleme_tarihi=excluded.guncelleme_tarihi
        """, (
            int(aday_id), str(rapor["motor_surumu"]),
            json.dumps(rapor.get("girdiler", {}), ensure_ascii=False),
            json.dumps(rapor.get("varsayimlar", {}), ensure_ascii=False),
            json.dumps(dict(rapor), ensure_ascii=False),
            float(rapor["tahmini_aylik_ciro"]),
            float(rapor["tahmini_yillik_ciro"]),
            int(personel["ogrenci_sayisi"]), str(personel["okul_tipi"]),
            float(personel["okul_tipi_katsayisi"]),
            int(personel["baz_personel_sayisi"]),
            int(personel["onerilen_calisan_sayisi"]),
            float(personel["brut_maas"]),
            float(personel["aylik_calisma_saati"]),
            float(personel["tahmini_net_maas"]),
            float(personel["sgk_maliyeti"]),
            float(personel["net_maas_sgk_toplami"]),
            float(personel["yan_hak_maliyeti"]),
            float(personel["kisi_basi_personel_maliyeti"]),
            float(personel["toplam_personel_gideri"]),
            str(personel["personel_hesaplama_modu"]),
            personel.get("manuel_calisan_sayisi"),
            float(rapor["net_kar"]),
            float(rapor["kira_orani"]), float(rapor["risk_skoru"]),
            str(rapor["risk"]), int(rapor["yatirim_skoru"]),
            float(rapor["maksimum_kira"]), str(rapor["yorum"]), simdi, simdi,
        ))


def kayitli_analizi_getir(aday_id: int) -> dict[str, object] | None:
    from veritabani import baglan

    with closing(baglan()) as conn:
        satir = conn.execute(
            "SELECT sonuc_json FROM kantin_yatirim_analizleri WHERE aday_id=?",
            (int(aday_id),),
        ).fetchone()
    return json.loads(satir[0]) if satir else None


def _etkin_analiz_girdisi_getir(aday_id: int) -> tuple[dict[str, object], dict[str, object]]:
    from veritabani import baglan

    with closing(baglan()) as conn:
        satir = conn.execute("""
            SELECT d.id AS aday_id,
                   COALESCE(NULLIF(TRIM(m.il), ''), k.il) AS il,
                   COALESCE(NULLIF(TRIM(m.ilce), ''), k.ilce) AS ilce,
                   COALESCE(NULLIF(TRIM(m.okul_adi), ''), a.okul_adi) AS okul_adi,
                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu) AS okul_turu,
                   COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) AS ogrenci_sayisi,
                   COALESCE(m.personel_sayisi, a.personel_sayisi) AS personel_sayisi,
                   COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik)
                       AS muhammen_bedel_aylik,
                   COALESCE(m.muhammen_bedel_yillik, a.muhammen_bedel_yillik)
                       AS muhammen_bedel_yillik,
                   a.kantin_alani_m2,
                   m.ogrenci_donusum_orani,
                   m.ortalama_ogrenci_harcamasi,
                   m.yillik_egitim_gunu,
                   m.hedef_net_kar_orani,
                   m.otomatik_personel_hesapla,
                   m.manuel_calisan_sayisi,
                   m.asgari_ucret,
                   m.net_asgari_ucret,
                   m.brut_maas,
                   m.aylik_calisma_saati,
                   m.tam_zamanli_aylik_saat,
                   m.sgk_isveren_orani,
                   m.issizlik_isveren_orani,
                   m.yemek_maliyeti,
                   m.yol_maliyeti,
                   m.diger_yan_haklar
            FROM duyuru_adaylari d
            JOIN kaynaklar k ON k.id=d.kaynak_id
            LEFT JOIN ilan_analiz_verileri a ON a.aday_id=d.id
            LEFT JOIN analiz_manuel_duzeltmeleri m ON m.aday_id=d.id
            WHERE d.id=?
        """, (int(aday_id),)).fetchone()
    if satir is None:
        raise AnalizVerisiHatasi("İlan kaydı bulunamadı")
    veri = dict(satir)
    parametreler = {
        anahtar: veri.pop(anahtar)
        for anahtar in (
            "ogrenci_donusum_orani", "ortalama_ogrenci_harcamasi",
            "yillik_egitim_gunu",
            "hedef_net_kar_orani",
            "otomatik_personel_hesapla", "manuel_calisan_sayisi",
            "asgari_ucret", "brut_maas", "sgk_isveren_orani",
            "net_asgari_ucret", "aylik_calisma_saati",
            "tam_zamanli_aylik_saat",
            "issizlik_isveren_orani", "yemek_maliyeti", "yol_maliyeti",
            "diger_yan_haklar",
        )
        if veri.get(anahtar) is not None
    }
    return veri, parametreler


def manuel_duzeltme_kaydet(
    aday_id: int,
    duzeltme: Mapping[str, object],
    *,
    duzelten: str = "admin",
) -> dict[str, object]:
    """Belge değerini ezmeden manuel katmanı kaydeder, denetler ve raporu yeniler."""
    from veritabani import baglan, tablo_olustur

    tablo_olustur()
    with closing(baglan()) as conn:
        kaynak_konumu = conn.execute("""
            SELECT k.il, COALESCE(k.ilce, '') AS ilce
            FROM duyuru_adaylari d
            JOIN kaynaklar k ON k.id=d.kaynak_id
            WHERE d.id=?
        """, (int(aday_id),)).fetchone()
    if kaynak_konumu is None:
        raise AnalizVerisiHatasi("İlan kaydı bulunamadı")
    il = str(duzeltme.get("il") or kaynak_konumu["il"] or "").strip()
    ilce = str(duzeltme.get("ilce") or kaynak_konumu["ilce"] or "").strip()
    if not il:
        raise AnalizVerisiHatasi("İl boş bırakılamaz")
    if not ilce:
        raise AnalizVerisiHatasi("İlçe boş bırakılamaz")
    okul_adi = okul_adi_temizle(duzeltme.get("okul_adi")) or ""
    if not okul_adi:
        raise AnalizVerisiHatasi("Okul adı boş bırakılamaz")
    tur_anahtari = _okul_turunu_normalize_et(duzeltme.get("okul_turu"))
    tur_etiketi = {
        "ilkokul": "İlkokul", "ortaokul": "Ortaokul",
        "lise": "Lise", "meslek_lisesi": "Meslek Lisesi", "karma": "Karma",
    }[tur_anahtari]
    ogrenci = int(_sayi(
        duzeltme.get("ogrenci_sayisi"), "Öğrenci sayısı", sifir_olabilir=False
    ))
    personel = int(_sayi(duzeltme.get("personel_sayisi") or 0, "Personel sayısı"))
    aylik = _sayi(
        duzeltme.get("muhammen_bedel_aylik"),
        "Aylık muhammen bedel", sifir_olabilir=False,
    )
    donusum = _oran(
        duzeltme.get("ogrenci_donusum_orani", VARSAYILAN_PARAMETRELER["ogrenci_donusum_orani"]),
        "Öğrenci dönüşüm oranı",
    )
    harcama = _sayi(
        duzeltme.get("ortalama_ogrenci_harcamasi", VARSAYILAN_PARAMETRELER["ortalama_ogrenci_harcamasi"]),
        "Ortalama öğrenci harcaması", sifir_olabilir=False,
    )
    yillik_egitim_gunu = int(_sayi(
        duzeltme.get(
            "yillik_egitim_gunu", VARSAYILAN_PARAMETRELER["yillik_egitim_gunu"]
        ),
        "Yıllık eğitim günü", sifir_olabilir=False,
    ))
    if yillik_egitim_gunu > 366:
        raise AnalizVerisiHatasi("Yıllık eğitim günü 366'yı aşamaz")
    hedef_net_kar_orani = _oran(
        duzeltme.get(
            "hedef_net_kar_orani", VARSAYILAN_PARAMETRELER["hedef_net_kar_orani"]
        ),
        "Hedef net kâr oranı",
    )
    otomatik_personel = bool(duzeltme.get("otomatik_personel_hesapla", True))
    manuel_calisan = None
    if not otomatik_personel:
        manuel_calisan = int(_sayi(
            duzeltme.get("manuel_calisan_sayisi"),
            "Manuel çalışan sayısı", sifir_olabilir=False,
        ))
    asgari_ucret = _sayi(
        duzeltme.get("asgari_ucret", VARSAYILAN_PARAMETRELER["asgari_ucret"]),
        "Asgari ücret", sifir_olabilir=False,
    )
    net_asgari_ucret = _sayi(
        duzeltme.get(
            "net_asgari_ucret", VARSAYILAN_PARAMETRELER["net_asgari_ucret"]
        ),
        "Net asgari ücret", sifir_olabilir=False,
    )
    brut_maas = _sayi(
        duzeltme.get("brut_maas", VARSAYILAN_PARAMETRELER["brut_maas"]),
        "Brüt maaş", sifir_olabilir=False,
    )
    aylik_calisma_saati = _sayi(
        duzeltme.get(
            "aylik_calisma_saati",
            VARSAYILAN_PARAMETRELER["aylik_calisma_saati"],
        ),
        "Aylık çalışma saati", sifir_olabilir=False,
    )
    tam_zamanli_aylik_saat = _sayi(
        duzeltme.get(
            "tam_zamanli_aylik_saat",
            VARSAYILAN_PARAMETRELER["tam_zamanli_aylik_saat"],
        ),
        "Tam zamanlı aylık saat", sifir_olabilir=False,
    )
    sgk_isveren_orani = _oran(
        duzeltme.get(
            "sgk_isveren_orani", VARSAYILAN_PARAMETRELER["sgk_isveren_orani"]
        ),
        "SGK işveren oranı",
    )
    issizlik_isveren_orani = _oran(
        duzeltme.get(
            "issizlik_isveren_orani",
            VARSAYILAN_PARAMETRELER["issizlik_isveren_orani"],
        ),
        "İşsizlik işveren oranı",
    )
    yemek_maliyeti = _sayi(
        duzeltme.get("yemek_maliyeti", 0), "Yemek maliyeti"
    )
    yol_maliyeti = _sayi(duzeltme.get("yol_maliyeti", 0), "Yol maliyeti")
    diger_yan_haklar = _sayi(
        duzeltme.get("diger_yan_haklar", 0), "Diğer yan haklar"
    )
    simdi = datetime.now().isoformat(timespec="seconds")
    yeni = {
        "il": il,
        "ilce": ilce,
        "okul_adi": okul_adi,
        "okul_turu": tur_etiketi,
        "ogrenci_sayisi": ogrenci,
        "personel_sayisi": personel,
        "muhammen_bedel_aylik": aylik,
        "muhammen_bedel_yillik": round(aylik * 9, 2),
        "ogrenci_donusum_orani": donusum,
        "ortalama_ogrenci_harcamasi": harcama,
        "yillik_egitim_gunu": yillik_egitim_gunu,
        "hedef_net_kar_orani": hedef_net_kar_orani,
        "otomatik_personel_hesapla": otomatik_personel,
        "manuel_calisan_sayisi": manuel_calisan,
        "asgari_ucret": asgari_ucret,
        "net_asgari_ucret": net_asgari_ucret,
        "brut_maas": brut_maas,
        "aylik_calisma_saati": aylik_calisma_saati,
        "tam_zamanli_aylik_saat": tam_zamanli_aylik_saat,
        "sgk_isveren_orani": sgk_isveren_orani,
        "issizlik_isveren_orani": issizlik_isveren_orani,
        "yemek_maliyeti": yemek_maliyeti,
        "yol_maliyeti": yol_maliyeti,
        "diger_yan_haklar": diger_yan_haklar,
        "duzeltme_notu": str(duzeltme.get("duzeltme_notu") or "").strip()[:500],
    }
    with closing(baglan()) as conn, conn:
        onceki_satir = conn.execute(
            "SELECT * FROM analiz_manuel_duzeltmeleri WHERE aday_id=?",
            (int(aday_id),),
        ).fetchone()
        onceki = dict(onceki_satir) if onceki_satir else None
        conn.execute("""
            INSERT INTO analiz_manuel_duzeltmeleri(
                aday_id, il, ilce, okul_adi, okul_turu,
                ogrenci_sayisi, personel_sayisi,
                muhammen_bedel_aylik, muhammen_bedel_yillik,
                ogrenci_donusum_orani, ortalama_ogrenci_harcamasi,
                yillik_egitim_gunu, hedef_net_kar_orani,
                otomatik_personel_hesapla, manuel_calisan_sayisi,
                asgari_ucret, brut_maas, sgk_isveren_orani,
                net_asgari_ucret, aylik_calisma_saati,
                tam_zamanli_aylik_saat,
                issizlik_isveren_orani, yemek_maliyeti, yol_maliyeti,
                diger_yan_haklar,
                duzeltme_notu, duzelten, olusturma_tarihi, guncelleme_tarihi
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(aday_id) DO UPDATE SET
                il=excluded.il, ilce=excluded.ilce,
                okul_adi=excluded.okul_adi, okul_turu=excluded.okul_turu,
                ogrenci_sayisi=excluded.ogrenci_sayisi,
                personel_sayisi=excluded.personel_sayisi,
                muhammen_bedel_aylik=excluded.muhammen_bedel_aylik,
                muhammen_bedel_yillik=excluded.muhammen_bedel_yillik,
                ogrenci_donusum_orani=excluded.ogrenci_donusum_orani,
                ortalama_ogrenci_harcamasi=excluded.ortalama_ogrenci_harcamasi,
                yillik_egitim_gunu=excluded.yillik_egitim_gunu,
                hedef_net_kar_orani=excluded.hedef_net_kar_orani,
                otomatik_personel_hesapla=excluded.otomatik_personel_hesapla,
                manuel_calisan_sayisi=excluded.manuel_calisan_sayisi,
                asgari_ucret=excluded.asgari_ucret,
                net_asgari_ucret=excluded.net_asgari_ucret,
                brut_maas=excluded.brut_maas,
                aylik_calisma_saati=excluded.aylik_calisma_saati,
                tam_zamanli_aylik_saat=excluded.tam_zamanli_aylik_saat,
                sgk_isveren_orani=excluded.sgk_isveren_orani,
                issizlik_isveren_orani=excluded.issizlik_isveren_orani,
                yemek_maliyeti=excluded.yemek_maliyeti,
                yol_maliyeti=excluded.yol_maliyeti,
                diger_yan_haklar=excluded.diger_yan_haklar,
                duzeltme_notu=excluded.duzeltme_notu,
                duzelten=excluded.duzelten,
                guncelleme_tarihi=excluded.guncelleme_tarihi
        """, (
            int(aday_id), yeni["il"], yeni["ilce"],
            yeni["okul_adi"], yeni["okul_turu"],
            yeni["ogrenci_sayisi"], yeni["personel_sayisi"],
            yeni["muhammen_bedel_aylik"], yeni["muhammen_bedel_yillik"],
            yeni["ogrenci_donusum_orani"], yeni["ortalama_ogrenci_harcamasi"],
            yeni["yillik_egitim_gunu"], yeni["hedef_net_kar_orani"],
            int(yeni["otomatik_personel_hesapla"]),
            yeni["manuel_calisan_sayisi"], yeni["asgari_ucret"],
            yeni["brut_maas"], yeni["sgk_isveren_orani"],
            yeni["net_asgari_ucret"], yeni["aylik_calisma_saati"],
            yeni["tam_zamanli_aylik_saat"],
            yeni["issizlik_isveren_orani"], yeni["yemek_maliyeti"],
            yeni["yol_maliyeti"], yeni["diger_yan_haklar"],
            yeni["duzeltme_notu"],
            str(duzelten or "admin")[:80], simdi, simdi,
        ))
        conn.execute("""
            INSERT INTO analiz_manuel_gecmisi(
                aday_id, islem, onceki_json, yeni_json, duzelten, islem_tarihi
            ) VALUES (?, 'kaydet', ?, ?, ?, ?)
        """, (
            int(aday_id), json.dumps(onceki, ensure_ascii=False) if onceki else None,
            json.dumps(yeni, ensure_ascii=False), str(duzelten or "admin")[:80], simdi,
        ))
        ogrenme_ornegi_kaydet(
            conn,
            int(aday_id),
            yeni,
            duzelten=str(duzelten or "admin"),
            olusturma_tarihi=simdi,
        )
        conn.execute("""
            UPDATE ihale_belgeleri
            SET durum='analiz_edildi', son_hata=NULL, son_kontrol=?
            WHERE aday_id=?
        """, (simdi, int(aday_id)))
    girdi, parametreler = _etkin_analiz_girdisi_getir(aday_id)
    rapor = analiz_raporu_olustur(girdi, parametreler)
    analizi_kaydet(aday_id, rapor)
    return rapor


def manuel_duzeltmeyi_kaldir(
    aday_id: int,
    *,
    duzelten: str = "admin",
) -> dict[str, object] | None:
    """Manuel katmanı geri alır; mümkünse belge verisiyle raporu yeniden üretir."""
    from veritabani import baglan, tablo_olustur

    tablo_olustur()
    simdi = datetime.now().isoformat(timespec="seconds")
    with closing(baglan()) as conn, conn:
        onceki_satir = conn.execute(
            "SELECT * FROM analiz_manuel_duzeltmeleri WHERE aday_id=?",
            (int(aday_id),),
        ).fetchone()
        onceki = dict(onceki_satir) if onceki_satir else None
        conn.execute(
            "DELETE FROM analiz_manuel_duzeltmeleri WHERE aday_id=?", (int(aday_id),)
        )
        conn.execute("""
            INSERT INTO analiz_manuel_gecmisi(
                aday_id, islem, onceki_json, yeni_json, duzelten, islem_tarihi
            ) VALUES (?, 'kaldir', ?, NULL, ?, ?)
        """, (
            int(aday_id), json.dumps(onceki, ensure_ascii=False) if onceki else None,
            str(duzelten or "admin")[:80], simdi,
        ))
        conn.execute("""
            UPDATE ihale_belgeleri
            SET durum='analiz_bekliyor',
                son_hata='Manuel doğrulama kaldırıldı; zorunlu belge alanları yeniden işlenecek',
                son_kontrol=?
            WHERE aday_id=?
              AND EXISTS (
                  SELECT 1
                  FROM ilan_analiz_verileri a
                  WHERE a.aday_id=?
                    AND (
                           NULLIF(TRIM(a.okul_adi), '') IS NULL
                        OR NULLIF(TRIM(a.okul_turu), '') IS NULL
                        OR a.ogrenci_sayisi IS NULL
                        OR a.muhammen_bedel_aylik IS NULL
                    )
              )
        """, (simdi, int(aday_id), int(aday_id)))
    try:
        girdi, parametreler = _etkin_analiz_girdisi_getir(aday_id)
        rapor = analiz_raporu_olustur(girdi, parametreler)
    except AnalizVerisiHatasi:
        with closing(baglan()) as conn, conn:
            conn.execute(
                "DELETE FROM kantin_yatirim_analizleri WHERE aday_id=?", (int(aday_id),)
            )
        return None
    analizi_kaydet(aday_id, rapor)
    return rapor


def tamamlanan_belgeleri_analiz_et(limit: int = 25) -> dict[str, int]:
    """Zorunlu belge alanları tamamlanan ilanların yatırım raporunu kalıcılaştırır."""
    from veritabani import baglan, tablo_olustur

    tablo_olustur()
    with closing(baglan()) as conn:
        satirlar = conn.execute("""
            SELECT d.id AS aday_id, d.baslik, k.il, k.ilce,
                   COALESCE(NULLIF(TRIM(m.okul_adi), ''), a.okul_adi) AS okul_adi,
                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu) AS okul_turu,
                   COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) AS ogrenci_sayisi,
                   COALESCE(m.personel_sayisi, a.personel_sayisi) AS personel_sayisi,
                   COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik)
                       AS muhammen_bedel_aylik,
                   COALESCE(m.muhammen_bedel_yillik, a.muhammen_bedel_yillik)
                       AS muhammen_bedel_yillik,
                   m.ogrenci_donusum_orani, m.ortalama_ogrenci_harcamasi,
                   m.yillik_egitim_gunu, m.hedef_net_kar_orani,
                   m.otomatik_personel_hesapla, m.manuel_calisan_sayisi,
                   m.asgari_ucret, m.brut_maas, m.sgk_isveren_orani,
                   m.net_asgari_ucret, m.aylik_calisma_saati,
                   m.tam_zamanli_aylik_saat,
                   m.issizlik_isveren_orani, m.yemek_maliyeti,
                   m.yol_maliyeti, m.diger_yan_haklar,
                   a.kantin_alani_m2
            FROM ilan_analiz_verileri a
            JOIN duyuru_adaylari d ON d.id=a.aday_id
            JOIN kaynaklar k ON k.id=d.kaynak_id
            LEFT JOIN analiz_manuel_duzeltmeleri m ON m.aday_id=d.id
            LEFT JOIN kantin_yatirim_analizleri y ON y.aday_id=d.id
            WHERE NULLIF(TRIM(COALESCE(m.okul_adi, a.okul_adi)), '') IS NOT NULL
              AND NULLIF(TRIM(COALESCE(m.okul_turu, a.okul_turu)), '') IS NOT NULL
              AND COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) IS NOT NULL
              AND COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik) IS NOT NULL
              AND (
                    y.id IS NULL OR y.motor_surumu<>?
                    OR COALESCE(y.tahmini_yillik_ciro, 0)<=0
                  )
              AND NOT EXISTS (
                  SELECT 1
                  FROM duyuru_adaylari child
                  WHERE child.detay_url=d.url
                    AND child.eslesme_turu='ek_dosya'
                  GROUP BY child.detay_url
                  HAVING COUNT(*) > 1
              )
            ORDER BY d.yayin_tarihi DESC, d.id DESC
            LIMIT ?
        """, (MOTOR_SURUMU, max(1, min(int(limit), 500)))).fetchall()
    sonuc = {"islenen": 0, "hata": 0}
    for satir in satirlar:
        try:
            veri = dict(satir)
            parametreler = {
                anahtar: veri.pop(anahtar)
                for anahtar in (
                    "ogrenci_donusum_orani", "ortalama_ogrenci_harcamasi",
                    "yillik_egitim_gunu", "hedef_net_kar_orani",
                    "otomatik_personel_hesapla", "manuel_calisan_sayisi",
                    "asgari_ucret", "brut_maas", "sgk_isveren_orani",
                    "net_asgari_ucret", "aylik_calisma_saati",
                    "tam_zamanli_aylik_saat",
                    "issizlik_isveren_orani", "yemek_maliyeti",
                    "yol_maliyeti", "diger_yan_haklar",
                )
                if veri.get(anahtar) is not None
            }
            rapor = analiz_raporu_olustur(veri, parametreler)
            analizi_kaydet(int(satir["aday_id"]), rapor)
            sonuc["islenen"] += 1
        except (AnalizVerisiHatasi, KeyError, TypeError, ValueError):
            sonuc["hata"] += 1
    return sonuc


__all__ = [
    "AnalizVerisiHatasi", "MOTOR_SURUMU", "VARSAYILAN_PARAMETRELER",
    "ciro_hesapla", "gider_hesapla", "net_kar_hesapla",
    "kira_orani_hesapla", "risk_skoru_hesapla", "yatirim_skoru_hesapla",
    "maksimum_teklif_hesapla", "analiz_raporu_olustur", "analiz_matematigi_olustur",
    "analizi_kaydet", "kayitli_analizi_getir", "okul_tipi_belirle",
    "tamamlanan_belgeleri_analiz_et", "manuel_duzeltme_kaydet",
    "manuel_duzeltmeyi_kaldir", "OKUL_TURU_HARCAMA_KATSAYILARI",
    "yatirim_skoru_detayi_hesapla", "OKUL_TURU_DONUSUM_ARALIKLARI",
    "OKUL_TURU_DONUSUM_ORANLARI",
]
