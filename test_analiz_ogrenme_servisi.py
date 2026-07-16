import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import analiz_motoru
from analiz_ogrenme_servisi import ogrenilmis_okul_bilgisini_uygula
import veritabani


class AnalizOgrenmeServisiTesti(unittest.TestCase):
    def test_okul_kimligi_ogrenilir_finansal_degerler_kopyalanmaz(self):
        with tempfile.TemporaryDirectory() as klasor, patch.object(
            veritabani, "DB", Path(klasor) / "ogrenme.db"
        ):
            veritabani.tablo_olustur()
            with closing(veritabani.baglan()) as conn, conn:
                kaynak_id = conn.execute("""
                    INSERT INTO kaynaklar(kurum_adi, il, ilce, url, eklenme_tarihi)
                    VALUES ('Mamak MEM', 'Ankara', 'Mamak',
                            'https://mamak.meb.gov.tr', '2026-07-16')
                """).lastrowid
                eski_id = conn.execute("""
                    INSERT INTO duyuru_adaylari(
                        kaynak_id, baslik, url, yayin_tarihi,
                        ilk_gorulme, son_gorulme
                    ) VALUES (?, 'Atatürk Ortaokulu Kantin İhalesi',
                              'https://mamak.meb.gov.tr/eski', '2026-07-15',
                              '2026-07-15', '2026-07-15')
                """, (kaynak_id,)).lastrowid
                yeni_id = conn.execute("""
                    INSERT INTO duyuru_adaylari(
                        kaynak_id, baslik, url, yayin_tarihi,
                        ilk_gorulme, son_gorulme
                    ) VALUES (?, 'Atatürk Ortaokulu Yeni Kantin İhalesi',
                              'https://mamak.meb.gov.tr/yeni', '2026-07-16',
                              '2026-07-16', '2026-07-16')
                """, (kaynak_id,)).lastrowid
                conn.execute("""
                    INSERT INTO ilan_analiz_verileri(
                        aday_id, ham_metin, guncelleme_tarihi
                    ) VALUES (?, 'Atatürk Ortaokulu şartname metni', '2026-07-16')
                """, (eski_id,))

            analiz_motoru.manuel_duzeltme_kaydet(eski_id, {
                "il": "Ankara", "ilce": "Mamak",
                "okul_adi": "Atatürk Ortaokulu", "okul_turu": "Ortaokul",
                "ogrenci_sayisi": 500, "personel_sayisi": 20,
                "muhammen_bedel_aylik": 10000,
            })
            with closing(veritabani.baglan()) as conn, conn:
                sonuc = ogrenilmis_okul_bilgisini_uygula(conn, yeni_id, {
                    "ham_metin": "Atatürk Ortaokulu kantin kiralama şartnamesi"
                })
            self.assertEqual("Atatürk Ortaokulu", sonuc["okul_adi"])
            self.assertEqual("Ortaokul", sonuc["okul_turu"])
            self.assertNotIn("ogrenci_sayisi", sonuc)
            self.assertNotIn("muhammen_bedel_aylik", sonuc)


if __name__ == "__main__":
    unittest.main()
