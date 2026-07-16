import unittest

from personel_maliyet_servisi import (
    PersonelMaliyetHatasi,
    baz_personel_sayisi_hesapla,
    kisi_basi_personel_maliyeti_hesapla,
    onerilen_calisan_sayisi_hesapla,
    personel_maliyet_raporu_olustur,
)


class PersonelMaliyetServisiTesti(unittest.TestCase):
    def test_her_300_ogrenci_icin_bir_calisan(self):
        for ogrenci, beklenen in ((100, 1), (300, 1), (400, 2), (600, 2),
                                  (665, 3), (800, 3), (1000, 4)):
            self.assertEqual(beklenen, baz_personel_sayisi_hesapla(ogrenci))

    def test_lise_katsayisi_yukari_yuvarlanir(self):
        sonuc = onerilen_calisan_sayisi_hesapla(800, "Lise")
        self.assertEqual(3, sonuc["baz_personel_sayisi"])
        self.assertEqual(4, sonuc["onerilen_calisan_sayisi"])

    def test_2026_indirimsiz_asgari_isveren_maliyeti(self):
        sonuc = kisi_basi_personel_maliyeti_hesapla()
        self.assertEqual(17616.00, sonuc["brut_maas"])
        self.assertEqual(14973.60, sonuc["tahmini_net_maas"])
        self.assertEqual(3831.48, sonuc["sgk_maliyeti"])
        self.assertEqual(352.32, sonuc["issizlik_sigortasi"])
        self.assertEqual(18805.08, sonuc["net_maas_sgk_toplami"])
        self.assertEqual(21799.80, sonuc["kisi_basi_personel_maliyeti"])

    def test_manuel_calisan_sayisi_toplamda_kullanilir(self):
        sonuc = personel_maliyet_raporu_olustur(800, "Lise", {
            "otomatik_personel_hesapla": False,
            "manuel_calisan_sayisi": 3,
        })
        self.assertEqual(4, sonuc["onerilen_calisan_sayisi"])
        self.assertEqual(3, sonuc["kullanilan_calisan_sayisi"])
        self.assertEqual("manuel", sonuc["personel_hesaplama_modu"])
        self.assertEqual(65399.40, sonuc["toplam_personel_gideri"])

    def test_brut_maas_asgari_altinda_olamaz(self):
        with self.assertRaises(PersonelMaliyetHatasi):
            kisi_basi_personel_maliyeti_hesapla(brut_maas=30000)


if __name__ == "__main__":
    unittest.main()
