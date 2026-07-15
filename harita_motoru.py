"""Son bir yıldaki doğrulanmış MEB ihaleleri için bölgesel istatistikler."""

from __future__ import annotations

import sqlite3
import unicodedata

import pandas as pd

from veritabani import DB, ihale_tarih_siniri


IL_ADLARI = (
    "", "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara",
    "Antalya", "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis",
    "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir",
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin",
    "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir",
    "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin",
    "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun",
    "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli",
    "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt",
    "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır",
    "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce",
)
IL_KODLARI = {ad: kod for kod, ad in enumerate(IL_ADLARI) if ad}
IL_KODLARI["Afyon"] = 3
_ILCE_ANAHTAR_DUZELTMELERI = {
    (4, "dogubeyazit"): "dogubayazit",
}


def metin_anahtari(metin: str) -> str:
    """Türkçe yer adlarını harita eşleştirmesi için dayanıklı bir anahtara çevirir."""
    sade = unicodedata.normalize("NFKD", str(metin).casefold()).replace("ı", "i")
    return "".join(
        harf for harf in sade if harf.isalnum() and not unicodedata.combining(harf)
    )


def ilce_harita_id(il_kodu: int, ilce: str) -> str:
    anahtar = metin_anahtari(ilce)
    anahtar = _ILCE_ANAHTAR_DUZELTMELERI.get((il_kodu, anahtar), anahtar)
    return f"{il_kodu}:{anahtar}"


def ilce_harita_istatistikleri() -> pd.DataFrame:
    """İlçe bilgisi bulunan benzersiz ihaleleri harita anahtarıyla döndürür."""
    sinir = ihale_tarih_siniri().isoformat()
    with sqlite3.connect(DB) as conn:
        df = pd.read_sql_query("""
            WITH benzersiz AS (
                SELECT k.il, k.ilce,
                       COALESCE(NULLIF(d.detay_url, ''), d.url) AS ihale
                FROM duyuru_adaylari d
                JOIN kaynaklar k ON k.id = d.kaynak_id
                WHERE k.ilce <> '' AND d.yayin_tarihi >= ?
                GROUP BY k.il, k.ilce, ihale
            )
            SELECT il, ilce, COUNT(*) AS ilan_sayisi
            FROM benzersiz
            GROUP BY il, ilce
        """, conn, params=(sinir,))
    if df.empty:
        return pd.DataFrame(
            columns=["il", "ilce", "il_kodu", "harita_id", "ilan_sayisi"]
        )
    df["il_kodu"] = df["il"].map(IL_KODLARI)
    df = df.dropna(subset=["il_kodu"]).copy()
    df["il_kodu"] = df["il_kodu"].astype(int)
    df["harita_id"] = df.apply(
        lambda satir: ilce_harita_id(satir["il_kodu"], satir["ilce"]), axis=1
    )
    return df


def il_istatistikleri() -> pd.DataFrame:
    sinir = ihale_tarih_siniri().isoformat()
    with sqlite3.connect(DB) as conn:
        iller = pd.read_sql_query(
            "SELECT DISTINCT il FROM bolgeler WHERE tur='il' ORDER BY il", conn
        )
        sayilar = pd.read_sql_query("""
            WITH benzersiz AS (
                SELECT k.il, COALESCE(NULLIF(d.detay_url, ''), d.url) AS ihale
                FROM duyuru_adaylari d
                JOIN kaynaklar k ON k.id = d.kaynak_id
                WHERE d.yayin_tarihi >= ?
                GROUP BY k.il, ihale
            )
            SELECT il, COUNT(*) AS ilan_sayisi
            FROM benzersiz
            GROUP BY il
        """, conn, params=(sinir,))
    sonuc = iller.merge(sayilar, on="il", how="left")
    sonuc["ilan_sayisi"] = sonuc["ilan_sayisi"].fillna(0).astype(int)
    return sonuc


def ilce_istatistikleri(il: str) -> pd.DataFrame:
    sinir = ihale_tarih_siniri().isoformat()
    with sqlite3.connect(DB) as conn:
        return pd.read_sql_query("""
            WITH benzersiz AS (
                SELECT k.ilce, COALESCE(NULLIF(d.detay_url, ''), d.url) AS ihale
                FROM duyuru_adaylari d
                JOIN kaynaklar k ON k.id = d.kaynak_id
                WHERE k.il = ? AND k.ilce <> '' AND d.yayin_tarihi >= ?
                GROUP BY k.ilce, ihale
            )
            SELECT ilce AS "İlçe", COUNT(*) AS "İhale sayısı"
            FROM benzersiz
            GROUP BY ilce
            ORDER BY "İhale sayısı" DESC, ilce
        """, conn, params=(il, sinir))
