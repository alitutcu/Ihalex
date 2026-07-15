"""Dashboard istatistikleri için okul adı ve tekrar ihale kuralları."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd


KANTIN_DESENI = (
    r"\b(?:kantin\w*|büfe\w*|bufe\w*|çay\s+ocağ\w*|"
    r"cay\s+ocag\w*|kafeterya\w*)\b"
)
OKUL_TURU_DESENI = (
    r"\b(?:anaokulu|ilkokulu|ortaokulu|lisesi|okulu|mtal|"
    r"eğitim\s+merkezi|egitim\s+merkezi)\b"
)
MEM_ON_EKI_DESENI = (
    r"^.*?\b(?:ilçe|ilce|il)\s+mill[iî]\s+eğitim\s+"
    r"müdürlüğü\w*\b"
)


def okul_adi_ayikla(baslik: object) -> str | None:
    """İhale başlığından kaynak MEM adını dışarıda bırakarak okul adını ayıklar."""
    metin = " ".join(str(baslik or "").strip().split())
    if not metin:
        return None

    metin = re.sub(MEM_ON_EKI_DESENI, "", metin, count=1, flags=re.IGNORECASE).strip()
    kantin_oncesi = re.split(KANTIN_DESENI, metin, maxsplit=1, flags=re.IGNORECASE)[0]
    aday = kantin_oncesi if re.search(OKUL_TURU_DESENI, kantin_oncesi, re.IGNORECASE) else ""

    if not aday:
        for parca in reversed(re.split(r"\s[-–—]\s|[:|/]", metin)):
            okul_turu = list(re.finditer(OKUL_TURU_DESENI, parca, re.IGNORECASE))
            if okul_turu:
                aday = parca[:okul_turu[-1].end()]
                break

    aday = re.sub(
        r"^.*\b(?:ihale(?:si|leri)?|ilan(?:ı|i)?|duyuru(?:su)?)\b",
        "",
        aday,
        count=1,
        flags=re.IGNORECASE,
    )
    aday = " ".join(aday.strip(" -–—_/\t").split())
    if not aday or not re.search(OKUL_TURU_DESENI, aday, re.IGNORECASE):
        return None
    if re.search(r"mill[iî]\s+eğitim\s+müdürlüğü", aday, re.IGNORECASE):
        return None
    return aday


def okul_anahtari(okul_adi: object) -> str:
    sade = unicodedata.normalize("NFKD", str(okul_adi).casefold()).replace("ı", "i")
    sade = "".join(harf for harf in sade if not unicodedata.combining(harf))
    return " ".join(re.findall(r"[a-z0-9]+", sade))


def _tarihleri_yaz(seri: pd.Series) -> str:
    tarihler = sorted(pd.Timestamp(tarih) for tarih in seri.dropna().unique())
    return " · ".join(tarih.strftime("%d.%m.%Y") for tarih in tarihler)


def tekrar_ihale_ozeti(veri: pd.DataFrame) -> pd.DataFrame:
    """Aynı okulun farklı yayın+ihale tarihi çiftlerini tekrar olarak sayar."""
    kolonlar = [
        "il", "İlçe", "Okul", "İhale sayısı", "Yayın tarihleri", "İhale tarihleri"
    ]
    if veri.empty:
        return pd.DataFrame(columns=kolonlar)

    okul_verisi = veri.copy()
    okul_verisi["İlçe"] = (
        okul_verisi["ilce"].fillna("").replace("", "Doğrulanıyor")
    )
    okul_verisi["Okul"] = okul_verisi["baslik"].map(okul_adi_ayikla)
    okul_verisi = okul_verisi.dropna(subset=["Okul", "ihale_tarihi"])
    okul_verisi["okul_anahtari"] = okul_verisi["Okul"].map(okul_anahtari)
    okul_verisi = okul_verisi.drop_duplicates(
        ["il", "İlçe", "okul_anahtari", "yayin_tarihi", "ihale_tarihi"]
    )

    tekrarlar = (
        okul_verisi.groupby(["il", "İlçe", "okul_anahtari"], as_index=False)
        .agg(
            Okul=("Okul", "first"),
            **{
                "İhale sayısı": ("yayin_tarihi", "size"),
                "Yayın tarihleri": ("yayin_tarihi", _tarihleri_yaz),
                "İhale tarihleri": ("ihale_tarihi", _tarihleri_yaz),
            },
        )
    )
    tekrarlar = tekrarlar[tekrarlar["İhale sayısı"] > 1].sort_values(
        "İhale sayısı", ascending=False
    )
    return tekrarlar.drop(columns="okul_anahtari").reset_index(drop=True)
