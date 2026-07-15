"""Doğrulanmış MEB kaynaklarını periyodik tarayan İhalex işçisi."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from meb_kaynaklari import siradaki_kaynaklar, tum_aktif_kaynaklar
from meb_tarama_servisi import kaynak_tara
from ihale_tarihi_geri_doldur import geri_doldur
from veritabani import aday_durumlarini_guncelle, eski_adaylari_temizle, tablo_olustur
from telegram_alarm import (
    TelegramKurulumHatasi,
    bekleyenleri_gonder,
    telegram_hazir,
)

KOK = Path(__file__).resolve().parent
LOG_DOSYASI = KOK / "worker.log"
DURUM_DOSYASI = KOK / "worker_durumu.json"
duruyor = False
TURKIYE_SAATI = ZoneInfo("Europe/Istanbul")
TARAMA_SAATLERI = ((11, 59), (23, 59))


def log_ayarla() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_DOSYASI, encoding="utf-8"), logging.StreamHandler()],
    )


def durum_yaz(**degerler: object) -> None:
    mevcut = {}
    if DURUM_DOSYASI.exists():
        try:
            mevcut = json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    mevcut.update(degerler)
    gecici = DURUM_DOSYASI.with_suffix(".tmp")
    gecici.write_text(json.dumps(mevcut, ensure_ascii=False, indent=2), encoding="utf-8")
    gecici.replace(DURUM_DOSYASI)


def _tek_kaynak(kaynak: dict[str, object]) -> int:
    bulunan, yeni = kaynak_tara(kaynak)
    logging.info("%s: %s bağlantı, %s yeni", kaynak["kurum_adi"], bulunan, yeni)
    return yeni


def telegram_turu() -> int:
    if not telegram_hazir():
        return 0
    try:
        gonderilen = bekleyenleri_gonder(limit=100)
        if gonderilen:
            logging.info("Telegram'a %s abone mesajı gönderildi", gonderilen)
        return gonderilen
    except TelegramKurulumHatasi as hata:
        logging.warning("Telegram abonelik turu tamamlanamadı: %s", hata)
        return 0


def tarama_turu(limit: int | None = 20, paralellik: int = 6) -> int:
    baslangic = datetime.now().isoformat(timespec="seconds")
    durum_yaz(durum="tariyor", son_baslangic=baslangic, hata=None)
    temizlenen = eski_adaylari_temizle()
    aday_durumlarini_guncelle()
    if temizlenen:
        logging.info("Tarih penceresi disindaki %s kayit temizlendi", temizlenen)
    yeni_toplam = 0
    kaynaklar = tum_aktif_kaynaklar() if limit is None else siradaki_kaynaklar(limit)
    logging.info("MEB taraması başladı: %s kaynak", len(kaynaklar))
    with ThreadPoolExecutor(max_workers=paralellik) as havuz:
        isler = {havuz.submit(_tek_kaynak, kaynak): kaynak for kaynak in kaynaklar}
        for islem in as_completed(isler):
            kaynak = isler[islem]
            try:
                yeni_toplam += islem.result()
            except Exception:
                logging.exception("Kaynak taranamadı: %s", kaynak.get("kurum_adi"))

    bitis = datetime.now().isoformat(timespec="seconds")
    durum_yaz(durum="bekliyor", son_bitis=bitis, son_yeni_kayit=yeni_toplam,
               kaynak_sayisi=len(kaynaklar), hata=None)
    tarih_limiti = max(50, yeni_toplam * 5) if limit is None else 5
    tarih_sonucu = geri_doldur(
        paralellik=min(paralellik, 2),
        limit=tarih_limiti,
    )
    aday_durumlarini_guncelle()
    telegram_turu()
    logging.info(
        "İhale tarihi kuyruğu: %s işlendi, %s tarih bulundu",
        tarih_sonucu["islenen"], tarih_sonucu["bulunan"],
    )
    if limit is None:
        gecmis_sonucu = geri_doldur(
            paralellik=min(paralellik, 2),
            limit=150,
        )
        logging.info(
            "Geçmiş tarih kuyruğu: %s işlendi, %s tarih bulundu",
            gecmis_sonucu["islenen"], gecmis_sonucu["bulunan"],
        )
    return yeni_toplam


def sonraki_tarama_zamani(simdi: datetime | None = None) -> datetime:
    simdi = simdi or datetime.now(TURKIYE_SAATI)
    if simdi.tzinfo is None:
        simdi = simdi.replace(tzinfo=TURKIYE_SAATI)
    for saat, dakika in TARAMA_SAATLERI:
        aday = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
        if aday >= simdi:
            return aday
    yarin = simdi + timedelta(days=1)
    saat, dakika = TARAMA_SAATLERI[0]
    return yarin.replace(hour=saat, minute=dakika, second=0, microsecond=0)


def _kesilebilir_bekle(saniye: int) -> None:
    for _ in range(max(0, saniye)):
        if duruyor:
            break
        time.sleep(1)


def planli_dongu(paralellik: int) -> None:
    while not duruyor:
        sonraki = sonraki_tarama_zamani()
        durum_yaz(
            durum="zamanlandi",
            sonraki_tarama=sonraki.isoformat(timespec="minutes"),
            tarama_programi=["11:59", "23:59"],
        )
        while not duruyor:
            kalan = (sonraki - datetime.now(TURKIYE_SAATI)).total_seconds()
            if kalan <= 0:
                break
            telegram_turu()
            _kesilebilir_bekle(min(30, max(1, int(kalan))))
        if duruyor:
            break
        try:
            tarama_turu(limit=None, paralellik=paralellik)
        except Exception as hata:
            logging.exception("Planlı tam tarama başarısız")
            durum_yaz(durum="hata", hata=str(hata))


def durdur(_isaret: int, _cerceve: object) -> None:
    global duruyor
    duruyor = True
    durum_yaz(durum="duruyor")


def main() -> None:
    parser = argparse.ArgumentParser(description="İhalex planlı MEB tarama işçisi")
    parser.add_argument("--once", action="store_true", help="Bütün kaynakları bir kez tara ve çık")
    parser.add_argument("--parallel", type=int, default=6, help="Eşzamanlı istek sayısı (1-10)")
    args = parser.parse_args()
    if not 1 <= args.parallel <= 10:
        parser.error("--parallel 1 ile 10 arasında olmalıdır")
    log_ayarla()
    tablo_olustur()
    signal.signal(signal.SIGINT, durdur)
    signal.signal(signal.SIGTERM, durdur)
    if args.once:
        try:
            tarama_turu(limit=None, paralellik=args.parallel)
        except Exception as hata:
            logging.exception("Tek seferlik tam tarama başarısız")
            durum_yaz(durum="hata", hata=str(hata))
        return
    planli_dongu(args.parallel)


if __name__ == "__main__":
    main()
