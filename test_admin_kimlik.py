import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from admin_kimlik import (
    AdminKimlikHatasi,
    admin_kimligini_dogrula,
    admin_kurulumu_gerekli,
    admin_oturumu_gecerli,
    admin_oturum_tokeni_olustur,
    admin_oturum_tokenini_dogrula,
    yerel_admin_olustur,
)


class AdminKimlikTesti(unittest.TestCase):
    def test_yerel_admin_ozetli_kaydedilir_ve_dogrulanir(self):
        with tempfile.TemporaryDirectory() as klasor, patch.dict(os.environ, {}, clear=True):
            dosya = Path(klasor) / ".admin_kimlik"
            self.assertTrue(admin_kurulumu_gerekli(dosya))
            yerel_admin_olustur("yonetici", "Guclu-Parola-2026", dosya=dosya)
            self.assertNotIn("Guclu-Parola-2026", dosya.read_text(encoding="utf-8"))
            self.assertTrue(admin_kimligini_dogrula("yonetici", "Guclu-Parola-2026", dosya=dosya))
            self.assertFalse(admin_kimligini_dogrula("yonetici", "yanlis-parola", dosya=dosya))

    def test_kisa_parola_reddedilir(self):
        with tempfile.TemporaryDirectory() as klasor:
            with self.assertRaises(AdminKimlikHatasi):
                yerel_admin_olustur("admin", "kisa", dosya=Path(klasor) / "kimlik")

    def test_admin_oturumu_uc_saatlik_bitis_zamanina_kadar_gecerlidir(self):
        self.assertTrue(admin_oturumu_gecerli(
            "2026-07-16T15:00:00", simdi=datetime(2026, 7, 16, 12, 0, 0)
        ))
        self.assertFalse(admin_oturumu_gecerli(
            "2026-07-16T15:00:00", simdi=datetime(2026, 7, 16, 15, 0, 0)
        ))

    def test_imzali_oturum_tokeni_sekmeler_arasinda_uc_saat_gecerlidir(self):
        with tempfile.TemporaryDirectory() as klasor, patch.dict(os.environ, {}, clear=True):
            dosya = Path(klasor) / ".admin_kimlik"
            yerel_admin_olustur("yonetici", "Guclu-Parola-2026", dosya=dosya)
            token, bitis = admin_oturum_tokeni_olustur(
                "yonetici", simdi=datetime(2026, 7, 16, 12, 0, 0), dosya=dosya
            )
            self.assertEqual(datetime(2026, 7, 16, 15, 0, 0), bitis)
            self.assertIsNotNone(admin_oturum_tokenini_dogrula(
                token, simdi=datetime(2026, 7, 16, 14, 59, 59), dosya=dosya
            ))
            self.assertIsNone(admin_oturum_tokenini_dogrula(
                token, simdi=datetime(2026, 7, 16, 15, 0, 0), dosya=dosya
            ))
            self.assertIsNone(admin_oturum_tokenini_dogrula(
                token + "x", simdi=datetime(2026, 7, 16, 13, 0, 0), dosya=dosya
            ))


if __name__ == "__main__":
    unittest.main()
