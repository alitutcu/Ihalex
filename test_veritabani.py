import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import veritabani
import meb_tarama_servisi


class VeritabaniTesti(unittest.TestCase):
    def setUp(self):
        self.gecici_klasor = tempfile.TemporaryDirectory()
        self.db = Path(self.gecici_klasor.name) / "test.db"
        self.db_yamasi = patch.object(veritabani, "DB", self.db)
        self.db_yamasi.start()
        veritabani.tablo_olustur()

    def tearDown(self):
        self.db_yamasi.stop()
        self.gecici_klasor.cleanup()

    def test_kayit_ve_kopya_engelleme(self):
        ilan = {"baslik": "Okul kantini", "url": "https://ornek/1", "puan": 80}
        self.assertTrue(veritabani.ilan_kaydet(ilan))
        self.assertFalse(veritabani.ilan_kaydet(ilan))
        kayitlar = veritabani.ilanlari_getir()
        self.assertEqual(1, len(kayitlar))
        self.assertEqual("Okul kantini", kayitlar[0]["baslik"])

    def test_urlsiz_ilan_reddedilir(self):
        with self.assertRaises(ValueError):
            veritabani.ilan_kaydet({"baslik": "Eksik ilan"})

    def test_ihalex_surumu_tarih_ve_etiketiyle_saklanir(self):
        with closing(veritabani.baglan()) as conn:
            onceki_surum = conn.execute("""
                SELECT surum_kodu, surum_adi, yayin_tarihi, git_etiketi
                FROM sistem_surumleri WHERE surum_kodu='v1.1.0'
            """).fetchone()
            guncel_surum = conn.execute("""
                SELECT surum_kodu, surum_adi, yayin_tarihi, git_etiketi
                FROM sistem_surumleri WHERE surum_kodu='v1.1.1'
            """).fetchone()
        self.assertEqual("Şeffaf Analiz Çekirdeği", onceki_surum["surum_adi"])
        self.assertEqual("2026-07-16", onceki_surum["yayin_tarihi"])
        self.assertEqual(
            "v1.1.0-seffaf-analiz-cekirdegi", onceki_surum["git_etiketi"]
        )
        self.assertEqual("Marka Arayüzü", guncel_surum["surum_adi"])
        self.assertEqual("2026-07-16", guncel_surum["yayin_tarihi"])
        self.assertEqual("v1.1.1-marka-arayuzu", guncel_surum["git_etiketi"])

    def test_eski_ve_tarihsiz_adaylar_kalici_arsivde_saklanir(self):
        with closing(veritabani.baglan()) as conn, conn:
            kaynak_id = conn.execute("""
                INSERT INTO kaynaklar
                    (kurum_adi, il, ilce, url, eklenme_tarihi)
                VALUES ('Mamak MEM', 'Ankara', 'Mamak', 'https://mamak.meb.gov.tr', '2026-01-01')
            """).lastrowid
            for sira, tarih in enumerate(("2025-07-14", None, "2025-07-15"), start=1):
                conn.execute("""
                    INSERT INTO duyuru_adaylari
                        (kaynak_id, baslik, url, yayin_tarihi, ilk_gorulme, son_gorulme)
                    VALUES (?, 'Kantin ihalesi', ?, ?, '2026-01-01', '2026-01-01')
                """, (kaynak_id, f"https://mamak.meb.gov.tr/{sira}", tarih))

        self.assertEqual(0, veritabani.eski_adaylari_temizle("2025-07-15"))
        with closing(veritabani.baglan()) as conn:
            tarihler = [satir[0] for satir in conn.execute(
                "SELECT yayin_tarihi FROM duyuru_adaylari"
            )]
        self.assertEqual(["2025-07-14", None, "2025-07-15"], tarihler)

    def test_ihale_durumu_tarihe_gore_guncellenir(self):
        with closing(veritabani.baglan()) as conn, conn:
            kaynak_id = conn.execute("""
                INSERT INTO kaynaklar
                    (kurum_adi, il, ilce, url, eklenme_tarihi)
                VALUES ('Test MEM', 'Ankara', 'Mamak', 'https://test.meb.gov.tr', '2026-01-01')
            """).lastrowid
            for sira, ihale_tarihi in enumerate(("2026-12-31", "2099-01-01", None), start=1):
                conn.execute("""
                    INSERT INTO duyuru_adaylari
                        (kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                         ilk_gorulme, son_gorulme)
                    VALUES (?, 'Kantin ihalesi', ?, '2026-01-01', ?,
                            '2026-01-01', '2026-01-01')
                """, (kaynak_id, f"https://test.meb.gov.tr/{sira}", ihale_tarihi))

        veritabani.aday_durumlarini_guncelle()
        with closing(veritabani.baglan()) as conn:
            durumlar = [satir[0] for satir in conn.execute(
                "SELECT durum FROM duyuru_adaylari ORDER BY id"
            )]
        self.assertEqual(["aktif", "tarih_bekleniyor", "tarih_bekleniyor"], durumlar)

    def test_mantiksiz_uzak_ihale_tarihi_reddedilir(self):
        with closing(veritabani.baglan()) as conn, conn:
            kaynak_id = conn.execute("""
                INSERT INTO kaynaklar
                    (kurum_adi, il, ilce, url, eklenme_tarihi)
                VALUES ('Test MEM', 'İstanbul', 'Pendik',
                        'https://pendik.meb.gov.tr', '2025-10-03')
            """).lastrowid
            kayit_id = conn.execute("""
                INSERT INTO duyuru_adaylari
                    (kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                     ilk_gorulme, son_gorulme)
                VALUES (?, 'Kantin ihalesi', 'https://pendik.meb.gov.tr/uzak',
                        '2025-10-03', '4734-03-04', '2025-10-03', '2025-10-03')
            """, (kaynak_id,)).lastrowid
            satir = conn.execute("""
                SELECT ihale_tarihi, durum, tarih_hatasi
                FROM duyuru_adaylari WHERE id=?
            """, (kayit_id,)).fetchone()
        self.assertIsNone(satir["ihale_tarihi"])
        self.assertEqual("tarih_bekleniyor", satir["durum"])
        self.assertIn("366", satir["tarih_hatasi"])

    def test_ihale_tarihi_yayin_tarihiyle_ayni_olamaz(self):
        with closing(veritabani.baglan()) as conn, conn:
            kaynak_id = conn.execute("""
                INSERT INTO kaynaklar
                    (kurum_adi, il, ilce, url, eklenme_tarihi)
                VALUES ('Test MEM', 'İzmir', 'Aliağa',
                        'https://aliaga.meb.gov.tr', '2026-01-01')
            """).lastrowid
            kayit_id = conn.execute("""
                INSERT INTO duyuru_adaylari
                    (kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                     ilk_gorulme, son_gorulme)
                VALUES (?, 'Kantin ihalesi', 'https://aliaga.meb.gov.tr/1',
                        '2026-07-07', '2026-07-07', '2026-07-07', '2026-07-07')
            """, (kaynak_id,)).lastrowid
            satir = conn.execute("""
                SELECT ihale_tarihi, durum, tarih_hatasi
                FROM duyuru_adaylari WHERE id=?
            """, (kayit_id,)).fetchone()
        self.assertIsNone(satir["ihale_tarihi"])
        self.assertEqual("tarih_bekleniyor", satir["durum"])
        self.assertIn("yayından sonra", satir["tarih_hatasi"])

    def test_ham_metadata_baglanti_hatasinda_korunur(self):
        with closing(veritabani.baglan()) as conn, conn:
            kaynak_id = conn.execute("""
                INSERT INTO kaynaklar
                    (kurum_adi, il, ilce, url, eklenme_tarihi)
                VALUES ('Test MEM', 'Ankara', 'Mamak',
                        'https://mamak.meb.gov.tr', '2026-01-01')
            """).lastrowid

        with patch.object(
            meb_tarama_servisi, "ihale_tarih_siniri", return_value=veritabani.ihale_tarih_siniri()
        ):
            meb_tarama_servisi._ham_adaylari_kaydet(
                kaynak_id,
                "https://mamak.meb.gov.tr/duyurular",
                {"https://mamak.meb.gov.tr/bozuk": ("Ekin Ortaokulu Kantin İhalesi", "2026-07-01")},
            )
        meb_tarama_servisi._ham_aday_sonucu_yaz(
            "https://mamak.meb.gov.tr/bozuk",
            erisim_durumu="hata",
            dogrulama_durumu="bekliyor",
            hata="Bağlantı kurulamadı",
        )
        with closing(veritabani.baglan()) as conn:
            satir = conn.execute("""
                SELECT baslik, yayin_tarihi, erisim_durumu, dogrulama_durumu, son_hata
                FROM ham_duyurular WHERE url='https://mamak.meb.gov.tr/bozuk'
            """).fetchone()
        self.assertIsNotNone(satir)
        self.assertEqual("2026-07-01", satir["yayin_tarihi"])
        self.assertEqual("hata", satir["erisim_durumu"])
        self.assertEqual("bekliyor", satir["dogrulama_durumu"])


if __name__ == "__main__":
    unittest.main()
