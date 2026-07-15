"""Kantin Radar ilan veritabani erisim katmani."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

DB = Path(__file__).resolve().with_name("ilanlar.db")
IHALE_GECERLILIK_GUNU = 365


def ihale_tarih_siniri() -> date:
    """Dashboard ve tarayici icin hareketli bir yillik alt siniri dondurur."""
    return date.today() - timedelta(days=IHALE_GECERLILIK_GUNU)


def baglan(db_yolu: str | Path | None = None) -> sqlite3.Connection:
    db_yolu = DB if db_yolu is None else db_yolu
    conn = sqlite3.connect(db_yolu, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def tablo_olustur() -> None:
    with closing(baglan()) as conn, conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ilanlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                baslik TEXT NOT NULL DEFAULT '', aciklama TEXT NOT NULL DEFAULT '',
                il TEXT NOT NULL DEFAULT '', ilce TEXT NOT NULL DEFAULT '',
                adres TEXT NOT NULL DEFAULT '', fiyat NUMERIC, alan REAL,
                kaynak TEXT NOT NULL DEFAULT '', url TEXT NOT NULL UNIQUE,
                puan INTEGER NOT NULL DEFAULT 0,
                durum TEXT NOT NULL DEFAULT 'yeni', eklenme_tarihi TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ilanlar_il_ilce ON ilanlar(il, ilce)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ilanlar_puan ON ilanlar(puan DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kaynaklar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kurum_adi TEXT NOT NULL,
                il TEXT NOT NULL,
                ilce TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL UNIQUE,
                kaynak_turu TEXT NOT NULL DEFAULT 'html',
                kaynak_seviyesi TEXT NOT NULL DEFAULT 'ilce',
                tarama_stratejisi TEXT NOT NULL DEFAULT 'duyuru_listesi',
                dogrulandi INTEGER NOT NULL DEFAULT 0,
                aktif INTEGER NOT NULL DEFAULT 1,
                tarama_araligi_dakika INTEGER NOT NULL DEFAULT 180,
                son_tarama TEXT,
                son_basarili_tarama TEXT,
                son_durum TEXT NOT NULL DEFAULT 'bekliyor',
                son_hata TEXT,
                eklenme_tarihi TEXT NOT NULL
            )
        """)
        mevcut_kolonlar = {
            satir[1] for satir in conn.execute("PRAGMA table_info(kaynaklar)").fetchall()
        }
        yeni_kolonlar = {
            "kaynak_seviyesi": "TEXT NOT NULL DEFAULT 'ilce'",
            "tarama_stratejisi": "TEXT NOT NULL DEFAULT 'duyuru_listesi'",
            "dogrulandi": "INTEGER NOT NULL DEFAULT 0",
        }
        for kolon, tanim in yeni_kolonlar.items():
            if kolon not in mevcut_kolonlar:
                conn.execute(f"ALTER TABLE kaynaklar ADD COLUMN {kolon} {tanim}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kaynak_taramalari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kaynak_id INTEGER NOT NULL,
                baslangic TEXT NOT NULL,
                bitis TEXT,
                durum TEXT NOT NULL,
                bulunan_baglanti INTEGER NOT NULL DEFAULT 0,
                yeni_baglanti INTEGER NOT NULL DEFAULT 0,
                hata TEXT,
                FOREIGN KEY(kaynak_id) REFERENCES kaynaklar(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS duyuru_adaylari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kaynak_id INTEGER NOT NULL,
                baslik TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                detay_url TEXT,
                liste_url TEXT,
                eslesme_turu TEXT NOT NULL DEFAULT 'baslik',
                yayin_tarihi TEXT,
                ihale_tarihi TEXT,
                tarih_son_kontrol TEXT,
                tarih_deneme_sayisi INTEGER NOT NULL DEFAULT 0,
                tarih_hatasi TEXT,
                dosya_turu TEXT,
                durum TEXT NOT NULL DEFAULT 'yeni',
                ilk_gorulme TEXT NOT NULL,
                son_gorulme TEXT NOT NULL,
                FOREIGN KEY(kaynak_id) REFERENCES kaynaklar(id) ON DELETE CASCADE
            )
        """)
        aday_kolonlari = {
            satir[1] for satir in conn.execute("PRAGMA table_info(duyuru_adaylari)").fetchall()
        }
        for kolon, tanim in {
            "detay_url": "TEXT",
            "liste_url": "TEXT",
            "eslesme_turu": "TEXT NOT NULL DEFAULT 'baslik'",
            "yayin_tarihi": "TEXT",
            "ihale_tarihi": "TEXT",
            "tarih_son_kontrol": "TEXT",
            "tarih_deneme_sayisi": "INTEGER NOT NULL DEFAULT 0",
            "tarih_hatasi": "TEXT",
        }.items():
            if kolon not in aday_kolonlari:
                conn.execute(f"ALTER TABLE duyuru_adaylari ADD COLUMN {kolon} {tanim}")
        conn.execute("""
            UPDATE duyuru_adaylari
            SET ihale_tarihi=NULL,
                durum='tarih_bekleniyor',
                tarih_son_kontrol=NULL,
                tarih_hatasi='İhale tarihi yayından sonra ve en fazla 366 gün içinde olmalı'
            WHERE ihale_tarihi IS NOT NULL
              AND yayin_tarihi IS NOT NULL
              AND (
                    date(ihale_tarihi) <= date(yayin_tarihi)
                 OR date(ihale_tarihi) > date(yayin_tarihi, '+366 days')
              )
        """)
        conn.execute("DROP TRIGGER IF EXISTS trg_ihale_tarihi_yayindan_farkli_ekle")
        conn.execute("DROP TRIGGER IF EXISTS trg_ihale_tarihi_yayindan_farkli_guncelle")
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_ihale_tarihi_yayindan_farkli_ekle
            AFTER INSERT ON duyuru_adaylari
            WHEN NEW.ihale_tarihi IS NOT NULL
             AND NEW.yayin_tarihi IS NOT NULL
             AND (
                    date(NEW.ihale_tarihi) <= date(NEW.yayin_tarihi)
                 OR date(NEW.ihale_tarihi) > date(NEW.yayin_tarihi, '+366 days')
             )
            BEGIN
                UPDATE duyuru_adaylari
                SET ihale_tarihi=NULL,
                    durum='tarih_bekleniyor',
                    tarih_son_kontrol=NULL,
                    tarih_hatasi='İhale tarihi yayından sonra ve en fazla 366 gün içinde olmalı'
                WHERE id=NEW.id;
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_ihale_tarihi_yayindan_farkli_guncelle
            AFTER UPDATE OF ihale_tarihi, yayin_tarihi ON duyuru_adaylari
            WHEN NEW.ihale_tarihi IS NOT NULL
             AND NEW.yayin_tarihi IS NOT NULL
             AND (
                    date(NEW.ihale_tarihi) <= date(NEW.yayin_tarihi)
                 OR date(NEW.ihale_tarihi) > date(NEW.yayin_tarihi, '+366 days')
             )
            BEGIN
                UPDATE duyuru_adaylari
                SET ihale_tarihi=NULL,
                    durum='tarih_bekleniyor',
                    tarih_son_kontrol=NULL,
                    tarih_hatasi='İhale tarihi yayından sonra ve en fazla 366 gün içinde olmalı'
                WHERE id=NEW.id;
            END
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kaynaklar_sira ON kaynaklar(aktif, son_tarama)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adaylar_durum ON duyuru_adaylari(durum, ilk_gorulme)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adaylar_ihale_tarihi ON duyuru_adaylari(ihale_tarihi)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ham_duyurular (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kaynak_id INTEGER NOT NULL,
                baslik TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                liste_url TEXT,
                yayin_tarihi TEXT NOT NULL,
                ilk_gorulme TEXT NOT NULL,
                son_gorulme TEXT NOT NULL,
                erisim_durumu TEXT NOT NULL DEFAULT 'bekliyor',
                dogrulama_durumu TEXT NOT NULL DEFAULT 'bekliyor',
                deneme_sayisi INTEGER NOT NULL DEFAULT 0,
                son_hata TEXT,
                FOREIGN KEY(kaynak_id) REFERENCES kaynaklar(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ham_duyurular_kuyruk
            ON ham_duyurular(yayin_tarihi, dogrulama_durumu, son_gorulme)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO ham_duyurular (
                kaynak_id, baslik, url, liste_url, yayin_tarihi,
                ilk_gorulme, son_gorulme, erisim_durumu, dogrulama_durumu
            )
            SELECT kaynak_id, baslik, url, liste_url, yayin_tarihi,
                   ilk_gorulme, son_gorulme, 'eristi', 'dogrulandi'
            FROM duyuru_adaylari
            WHERE yayin_tarihi IS NOT NULL AND TRIM(yayin_tarihi) <> ''
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alarmlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aday_id INTEGER NOT NULL,
                kanal TEXT NOT NULL DEFAULT 'telegram',
                durum TEXT NOT NULL DEFAULT 'bekliyor',
                deneme_sayisi INTEGER NOT NULL DEFAULT 0,
                olusturma_tarihi TEXT NOT NULL,
                gonderilme_tarihi TEXT,
                son_hata TEXT,
                UNIQUE(aday_id, kanal),
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alarmlar_durum ON alarmlar(durum, olusturma_tarihi)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_aboneleri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL UNIQUE,
                ad TEXT NOT NULL DEFAULT '',
                kullanici_adi TEXT NOT NULL DEFAULT '',
                sohbet_turu TEXT NOT NULL DEFAULT 'private',
                aktif INTEGER NOT NULL DEFAULT 1,
                baslama_tarihi TEXT NOT NULL,
                son_gorulme TEXT NOT NULL
            )
        """)
        telegram_abone_kolonlari = {
            satir[1]
            for satir in conn.execute("PRAGMA table_info(telegram_aboneleri)").fetchall()
        }
        for kolon, tanim in {
            "ad": "TEXT NOT NULL DEFAULT ''",
            "kullanici_adi": "TEXT NOT NULL DEFAULT ''",
            "sohbet_turu": "TEXT NOT NULL DEFAULT 'private'",
        }.items():
            if kolon not in telegram_abone_kolonlari:
                conn.execute(f"ALTER TABLE telegram_aboneleri ADD COLUMN {kolon} {tanim}")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_aboneleri_aktif
            ON telegram_aboneleri(aktif)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_teslimatlari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alarm_id INTEGER NOT NULL,
                abone_id INTEGER NOT NULL,
                durum TEXT NOT NULL DEFAULT 'bekliyor',
                deneme_sayisi INTEGER NOT NULL DEFAULT 0,
                olusturma_tarihi TEXT NOT NULL,
                gonderilme_tarihi TEXT,
                son_hata TEXT,
                UNIQUE(alarm_id, abone_id),
                FOREIGN KEY(alarm_id) REFERENCES alarmlar(id) ON DELETE CASCADE,
                FOREIGN KEY(abone_id) REFERENCES telegram_aboneleri(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_teslimatlari_kuyruk
            ON telegram_teslimatlari(durum, olusturma_tarihi)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bolgeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                il TEXT NOT NULL,
                ilce TEXT NOT NULL DEFAULT '',
                tur TEXT NOT NULL,
                UNIQUE(il, ilce)
            )
        """)


def ilan_kaydet(ilan: Mapping[str, Any]) -> bool:
    """Ilani kaydeder; yeni kayit olustuysa True, kopyaysa False dondurur."""
    url = str(ilan.get("url") or "").strip()
    if not url:
        raise ValueError("Ilan kaydi icin 'url' zorunludur")
    degerler = (
        ilan.get("baslik", ""), ilan.get("aciklama", ""),
        ilan.get("il", ""), ilan.get("ilce", ""), ilan.get("adres", ""),
        ilan.get("fiyat"), ilan.get("alan"), ilan.get("kaynak", ""), url,
        ilan.get("puan", 0), ilan.get("durum", "yeni"),
        ilan.get("eklenme_tarihi") or datetime.now().isoformat(timespec="seconds"),
    )
    with closing(baglan()) as conn, conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO ilanlar (
                baslik, aciklama, il, ilce, adres, fiyat, alan, kaynak,
                url, puan, durum, eklenme_tarihi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, degerler)
        return cursor.rowcount == 1


def ilanlari_getir() -> list[dict[str, Any]]:
    with closing(baglan()) as conn:
        satirlar = conn.execute(
            "SELECT * FROM ilanlar ORDER BY puan DESC, eklenme_tarihi DESC"
        ).fetchall()
    return [dict(satir) for satir in satirlar]


def eski_adaylari_temizle(en_eski: date | str | None = None) -> int:
    """Tarihi bilinmeyen veya bir yillik pencerenin disindaki adaylari siler."""
    if en_eski is None:
        en_eski = ihale_tarih_siniri()
    sinir = en_eski.isoformat() if isinstance(en_eski, date) else str(en_eski)
    with closing(baglan()) as conn, conn:
        cursor = conn.execute("""
            DELETE FROM duyuru_adaylari
            WHERE yayin_tarihi IS NULL
               OR TRIM(yayin_tarihi) = ''
               OR yayin_tarihi < ?
        """, (sinir,))
        silinen = cursor.rowcount
        cursor = conn.execute("""
            DELETE FROM ham_duyurular
            WHERE yayin_tarihi IS NULL
               OR TRIM(yayin_tarihi) = ''
               OR yayin_tarihi < ?
        """, (sinir,))
        return silinen + cursor.rowcount


def ham_arsiv_ozeti() -> dict[str, int]:
    """Son bir yıllık ham keşif arşivinin durum sayılarını döndürür."""
    with closing(baglan()) as conn:
        satir = conn.execute("""
            SELECT
                COUNT(*) AS toplam,
                SUM(CASE WHEN dogrulama_durumu='dogrulandi' THEN 1 ELSE 0 END) AS dogrulandi,
                SUM(CASE WHEN erisim_durumu='hata' THEN 1 ELSE 0 END) AS hatali,
                SUM(CASE WHEN dogrulama_durumu='bekliyor' THEN 1 ELSE 0 END) AS bekliyor
            FROM ham_duyurular
            WHERE yayin_tarihi >= ?
        """, (ihale_tarih_siniri().isoformat(),)).fetchone()
    return {anahtar: int(satir[anahtar] or 0) for anahtar in satir.keys()}


def aday_durumlarini_guncelle() -> int:
    """İhale tarihine göre aktif/pasif durumunu günlük olarak yeniler."""
    with closing(baglan()) as conn, conn:
        conn.execute("""
            UPDATE duyuru_adaylari
            SET ihale_tarihi=NULL,
                tarih_son_kontrol=NULL,
                tarih_hatasi='İhale tarihi yayından sonra ve en fazla 366 gün içinde olmalı'
            WHERE ihale_tarihi IS NOT NULL
              AND yayin_tarihi IS NOT NULL
              AND (
                    date(ihale_tarihi) <= date(yayin_tarihi)
                 OR date(ihale_tarihi) > date(yayin_tarihi, '+366 days')
              )
        """)
        cursor = conn.execute("""
            UPDATE duyuru_adaylari
            SET durum = CASE
                WHEN ihale_tarihi IS NULL OR TRIM(ihale_tarihi) = ''
                    THEN 'tarih_bekleniyor'
                WHEN date(ihale_tarihi) >= date('now', 'localtime')
                    THEN 'aktif'
                ELSE 'pasif'
            END
        """)
        return cursor.rowcount


if __name__ == "__main__":
    tablo_olustur()
    print("Veritabani hazir")
