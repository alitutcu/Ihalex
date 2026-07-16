import unittest
from datetime import date

from yapay_zeka_analizi import ilan_kart_analizi


class YapayZekaAnaliziTesti(unittest.TestCase):
    def test_yaklasan_aktif_ilan_yuksek_oncelik_alir(self):
        sonuc = ilan_kart_analizi(
            {
                "durum": "aktif",
                "okul_adi": "Atatürk İlkokulu",
                "ilce": "Mamak",
                "yayin_tarihi": "2026-07-10",
                "ihale_tarihi": "2026-07-18",
                "ihale_url": "https://mamak.meb.gov.tr/ilan",
            },
            bugun=date(2026, 7, 16),
        )
        self.assertEqual("Çok acil", sonuc["etiket"])
        self.assertGreaterEqual(sonuc["takip_onceligi"], 90)
        self.assertEqual(2, sonuc["kalan_gun"])

    def test_tarihi_eksik_ilan_dogrulama_uyarisi_alir(self):
        sonuc = ilan_kart_analizi(
            {"durum": "tarih_bekleniyor", "okul_adi": "Okul adı doğrulanıyor"},
            bugun=date(2026, 7, 16),
        )
        self.assertEqual("Tarih doğrulanmalı", sonuc["etiket"])
        self.assertIn("ihale tarihi", sonuc["eksikler"])
        self.assertLess(sonuc["veri_guveni"], 70)

    def test_gecmis_ilan_dusuk_oncelik_alir(self):
        sonuc = ilan_kart_analizi(
            {"durum": "pasif", "ihale_tarihi": "2026-07-10"},
            bugun=date(2026, 7, 16),
        )
        self.assertEqual(15, sonuc["takip_onceligi"])
        self.assertEqual("Süresi geçmiş", sonuc["etiket"])


if __name__ == "__main__":
    unittest.main()
