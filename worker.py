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
from ihale_belge_arsivi import (
    arsivi_geri_doldur,
    kayitli_metinleri_yeniden_ayristir,
    toplu_ilan_belgelerini_ayir,
    yerel_arsivi_yeniden_isle,
)
from analiz_motoru import tamamlanan_belgeleri_analiz_et
from tarama_kontrolu import DURUM_DOSYASI, manuel_tarama_istegini_al
from veritabani import aday_durumlarini_guncelle, eski_adaylari_temizle, tablo_olustur
from telegram_alarm import (
    TelegramKurulumHatasi,
    bekleyenleri_gonder,
    telegram_hazir,
)

KOK = Path(__file__).resolve().parent
LOG_DOSYASI = KOK / "worker.log"
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


def belge_arsiv_turu(limit: int = 2) -> int:
    try:
        # Yeni ayrıştırma kuralları önce saklanan metinde denenir; OCR tekrarlanmaz.
        metin_sonucu = kayitli_metinleri_yeniden_ayristir(
            limit=max(10, limit * 10)
        )
        if metin_sonucu["islenen"] or metin_sonucu["hata"]:
            logging.info(
                "Saklanan metin ayrıştırma: %s işlendi, %s tamamlandı, %s eksik, %s hata",
                metin_sonucu["islenen"], metin_sonucu["tamamlanan"],
                metin_sonucu["eksik"], metin_sonucu["hata"],
            )
        # Yeni ve aktif ilanlar her zaman geçmiş arşiv düzenlemesinden önce gelir.
        sonuc = arsivi_geri_doldur(limit=limit)
        if sonuc["islenen"] or sonuc["hata"]:
            logging.info(
                "Belge arşivi: %s işlendi, %s analiz edildi, %s hata",
                sonuc["islenen"], sonuc["analiz_edilen"], sonuc["hata"],
            )
        ayrilan = toplu_ilan_belgelerini_ayir(limit=max(2, limit * 2))
        if ayrilan["ayrilan"] or ayrilan["temizlenen_parent"]:
            logging.info(
                "Toplu ilan ayrıştırma: %s belge okul kaydına taşındı, %s ana analiz temizlendi",
                ayrilan["ayrilan"], ayrilan["temizlenen_parent"],
            )
        yeniden = yerel_arsivi_yeniden_isle(limit=limit)
        if yeniden["islenen"] or yeniden["hata"]:
            logging.info(
                "Yerel belge yeniden işleme: %s işlendi, %s hazır, %s hata",
                yeniden["islenen"], yeniden["analiz_edilen"], yeniden["hata"],
            )
        yatirim = tamamlanan_belgeleri_analiz_et(limit=25)
        if yatirim["islenen"]:
            logging.info("Yatırım analizi: %s yeni rapor", yatirim["islenen"])
        return sonuc["islenen"]
    except Exception:
        logging.exception("Belge arşiv turu tamamlanamadı")
        return 0


def tarama_turu(
    limit: int | None = 20,
    paralellik: int = 6,
    tetikleyici: str = "planli",
) -> int:
    baslangic = datetime.now().isoformat(timespec="seconds")
    temizlenen = eski_adaylari_temizle()
    aday_durumlarini_guncelle()
    if temizlenen:
        logging.info("Tarih penceresi disindaki %s kayit temizlendi", temizlenen)
    yeni_toplam = 0
    kaynaklar = tum_aktif_kaynaklar() if limit is None else siradaki_kaynaklar(limit)
    tamamlanan = 0
    hata_sayisi = 0
    durum_yaz(
        durum="tariyor",
        son_baslangic=baslangic,
        hata=None,
        tetikleyici=tetikleyici,
        kaynak_sayisi=len(kaynaklar),
        tamamlanan_kaynak=0,
        anlik_yeni_kayit=0,
        hata_sayisi=0,
    )
    logging.info("MEB taraması başladı: %s kaynak", len(kaynaklar))
    with ThreadPoolExecutor(max_workers=paralellik) as havuz:
        isler = {havuz.submit(_tek_kaynak, kaynak): kaynak for kaynak in kaynaklar}
        for islem in as_completed(isler):
            kaynak = isler[islem]
            try:
                yeni_toplam += islem.result()
            except Exception:
                hata_sayisi += 1
                logging.exception("Kaynak taranamadı: %s", kaynak.get("kurum_adi"))

            tamamlanan += 1
            durum_yaz(
                tamamlanan_kaynak=tamamlanan,
                anlik_yeni_kayit=yeni_toplam,
                hata_sayisi=hata_sayisi,
                son_kaynak=str(kaynak.get("kurum_adi") or ""),
            )

    bitis = datetime.now().isoformat(timespec="seconds")
    durum_yaz(
        durum="sonuclaniyor",
        son_bitis=bitis,
        son_yeni_kayit=yeni_toplam,
        kaynak_sayisi=len(kaynaklar),
        tamamlanan_kaynak=len(kaynaklar),
        anlik_yeni_kayit=yeni_toplam,
        hata_sayisi=hata_sayisi,
        hata=None,
    )
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
    belge_arsiv_turu(limit=2)
    durum_yaz(durum="bekliyor", son_bitis=datetime.now().isoformat(timespec="seconds"))
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
        manuel_calisti = False
        son_telegram_turu = 0.0
        son_belge_arsiv_turu = 0.0
        while not duruyor:
            istek = manuel_tarama_istegini_al()
            if istek is not None:
                logging.info("Yonetim panelinden manuel tam tarama istendi")
                try:
                    tarama_turu(
                        limit=None,
                        paralellik=paralellik,
                        tetikleyici="manuel",
                    )
                except Exception as hata:
                    logging.exception("Manuel tam tarama basarisiz")
                    durum_yaz(durum="hata", hata=str(hata))
                manuel_calisti = True
                break
            kalan = (sonraki - datetime.now(TURKIYE_SAATI)).total_seconds()
            if kalan <= 0:
                break
            simdi = time.monotonic()
            if simdi - son_telegram_turu >= 30:
                telegram_turu()
                son_telegram_turu = simdi
            if simdi - son_belge_arsiv_turu >= 45:
                belge_arsiv_turu(limit=2)
                son_belge_arsiv_turu = time.monotonic()
            _kesilebilir_bekle(min(2, max(1, int(kalan))))
        if duruyor:
            break
        if manuel_calisti:
            continue
        try:
            tarama_turu(limit=None, paralellik=paralellik, tetikleyici="planli")
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
