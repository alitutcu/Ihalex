"""Kantin Radar ilan veritabani erisim katmani."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from okul_adi_servisi import okul_adi_temizle
from surum_bilgisi import SURUM_GECMISI

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


def okul_adlarini_temizle(db_yolu: str | Path | None = None) -> int:
    """Belge ve manuel düzeltme kayıtlarındaki okul adlarını yerinde normalleştir."""
    degisen = 0
    with closing(baglan(db_yolu)) as conn, conn:
        for tablo in ("ilan_analiz_verileri", "analiz_manuel_duzeltmeleri"):
            mevcut = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (tablo,),
            ).fetchone()
            if not mevcut:
                continue
            for satir in conn.execute(
                f"SELECT aday_id, okul_adi FROM {tablo} "
                "WHERE NULLIF(TRIM(okul_adi), '') IS NOT NULL"
            ).fetchall():
                eski = str(satir["okul_adi"])
                yeni = okul_adi_temizle(eski)
                if yeni and yeni != eski:
                    conn.execute(
                        f"UPDATE {tablo} SET okul_adi=? WHERE aday_id=?",
                        (yeni, int(satir["aday_id"])),
                    )
                    degisen += 1
    return degisen


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
            UPDATE duyuru_adaylari AS ek
            SET baslik=COALESCE((
                SELECT NULLIF(TRIM(parent.baslik), '')
                FROM duyuru_adaylari parent
                WHERE parent.url=ek.detay_url
                LIMIT 1
            ), ek.baslik)
            WHERE ek.eslesme_turu='ek_dosya'
              AND (
                   LOWER(ek.baslik) LIKE '%tıklay%'
                OR LOWER(ek.baslik) LIKE '%tiklay%'
              )
        """)
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
            CREATE TABLE IF NOT EXISTS ihale_belgeleri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aday_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                yerel_yol TEXT,
                sha256 TEXT,
                boyut INTEGER,
                mime_turu TEXT,
                durum TEXT NOT NULL DEFAULT 'bekliyor',
                son_hata TEXT,
                ilk_indirme TEXT,
                son_kontrol TEXT NOT NULL,
                UNIQUE(aday_id, url),
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ihale_belgeleri_durum
            ON ihale_belgeleri(durum, son_kontrol)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ihale_belgeleri_sha256
            ON ihale_belgeleri(sha256)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ilan_analiz_verileri (
                aday_id INTEGER PRIMARY KEY,
                okul_adi TEXT,
                okul_turu TEXT,
                adres TEXT,
                ogrenci_sayisi INTEGER,
                personel_sayisi INTEGER,
                muhammen_bedel NUMERIC,
                muhammen_bedel_aylik NUMERIC,
                muhammen_bedel_yillik NUMERIC,
                muhammen_bedel_donemi TEXT,
                sartname_bedeli NUMERIC,
                gecici_teminat NUMERIC,
                kantin_alani_m2 REAL,
                kira_suresi_ay INTEGER,
                belge_guveni INTEGER NOT NULL DEFAULT 0,
                kaynak_belge_id INTEGER,
                veri_yontemi TEXT NOT NULL DEFAULT 'belge_metni',
                ham_metin TEXT,
                guncelleme_tarihi TEXT NOT NULL,
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE,
                FOREIGN KEY(kaynak_belge_id) REFERENCES ihale_belgeleri(id) ON DELETE SET NULL
            )
        """)
        analiz_kolonlari = {
            satir[1]
            for satir in conn.execute(
                "PRAGMA table_info(ilan_analiz_verileri)"
            ).fetchall()
        }
        for kolon, tanim in {
            "okul_turu": "TEXT",
            "muhammen_bedel_aylik": "NUMERIC",
            "muhammen_bedel_yillik": "NUMERIC",
            "muhammen_bedel_donemi": "TEXT",
        }.items():
            if kolon not in analiz_kolonlari:
                conn.execute(
                    f"ALTER TABLE ilan_analiz_verileri ADD COLUMN {kolon} {tanim}"
                )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bolge_verileri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                il TEXT NOT NULL,
                ilce TEXT NOT NULL DEFAULT '',
                ekonomik_katsayi REAL NOT NULL DEFAULT 1.00,
                gelir_katsayi REAL NOT NULL DEFAULT 1.00,
                nufus_katsayi REAL NOT NULL DEFAULT 1.00,
                ticari_hareketlilik_katsayi REAL NOT NULL DEFAULT 1.00,
                kira_endeksi REAL,
                ses_skoru REAL,
                veri_kaynagi TEXT NOT NULL DEFAULT 'Henüz bağlanmadı',
                guncelleme_tarihi TEXT NOT NULL,
                UNIQUE(il, ilce)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bolge_verileri_il_ilce
            ON bolge_verileri(il, ilce)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO bolge_verileri(
                il, ilce, ekonomik_katsayi, gelir_katsayi, nufus_katsayi,
                ticari_hareketlilik_katsayi, veri_kaynagi, guncelleme_tarihi
            )
            SELECT DISTINCT il, COALESCE(ilce, ''), 1.00, 1.00, 1.00, 1.00,
                   'Henüz bağlanmadı', datetime('now', 'localtime')
            FROM kaynaklar WHERE TRIM(il) <> ''
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_kaynak_bolge_varsayilani_ekle
            AFTER INSERT ON kaynaklar
            WHEN TRIM(NEW.il) <> ''
            BEGIN
                INSERT OR IGNORE INTO bolge_verileri(
                    il, ilce, ekonomik_katsayi, gelir_katsayi, nufus_katsayi,
                    ticari_hareketlilik_katsayi, veri_kaynagi, guncelleme_tarihi
                ) VALUES (
                    NEW.il, COALESCE(NEW.ilce, ''), 1.00, 1.00, 1.00, 1.00,
                    'Henüz bağlanmadı', datetime('now', 'localtime')
                );
            END
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kantin_yatirim_analizleri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aday_id INTEGER NOT NULL UNIQUE,
                motor_surumu TEXT NOT NULL,
                girdi_json TEXT NOT NULL,
                varsayim_json TEXT NOT NULL,
                sonuc_json TEXT NOT NULL,
                tahmini_aylik_ciro NUMERIC NOT NULL,
                tahmini_yillik_ciro NUMERIC NOT NULL DEFAULT 0,
                ogrenci_sayisi INTEGER,
                okul_tipi TEXT,
                okul_tipi_katsayisi REAL,
                baz_personel_sayisi INTEGER,
                onerilen_calisan_sayisi INTEGER,
                brut_maas NUMERIC,
                aylik_calisma_saati REAL,
                tahmini_net_maas NUMERIC,
                sgk_maliyeti NUMERIC,
                net_maas_sgk_toplami NUMERIC,
                yan_hak_maliyeti NUMERIC,
                kisi_basi_personel_maliyeti NUMERIC,
                toplam_personel_gideri NUMERIC,
                personel_hesaplama_modu TEXT,
                manuel_calisan_sayisi INTEGER,
                tahmini_net_kar NUMERIC NOT NULL,
                kira_ciro_orani REAL NOT NULL,
                risk_skoru REAL NOT NULL,
                risk_seviyesi TEXT NOT NULL,
                yatirim_skoru INTEGER NOT NULL,
                maksimum_teklif NUMERIC NOT NULL,
                tahmini_ihale_sonucu_kira NUMERIC NOT NULL DEFAULT 0,
                tahmini_ihale_azami_orani REAL NOT NULL DEFAULT 0.80,
                tahmini_ihale_sonrasi_net_kar NUMERIC NOT NULL DEFAULT 0,
                tahmini_ihale_sonrasi_net_kar_marji REAL NOT NULL DEFAULT 0,
                azami_kira_sonrasi_net_kar NUMERIC NOT NULL DEFAULT 0,
                azami_kira_sonrasi_net_kar_marji REAL NOT NULL DEFAULT 0,
                yorum TEXT NOT NULL,
                olusturma_tarihi TEXT NOT NULL,
                guncelleme_tarihi TEXT NOT NULL,
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE
            )
        """)
        yatirim_kolonlari = {
            satir[1]
            for satir in conn.execute(
                "PRAGMA table_info(kantin_yatirim_analizleri)"
            ).fetchall()
        }
        for kolon, tanim in {
            "tahmini_yillik_ciro": "NUMERIC NOT NULL DEFAULT 0",
            "ogrenci_sayisi": "INTEGER",
            "okul_tipi": "TEXT",
            "okul_tipi_katsayisi": "REAL",
            "baz_personel_sayisi": "INTEGER",
            "onerilen_calisan_sayisi": "INTEGER",
            "brut_maas": "NUMERIC",
            "aylik_calisma_saati": "REAL",
            "tahmini_net_maas": "NUMERIC",
            "sgk_maliyeti": "NUMERIC",
            "net_maas_sgk_toplami": "NUMERIC",
            "yan_hak_maliyeti": "NUMERIC",
            "kisi_basi_personel_maliyeti": "NUMERIC",
            "toplam_personel_gideri": "NUMERIC",
            "personel_hesaplama_modu": "TEXT",
            "manuel_calisan_sayisi": "INTEGER",
            "tahmini_ihale_sonucu_kira": "NUMERIC NOT NULL DEFAULT 0",
            "tahmini_ihale_azami_orani": "REAL NOT NULL DEFAULT 0.80",
            "tahmini_ihale_sonrasi_net_kar": "NUMERIC NOT NULL DEFAULT 0",
            "tahmini_ihale_sonrasi_net_kar_marji": "REAL NOT NULL DEFAULT 0",
            "azami_kira_sonrasi_net_kar": "NUMERIC NOT NULL DEFAULT 0",
            "azami_kira_sonrasi_net_kar_marji": "REAL NOT NULL DEFAULT 0",
        }.items():
            if kolon not in yatirim_kolonlari:
                conn.execute(
                    f"ALTER TABLE kantin_yatirim_analizleri ADD COLUMN {kolon} {tanim}"
                )
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kantin_yatirim_skoru
            ON kantin_yatirim_analizleri(yatirim_skoru DESC, risk_skoru)
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_yeni_analiz_motorunu_koru
            BEFORE UPDATE OF motor_surumu ON kantin_yatirim_analizleri
            WHEN CAST(REPLACE(NEW.motor_surumu, '.', '') AS INTEGER)
                 < CAST(REPLACE(OLD.motor_surumu, '.', '') AS INTEGER)
            BEGIN
                SELECT RAISE(IGNORE);
            END
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analiz_manuel_duzeltmeleri (
                aday_id INTEGER PRIMARY KEY,
                il TEXT,
                ilce TEXT,
                okul_adi TEXT,
                okul_turu TEXT,
                ogrenci_sayisi INTEGER,
                personel_sayisi INTEGER,
                muhammen_bedel_aylik NUMERIC,
                muhammen_bedel_yillik NUMERIC,
                ogrenci_donusum_orani REAL,
                donusum_modeli_surumu TEXT NOT NULL
                    DEFAULT '2026-07-16-okul-turu-yuzde10-v2',
                ortalama_ogrenci_harcamasi NUMERIC,
                yillik_egitim_gunu INTEGER,
                hedef_net_kar_orani REAL,
                tahmini_ihale_azami_orani REAL,
                otomatik_personel_hesapla INTEGER,
                manuel_calisan_sayisi INTEGER,
                asgari_ucret NUMERIC,
                net_asgari_ucret NUMERIC,
                brut_maas NUMERIC,
                aylik_calisma_saati REAL,
                tam_zamanli_aylik_saat REAL,
                sgk_isveren_orani REAL,
                issizlik_isveren_orani REAL,
                yemek_maliyeti NUMERIC,
                yol_maliyeti NUMERIC,
                diger_yan_haklar NUMERIC,
                duzeltme_notu TEXT,
                duzelten TEXT NOT NULL DEFAULT 'admin',
                olusturma_tarihi TEXT NOT NULL,
                guncelleme_tarihi TEXT NOT NULL,
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE
            )
        """)
        manuel_kolonlari = {
            satir[1]
            for satir in conn.execute(
                "PRAGMA table_info(analiz_manuel_duzeltmeleri)"
            ).fetchall()
        }
        if "donusum_modeli_surumu" not in manuel_kolonlari:
            conn.execute(
                "ALTER TABLE analiz_manuel_duzeltmeleri "
                "ADD COLUMN donusum_modeli_surumu TEXT"
            )
        # Eski editör genel %60 oranını bazı okul türlerine de yazıyordu.
        # Bu sürümlü ve idempotent göç yalnız eski kayıtları okul türünün yeni
        # (%10 azaltılmış) ortalamasına taşır; bundan sonra kaydedilen manuel
        # tercihler v2 etiketiyle korunur.
        conn.execute("""
            UPDATE analiz_manuel_duzeltmeleri
            SET ogrenci_donusum_orani=CASE
                    WHEN LOWER(REPLACE(okul_turu, 'İ', 'i')) LIKE '%ilkokul%'
                        THEN 0.36
                    WHEN LOWER(REPLACE(okul_turu, 'İ', 'i')) LIKE '%ortaokul%'
                        THEN 0.54
                    WHEN LOWER(REPLACE(okul_turu, 'İ', 'i')) LIKE '%meslek%lise%'
                        THEN 0.72
                    WHEN LOWER(REPLACE(okul_turu, 'İ', 'i')) LIKE '%lise%'
                        THEN 0.6525
                    ELSE ROUND(COALESCE(ogrenci_donusum_orani, 0.55) * 0.90, 6)
                END,
                donusum_modeli_surumu='2026-07-16-okul-turu-yuzde10-v2'
            WHERE COALESCE(donusum_modeli_surumu, '')<>
                  '2026-07-16-okul-turu-yuzde10-v2'
        """)
        if "yillik_egitim_gunu" not in manuel_kolonlari:
            conn.execute(
                "ALTER TABLE analiz_manuel_duzeltmeleri "
                "ADD COLUMN yillik_egitim_gunu INTEGER"
            )
        if "hedef_net_kar_orani" not in manuel_kolonlari:
            conn.execute(
                "ALTER TABLE analiz_manuel_duzeltmeleri "
                "ADD COLUMN hedef_net_kar_orani REAL"
            )
        for kolon, tanim in {
            "il": "TEXT",
            "ilce": "TEXT",
            "tahmini_ihale_azami_orani": "REAL",
            "otomatik_personel_hesapla": "INTEGER",
            "manuel_calisan_sayisi": "INTEGER",
            "asgari_ucret": "NUMERIC",
            "net_asgari_ucret": "NUMERIC",
            "brut_maas": "NUMERIC",
            "aylik_calisma_saati": "REAL",
            "tam_zamanli_aylik_saat": "REAL",
            "sgk_isveren_orani": "REAL",
            "issizlik_isveren_orani": "REAL",
            "yemek_maliyeti": "NUMERIC",
            "yol_maliyeti": "NUMERIC",
            "diger_yan_haklar": "NUMERIC",
        }.items():
            if kolon not in manuel_kolonlari:
                conn.execute(
                    f"ALTER TABLE analiz_manuel_duzeltmeleri ADD COLUMN {kolon} {tanim}"
                )
        conn.execute("""
            UPDATE ilan_analiz_verileri
            SET muhammen_bedel_yillik=ROUND(muhammen_bedel_aylik * 9, 2)
            WHERE muhammen_bedel_donemi='aylik'
              AND muhammen_bedel_aylik IS NOT NULL
              AND ABS(COALESCE(muhammen_bedel_yillik, 0)
                      - muhammen_bedel_aylik * 12) < 0.01
        """)
        conn.execute("""
            UPDATE analiz_manuel_duzeltmeleri
            SET muhammen_bedel_yillik=ROUND(muhammen_bedel_aylik * 9, 2)
            WHERE muhammen_bedel_aylik IS NOT NULL
              AND ABS(COALESCE(muhammen_bedel_yillik, 0)
                      - muhammen_bedel_aylik * 12) < 0.01
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analiz_manuel_gecmisi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aday_id INTEGER NOT NULL,
                islem TEXT NOT NULL,
                onceki_json TEXT,
                yeni_json TEXT,
                duzelten TEXT NOT NULL DEFAULT 'admin',
                islem_tarihi TEXT NOT NULL,
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analiz_ogrenme_ornekleri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aday_id INTEGER NOT NULL,
                kaynak_id INTEGER NOT NULL,
                belge_id INTEGER,
                belge_degerleri_json TEXT NOT NULL,
                dogrulanmis_degerler_json TEXT NOT NULL,
                degisen_alanlar_json TEXT NOT NULL,
                metin_parmak_izi TEXT,
                duzelten TEXT NOT NULL DEFAULT 'admin',
                olusturma_tarihi TEXT NOT NULL,
                uygulanma_sayisi INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(aday_id) REFERENCES duyuru_adaylari(id) ON DELETE CASCADE,
                FOREIGN KEY(kaynak_id) REFERENCES kaynaklar(id) ON DELETE CASCADE,
                FOREIGN KEY(belge_id) REFERENCES ihale_belgeleri(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_analiz_ogrenme_kaynak
            ON analiz_ogrenme_ornekleri(kaynak_id, olusturma_tarihi DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sistem_surumleri (
                surum_kodu TEXT PRIMARY KEY,
                surum_adi TEXT NOT NULL,
                yayin_tarihi TEXT NOT NULL,
                analiz_motoru_surumu TEXT NOT NULL,
                git_etiketi TEXT NOT NULL,
                aciklama TEXT NOT NULL
            )
        """)
        for surum in SURUM_GECMISI:
            conn.execute("""
                INSERT INTO sistem_surumleri(
                    surum_kodu, surum_adi, yayin_tarihi,
                    analiz_motoru_surumu, git_etiketi, aciklama
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(surum_kodu) DO UPDATE SET
                    surum_adi=excluded.surum_adi,
                    yayin_tarihi=excluded.yayin_tarihi,
                    analiz_motoru_surumu=excluded.analiz_motoru_surumu,
                    git_etiketi=excluded.git_etiketi,
                    aciklama=excluded.aciklama
            """, (
                surum["surum_kodu"], surum["surum_adi"],
                surum["yayin_tarihi"], surum["analiz_motoru_surumu"],
                surum["git_etiketi"], surum["aciklama"],
            ))
        conn.execute("DROP VIEW IF EXISTS ihale_analiz_kayitlari")
        conn.execute("""
            CREATE VIEW ihale_analiz_kayitlari AS
            SELECT d.id AS aday_id,
                   COALESCE(NULLIF(TRIM(m.okul_adi), ''), a.okul_adi) AS okul_adi,
                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu) AS okul_turu,
                   k.il,
                   COALESCE(k.ilce, '') AS ilce,
                   a.adres,
                   COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) AS ogrenci_sayisi,
                   COALESCE(m.personel_sayisi, a.personel_sayisi) AS personel_sayisi,
                   COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik)
                       AS muhammen_bedel_aylik,
                   COALESCE(m.muhammen_bedel_yillik, a.muhammen_bedel_yillik)
                       AS muhammen_bedel_yillik,
                   a.muhammen_bedel_donemi,
                   a.sartname_bedeli,
                   a.gecici_teminat,
                   a.kantin_alani_m2,
                   a.kira_suresi_ay,
                   a.belge_guveni,
                   d.baslik,
                   d.url AS belge_url,
                   d.yayin_tarihi,
                   d.ihale_tarihi,
                   d.durum,
                   CASE WHEN NULLIF(TRIM(COALESCE(m.okul_adi, a.okul_adi)), '') IS NOT NULL
                          AND NULLIF(TRIM(COALESCE(m.okul_turu, a.okul_turu)), '') IS NOT NULL
                          AND COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) IS NOT NULL
                          AND COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik) IS NOT NULL
                        THEN 1 ELSE 0 END AS analize_hazir,
                   CASE WHEN m.aday_id IS NULL THEN 0 ELSE 1 END AS manuel_duzeltme,
                   m.ogrenci_donusum_orani,
                   m.ortalama_ogrenci_harcamasi,
                   m.yillik_egitim_gunu,
                   m.hedef_net_kar_orani,
                   m.duzeltme_notu,
                   y.yatirim_skoru,
                   y.risk_seviyesi,
                   y.tahmini_aylik_ciro,
                   y.tahmini_yillik_ciro,
                   y.okul_tipi_katsayisi,
                   y.baz_personel_sayisi,
                   y.onerilen_calisan_sayisi,
                   y.kisi_basi_personel_maliyeti,
                   y.net_maas_sgk_toplami,
                   y.toplam_personel_gideri,
                   y.personel_hesaplama_modu,
                   y.tahmini_net_kar,
                   y.maksimum_teklif,
                   a.guncelleme_tarihi
            FROM ilan_analiz_verileri a
            JOIN duyuru_adaylari d ON d.id=a.aday_id
            JOIN kaynaklar k ON k.id=d.kaynak_id
            LEFT JOIN analiz_manuel_duzeltmeleri m ON m.aday_id=d.id
            LEFT JOIN kantin_yatirim_analizleri y ON y.aday_id=d.id
        """)
        conn.execute("""
            UPDATE ihale_belgeleri
            SET durum='analiz_bekliyor',
                son_hata='Okul adı, okul türü, öğrenci sayısı ve aylık muhammen bedel yeniden işlenecek'
            WHERE durum='analiz_edildi'
              AND EXISTS (
                  SELECT 1
                  FROM ilan_analiz_verileri a
                  LEFT JOIN analiz_manuel_duzeltmeleri m ON m.aday_id=a.aday_id
                  WHERE a.aday_id=ihale_belgeleri.aday_id
                    AND (
                           NULLIF(TRIM(COALESCE(m.okul_adi, a.okul_adi)), '') IS NULL
                        OR NULLIF(TRIM(COALESCE(m.okul_turu, a.okul_turu)), '') IS NULL
                        OR COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) IS NULL
                        OR COALESCE(
                               m.muhammen_bedel_aylik,
                               a.muhammen_bedel_aylik
                           ) IS NULL
                    )
              )
        """)
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
    """Kalıcı arşiv politikası gereği ilan ve ham duyuru kayıtlarını silmez."""
    del en_eski
    return 0


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
