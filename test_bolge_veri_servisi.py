import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bolge_veri_servisi
import veritabani


class BolgeVeriServisiTesti(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.db_yamasi = patch.object(
            veritabani, "DB", Path(self.klasor.name) / "bolge.db"
        )
        self.db_yamasi.start()
        veritabani.tablo_olustur()

    def tearDown(self):
        self.db_yamasi.stop()
        self.klasor.cleanup()

    def test_yeni_bolge_notr_katsayilarla_olusturulur(self):
        veri = bolge_veri_servisi.bolge_verisi_getir("Ankara", "Mamak")
        self.assertEqual("Varsayılan", veri["veri_durumu"])
        self.assertEqual(1.0, veri["ekonomik_katsayi"])
        self.assertEqual(1.0, veri["gelir_katsayi"])
        self.assertEqual(1.0, veri["nufus_katsayi"])
        self.assertEqual(1.0, veri["ticari_hareketlilik_katsayi"])
        self.assertEqual(1.0, bolge_veri_servisi.ekonomik_katsayi_hesapla(veri))

    def test_dogrulanmamis_kaynak_notr_disi_katsayi_yazamaz(self):
        with self.assertRaises(bolge_veri_servisi.BolgeVeriHatasi):
            bolge_veri_servisi.veri_guncelle(
                "Ankara", "Mamak", ekonomik_katsayi=1.20
            )

    def test_dogrulanmis_kaynak_gelecekte_katsayi_guncelleyebilir(self):
        veri = bolge_veri_servisi.veri_guncelle(
            "Ankara", "Mamak",
            ekonomik_katsayi=1.10,
            gelir_katsayi=1.05,
            ticari_hareketlilik_katsayi=1.08,
            veri_kaynagi="TÜİK SES 2027",
            kaynak_dogrulandi=True,
        )
        self.assertEqual("Kaynak bağlı", veri["veri_durumu"])
        self.assertEqual(1.10, veri["ekonomik_katsayi"])


if __name__ == "__main__":
    unittest.main()
