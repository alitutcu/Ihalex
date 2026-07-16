"""İl/ilçe bazlı doğrulanabilir bölgesel veri erişim katmanı.

Gerçek bir kaynak bağlanana kadar bütün katsayılar 1.00'dır ve nötr etki yapar.
Bu modül tahmini bölgesel skor üretmez.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from typing import Mapping, Protocol

from veritabani import baglan, tablo_olustur


VARSAYILAN_KAYNAK = "Henüz bağlanmadı"
KATSAYI_ALANLARI = (
    "ekonomik_katsayi",
    "gelir_katsayi",
    "nufus_katsayi",
    "ticari_hareketlilik_katsayi",
)


class BolgeVeriHatasi(ValueError):
    pass


class BolgeVeriSaglayici(Protocol):
    """TÜİK, belediye veya başka bir doğrulanmış adaptörün uyması gereken arayüz."""

    kaynak_adi: str

    def veri_getir(self, il: str, ilce: str) -> Mapping[str, object]: ...


def _konum_duzelt(deger: object, alan: str, *, bos_olabilir: bool = False) -> str:
    metin = " ".join(str(deger or "").split())
    if not metin and not bos_olabilir:
        raise BolgeVeriHatasi(f"{alan} zorunludur")
    return metin


def _katsayi(deger: object, alan: str) -> float:
    try:
        sayi = float(deger)
    except (TypeError, ValueError) as hata:
        raise BolgeVeriHatasi(f"{alan} sayısal olmalıdır") from hata
    if not 0.25 <= sayi <= 4.00:
        raise BolgeVeriHatasi(f"{alan} 0.25 ile 4.00 arasında olmalıdır")
    return round(sayi, 4)


def veri_kaynagi_kontrol(veri_kaynagi: object) -> bool:
    """Bir kaynak adının varsayılan/boş olmadığını kontrol eder; içerik doğrulamaz."""
    kaynak = " ".join(str(veri_kaynagi or "").split())
    return bool(kaynak and kaynak.casefold() != VARSAYILAN_KAYNAK.casefold())


def varsayilan_bolge_olustur(il: str, ilce: str = "") -> dict[str, object]:
    tablo_olustur()
    il = _konum_duzelt(il, "İl")
    ilce = _konum_duzelt(ilce, "İlçe", bos_olabilir=True)
    simdi = datetime.now().isoformat(timespec="seconds")
    with closing(baglan()) as conn, conn:
        conn.execute("""
            INSERT OR IGNORE INTO bolge_verileri(
                il, ilce, ekonomik_katsayi, gelir_katsayi, nufus_katsayi,
                ticari_hareketlilik_katsayi, veri_kaynagi, guncelleme_tarihi
            ) VALUES (?, ?, 1.00, 1.00, 1.00, 1.00, ?, ?)
        """, (il, ilce, VARSAYILAN_KAYNAK, simdi))
        satir = conn.execute(
            "SELECT * FROM bolge_verileri WHERE il=? AND ilce=?",
            (il, ilce),
        ).fetchone()
    return _satir_sozluk(satir)


def _satir_sozluk(satir: object) -> dict[str, object]:
    veri = dict(satir)
    veri["veri_durumu"] = (
        "Kaynak bağlı" if veri_kaynagi_kontrol(veri.get("veri_kaynagi"))
        else "Varsayılan"
    )
    return veri


def bolge_verisi_getir(il: str, ilce: str = "") -> dict[str, object]:
    il = _konum_duzelt(il, "İl")
    ilce = _konum_duzelt(ilce, "İlçe", bos_olabilir=True)
    tablo_olustur()
    with closing(baglan()) as conn:
        satir = conn.execute(
            "SELECT * FROM bolge_verileri WHERE il=? AND ilce=?",
            (il, ilce),
        ).fetchone()
    return _satir_sozluk(satir) if satir else varsayilan_bolge_olustur(il, ilce)


def ekonomik_katsayi_hesapla(bolge_verisi: Mapping[str, object] | None = None) -> float:
    """Doğrulanmış kaynak yoksa tahmin üretmeden nötr 1.00 döndürür."""
    veri = dict(bolge_verisi or {})
    if not veri_kaynagi_kontrol(veri.get("veri_kaynagi")):
        return 1.00
    return _katsayi(veri.get("ekonomik_katsayi", 1.00), "Ekonomik katsayı")


def veri_guncelle(
    il: str,
    ilce: str = "",
    *,
    ekonomik_katsayi: float = 1.00,
    gelir_katsayi: float = 1.00,
    nufus_katsayi: float = 1.00,
    ticari_hareketlilik_katsayi: float = 1.00,
    kira_endeksi: float | None = None,
    ses_skoru: float | None = None,
    veri_kaynagi: str = VARSAYILAN_KAYNAK,
    kaynak_dogrulandi: bool = False,
) -> dict[str, object]:
    """Bölge kaydını günceller; doğrulama olmadan nötr dışı katsayı kabul etmez."""
    il = _konum_duzelt(il, "İl")
    ilce = _konum_duzelt(ilce, "İlçe", bos_olabilir=True)
    katsayilar = {
        "ekonomik_katsayi": _katsayi(ekonomik_katsayi, "Ekonomik katsayı"),
        "gelir_katsayi": _katsayi(gelir_katsayi, "Gelir katsayısı"),
        "nufus_katsayi": _katsayi(nufus_katsayi, "Nüfus katsayısı"),
        "ticari_hareketlilik_katsayi": _katsayi(
            ticari_hareketlilik_katsayi, "Ticari hareketlilik katsayısı"
        ),
    }
    notr_disinda = any(abs(deger - 1.00) > 0.0001 for deger in katsayilar.values())
    if notr_disinda and not kaynak_dogrulandi:
        raise BolgeVeriHatasi(
            "Doğrulanmış veri kaynağı olmadan nötr dışı bölgesel katsayı kaydedilemez"
        )
    if kaynak_dogrulandi and not veri_kaynagi_kontrol(veri_kaynagi):
        raise BolgeVeriHatasi("Doğrulanmış güncelleme için veri kaynağı zorunludur")
    simdi = datetime.now().isoformat(timespec="seconds")
    tablo_olustur()
    with closing(baglan()) as conn, conn:
        conn.execute("""
            INSERT INTO bolge_verileri(
                il, ilce, ekonomik_katsayi, gelir_katsayi, nufus_katsayi,
                ticari_hareketlilik_katsayi, kira_endeksi, ses_skoru,
                veri_kaynagi, guncelleme_tarihi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(il, ilce) DO UPDATE SET
                ekonomik_katsayi=excluded.ekonomik_katsayi,
                gelir_katsayi=excluded.gelir_katsayi,
                nufus_katsayi=excluded.nufus_katsayi,
                ticari_hareketlilik_katsayi=excluded.ticari_hareketlilik_katsayi,
                kira_endeksi=excluded.kira_endeksi,
                ses_skoru=excluded.ses_skoru,
                veri_kaynagi=excluded.veri_kaynagi,
                guncelleme_tarihi=excluded.guncelleme_tarihi
        """, (
            il, ilce, katsayilar["ekonomik_katsayi"], katsayilar["gelir_katsayi"],
            katsayilar["nufus_katsayi"], katsayilar["ticari_hareketlilik_katsayi"],
            float(kira_endeksi) if kira_endeksi is not None else None,
            float(ses_skoru) if ses_skoru is not None else None,
            str(veri_kaynagi or VARSAYILAN_KAYNAK), simdi,
        ))
        satir = conn.execute(
            "SELECT * FROM bolge_verileri WHERE il=? AND ilce=?", (il, ilce)
        ).fetchone()
    return _satir_sozluk(satir)


__all__ = [
    "BolgeVeriHatasi", "BolgeVeriSaglayici", "VARSAYILAN_KAYNAK",
    "bolge_verisi_getir", "varsayilan_bolge_olustur",
    "ekonomik_katsayi_hesapla", "veri_guncelle", "veri_kaynagi_kontrol",
]
