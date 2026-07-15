"""Mevcut MEB duyurularının gerçek ihale tarihlerini sayfa/PDF içeriğinden tamamlar."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from pathlib import PurePosixPath
from urllib.parse import urlparse
from datetime import datetime

import requests

from meb_tarama_servisi import (
    HEADERS,
    _detay_dogrula,
    _resmi_meb_url,
)
from veritabani import aday_durumlarini_guncelle, baglan, ihale_tarih_siniri


def bekleyen_ihaleler(
    limit: int | None = None,
    *,
    zorla: bool = False,
    dosya_turu: str | None = None,
) -> list[dict[str, object]]:
    sinir = ihale_tarih_siniri().isoformat()
    limit_sql = " LIMIT ?" if limit else ""
    tekrar_sql = "" if zorla else """
              AND (
                  tarih_son_kontrol IS NULL OR
                  datetime(tarih_son_kontrol, '+24 hours') <= datetime('now', 'localtime')
              )
    """
    tur_having = (
        "HAVING MAX(CASE WHEN dosya_turu=? THEN 1 ELSE 0 END)=1"
        if dosya_turu else ""
    )
    parametreler: list[object] = [sinir]
    if dosya_turu:
        parametreler.append(dosya_turu)
    if limit:
        parametreler.append(limit)
    with closing(baglan()) as conn:
        satirlar = conn.execute(f"""
            SELECT
                COALESCE(NULLIF(detay_url, ''), url) AS ihale_anahtari,
                MAX(yayin_tarihi) AS yayin_tarihi
            FROM duyuru_adaylari
            WHERE ihale_tarihi IS NULL AND yayin_tarihi >= ?
              {tekrar_sql}
            GROUP BY ihale_anahtari
            {tur_having}
            ORDER BY MIN(tarih_son_kontrol) IS NOT NULL, MIN(tarih_son_kontrol), yayin_tarihi DESC
            {limit_sql}
        """, tuple(parametreler)).fetchall()
    return [dict(satir) for satir in satirlar]


def _tek_ihale(
    kayit: dict[str, object], derin_ocr: bool = False
) -> tuple[str, str | None]:
    anahtar = str(kayit["ihale_anahtari"])
    yayin_tarihi = str(kayit["yayin_tarihi"])
    if not _resmi_meb_url(anahtar):
        return anahtar, None

    oturum = requests.Session()
    oturum.headers.update(HEADERS)
    ihale_tarihi = None
    uzanti = PurePosixPath(urlparse(anahtar).path).suffix.lower()
    try:
        if uzanti not in {".doc", ".xls"}:
            _, _, _, ihale_tarihi = _detay_dogrula(
                oturum, anahtar, "", yayin_tarihi, dosya_gun_siniri=None,
                pdf_ocr_kullan=derin_ocr,
            )
    except requests.RequestException:
        pass
    return anahtar, ihale_tarihi


def geri_doldur(
    paralellik: int = 6,
    limit: int | None = None,
    *,
    zorla: bool = False,
    dosya_turu: str | None = None,
    derin_ocr: bool = False,
) -> dict[str, int]:
    kayitlar = bekleyen_ihaleler(limit, zorla=zorla, dosya_turu=dosya_turu)
    bulunan = 0
    tamamlanan = 0
    with ThreadPoolExecutor(max_workers=paralellik) as havuz:
        isler = [havuz.submit(_tek_ihale, kayit, derin_ocr) for kayit in kayitlar]
        for islem in as_completed(isler):
            anahtar, ihale_tarihi = islem.result()
            tamamlanan += 1
            simdi = datetime.now().isoformat(timespec="seconds")
            with closing(baglan()) as conn, conn:
                conn.execute("""
                    UPDATE duyuru_adaylari
                    SET ihale_tarihi=COALESCE(?, ihale_tarihi),
                        tarih_son_kontrol=?,
                        tarih_deneme_sayisi=tarih_deneme_sayisi+1,
                        tarih_hatasi=CASE WHEN ? IS NULL
                            THEN 'Tarih metin/OCR ile bulunamadı' ELSE NULL END
                    WHERE COALESCE(NULLIF(detay_url, ''), url)=?
                """, (ihale_tarihi, simdi, ihale_tarihi, anahtar))
            if ihale_tarihi:
                bulunan += 1
            if tamamlanan % 50 == 0:
                print(f"İşlenen: {tamamlanan}/{len(kayitlar)} · Tarihi bulunan: {bulunan}")
    aday_durumlarini_guncelle()
    return {"islenen": tamamlanan, "bulunan": bulunan}


def main() -> None:
    parser = argparse.ArgumentParser(description="İhalex ihale tarihi geri doldurma")
    parser.add_argument("--parallel", type=int, default=6)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="Bekleme süresini yok say")
    parser.add_argument("--file-type", choices=["html", ".docx", ".pdf", ".xlsx"])
    parser.add_argument(
        "--deep-ocr", action="store_true",
        help="Metin katmanı olmayan PDF'lerde yavaş OCR çalıştır",
    )
    args = parser.parse_args()
    if not 1 <= args.parallel <= 10:
        parser.error("--parallel 1 ile 10 arasında olmalıdır")
    print(geri_doldur(
        args.parallel,
        args.limit,
        zorla=args.force,
        dosya_turu=args.file_type,
        derin_ocr=args.deep_ocr,
    ))


if __name__ == "__main__":
    main()
