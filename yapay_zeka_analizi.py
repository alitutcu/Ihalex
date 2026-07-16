"""MEB ihale kayitlari icin aciklanabilir kart analizleri."""

from __future__ import annotations

from datetime import date
from typing import Mapping
from urllib.parse import urlparse

import pandas as pd


def _var(deger: object) -> bool:
    return deger is not None and not pd.isna(deger) and bool(str(deger).strip())


def _resmi_meb_url(url: object) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host == "meb.gov.tr" or host.endswith(".meb.gov.tr")


def ilan_kart_analizi(
    ilan: Mapping[str, object],
    *,
    bugun: date | None = None,
) -> dict[str, object]:
    """Bir ilani takip onceligi ve veri guveniyle aciklanabilir sekilde ozetler."""
    bugun = bugun or date.today()
    durum = str(ilan.get("durum") or "tarih_bekleniyor")
    ihale_ham = ilan.get("ihale_tarihi")
    ihale_tarihi = None
    if _var(ihale_ham):
        try:
            ihale_tarihi = pd.Timestamp(ihale_ham).date()
        except (TypeError, ValueError):
            pass
    kalan_gun = (ihale_tarihi - bugun).days if ihale_tarihi else None

    okul = str(ilan.get("okul_adi") or "").strip()
    okul_dogrulandi = bool(okul and okul != "Okul adı doğrulanıyor")
    okul_turu = str(ilan.get("okul_turu") or "").strip()
    okul_turu_dogrulandi = bool(
        okul_turu and okul_turu != "Okul türü doğrulanıyor"
    )
    ilce_dogrulandi = _var(ilan.get("ilce"))
    resmi_baglanti = _resmi_meb_url(ilan.get("ihale_url"))

    guven = 35
    guven += 15 if _var(ilan.get("yayin_tarihi")) else 0
    guven += 25 if ihale_tarihi else 0
    guven += 15 if okul_dogrulandi else 0
    guven += 5 if okul_turu_dogrulandi else 0
    guven += 5 if ilce_dogrulandi else 0
    guven += 5 if resmi_baglanti else 0
    belge_alanlari = (
        "ogrenci_sayisi", "personel_sayisi", "muhammen_bedel_aylik",
        "sartname_bedeli", "gecici_teminat", "kantin_alani_m2",
    )
    dolu_belge_alani = sum(_var(ilan.get(alan)) for alan in belge_alanlari)
    guven += min(dolu_belge_alani * 3, 15)
    guven = min(guven, 100)

    if durum == "aktif" and kalan_gun is not None and kalan_gun >= 0:
        oncelik = 70
        if kalan_gun <= 3:
            oncelik += 25
            etiket = "Çok acil"
        elif kalan_gun <= 10:
            oncelik += 18
            etiket = "Yaklaşan ihale"
        elif kalan_gun <= 30:
            oncelik += 10
            etiket = "Takip edilmeli"
        else:
            etiket = "Planlama aşaması"
        oncelik = min(oncelik + (5 if guven >= 90 else 0), 100)
        ozet = f"İhale için {kalan_gun} gün kaldı. Resmî belge ve başvuru koşulları kontrol edilmeli."
    elif durum == "pasif" or (kalan_gun is not None and kalan_gun < 0):
        oncelik = 15
        etiket = "Süresi geçmiş"
        ozet = "İhale tarihi geçmiş. Kayıt geçmiş ve tekrar ihale analizi için korunuyor."
    else:
        oncelik = 45
        etiket = "Tarih doğrulanmalı"
        ozet = "İhale tarihi henüz doğrulanmadı; belge incelemesi tamamlanmadan karar verilmemeli."

    eksikler: list[str] = []
    if not okul_dogrulandi:
        eksikler.append("okul adı")
    if not okul_turu_dogrulandi:
        eksikler.append("okul türü")
    if not ilce_dogrulandi:
        eksikler.append("ilçe")
    if not ihale_tarihi:
        eksikler.append("ihale tarihi")
    alan_etiketleri = {
        "ogrenci_sayisi": "öğrenci sayısı",
        "personel_sayisi": "personel sayısı",
        "muhammen_bedel_aylik": "aylık muhammen bedel",
        "sartname_bedeli": "şartname bedeli",
        "gecici_teminat": "geçici teminat",
        "kantin_alani_m2": "kantin alanı",
    }
    eksikler.extend(
        etiket for alan, etiket in alan_etiketleri.items() if not _var(ilan.get(alan))
    )

    return {
        "takip_onceligi": oncelik,
        "veri_guveni": guven,
        "etiket": etiket,
        "ozet": ozet,
        "kalan_gun": kalan_gun,
        "eksikler": eksikler,
        "resmi_baglanti": resmi_baglanti,
        "belge_alani_sayisi": dolu_belge_alani,
    }
