import unittest

import pandas as pd

from istatistik_motoru import okul_adi_ayikla, tekrar_ihale_ozeti
from okul_adi_servisi import okul_adi_temizle


class IstatistikMotoruTesti(unittest.TestCase):
    def test_okul_adindaki_ozel_karakterler_temizlenir(self):
        self.assertEqual(
            "Talat Tömekçe İlkokulu",
            okul_adi_temizle("(*Talat Tömekçe İlkokulu?!')"),
        )
        self.assertEqual(
            "75. Yıl Ortaokulu",
            okul_adi_temizle("75. Yıl Ortaokulu"),
        )

    def test_mem_adi_okul_adindan_ayrilir(self):
        ornekler = {
            "Altınözü İlçe Milli Eğitim Müdürlüğü Atatürk Ortaokulu Kantin İşletme İhale Duyurusu": "Atatürk Ortaokulu",
            "Mamak İlçe Milli Eğitim Müdürlüğü Ekin Ortaokulu Kantin İhale İlanı": "Ekin Ortaokulu",
            "ODUNPAZARI İLÇE MİLLİ EĞİTİM MÜDÜRLÜĞÜNE BAĞLI OKUL VE KURUMLARIN KANTİN İHALE İLANI- Milli Zafer İlkokulu": "Milli Zafer İlkokulu",
            "Pendik Milli Eğitim Vakfı İlkokulu Kantin İhalesi": "Pendik Milli Eğitim Vakfı İlkokulu",
        }
        for baslik, beklenen in ornekler.items():
            with self.subTest(baslik=baslik):
                self.assertEqual(beklenen, okul_adi_ayikla(baslik))

    def test_okul_adi_olmayan_mem_toplu_ilani_reddedilir(self):
        self.assertIsNone(
            okul_adi_ayikla("Yenimahalle İlçe Milli Eğitim Müdürlüğü Kantin İhale İlanları")
        )

    def test_tekrar_dosya_urlsiyle_degil_tarih_ciftiyle_sayilir(self):
        veri = pd.DataFrame([
            {"baslik": "Ekin Ortaokulu Kantin İhalesi", "il": "Ankara", "ilce": "Mamak", "yayin_tarihi": pd.Timestamp("2026-01-01"), "ihale_tarihi": pd.Timestamp("2026-01-10"), "ihale_url": "a"},
            {"baslik": "Ekin Ortaokulu Kantin İhalesi PDF", "il": "Ankara", "ilce": "Mamak", "yayin_tarihi": pd.Timestamp("2026-01-01"), "ihale_tarihi": pd.Timestamp("2026-01-10"), "ihale_url": "b"},
            {"baslik": "Ekin Ortaokulu Kantin İhalesi", "il": "Ankara", "ilce": "Mamak", "yayin_tarihi": pd.Timestamp("2026-06-01"), "ihale_tarihi": pd.Timestamp("2026-06-15"), "ihale_url": "c"},
            {"baslik": "Ekin Ortaokulu Kantin İhalesi", "il": "Ankara", "ilce": "Mamak", "yayin_tarihi": pd.Timestamp("2026-07-01"), "ihale_tarihi": pd.NaT, "ihale_url": "d"},
        ])
        sonuc = tekrar_ihale_ozeti(veri)
        self.assertEqual(1, len(sonuc))
        self.assertEqual(2, sonuc.iloc[0]["İhale sayısı"])
        self.assertEqual("01.01.2026 · 01.06.2026", sonuc.iloc[0]["Yayın tarihleri"])


if __name__ == "__main__":
    unittest.main()
