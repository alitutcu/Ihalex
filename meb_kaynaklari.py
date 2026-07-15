"""İl ve ilçe MEB takip kaynaklarının veritabanı işlemleri."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from typing import Any

from veritabani import baglan


def kaynak_ekle(
    kurum_adi: str,
    il: str,
    ilce: str,
    url: str,
    *,
    aktif: bool,
    dogrulandi: bool,
    seviye: str,
    strateji: str = "duyuru_listesi",
) -> bool:
    simdi = datetime.now().isoformat(timespec="seconds")
    with closing(baglan()) as conn, conn:
        cursor = conn.execute("""
            INSERT INTO kaynaklar (
                kurum_adi, il, ilce, url, kaynak_turu, aktif,
                dogrulandi, kaynak_seviyesi, tarama_stratejisi, eklenme_tarihi
            ) VALUES (?, ?, ?, ?, 'html', ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                kurum_adi=excluded.kurum_adi,
                il=excluded.il,
                ilce=excluded.ilce,
                kaynak_seviyesi=excluded.kaynak_seviyesi,
                tarama_stratejisi=excluded.tarama_stratejisi,
                dogrulandi=MAX(kaynaklar.dogrulandi, excluded.dogrulandi),
                aktif=MAX(kaynaklar.aktif, excluded.aktif)
        """, (kurum_adi, il, ilce, url, int(aktif), int(dogrulandi),
              seviye, strateji, simdi))
        return cursor.rowcount > 0


def siradaki_kaynaklar(limit: int = 20) -> list[dict[str, Any]]:
    with closing(baglan()) as conn:
        satirlar = conn.execute("""
            SELECT * FROM kaynaklar
            WHERE aktif = 1 AND dogrulandi = 1 AND (
                son_tarama IS NULL OR
                datetime(son_tarama, '+' || tarama_araligi_dakika || ' minutes')
                    <= datetime('now', 'localtime')
            )
            ORDER BY son_tarama IS NOT NULL, son_tarama
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(satir) for satir in satirlar]


def tum_aktif_kaynaklar() -> list[dict[str, Any]]:
    """Planlı tam tarama için bütün doğrulanmış kaynakları döndürür."""
    with closing(baglan()) as conn:
        satirlar = conn.execute("""
            SELECT * FROM kaynaklar
            WHERE aktif=1 AND dogrulandi=1
            ORDER BY il, ilce, kurum_adi
        """).fetchall()
    return [dict(satir) for satir in satirlar]


def kaynak_ozeti() -> dict[str, int]:
    with closing(baglan()) as conn:
        satir = conn.execute("""
            SELECT COUNT(1), SUM(aktif), SUM(dogrulandi),
                   SUM(CASE WHEN kaynak_seviyesi='il' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN kaynak_seviyesi='ilce' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN son_durum='basarili' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN son_durum='hata' THEN 1 ELSE 0 END)
            FROM kaynaklar
        """).fetchone()
    anahtarlar = ("toplam", "aktif", "dogrulanmis", "il", "ilce", "basarili", "hata")
    return {anahtar: int(deger or 0) for anahtar, deger in zip(anahtarlar, satir)}


def kaynaklari_getir() -> list[dict[str, Any]]:
    with closing(baglan()) as conn:
        satirlar = conn.execute("""
            SELECT kurum_adi, il, ilce, url, kaynak_seviyesi, aktif,
                   dogrulandi, son_durum, son_tarama, son_hata
            FROM kaynaklar ORDER BY il, ilce
        """).fetchall()
    return [dict(satir) for satir in satirlar]
