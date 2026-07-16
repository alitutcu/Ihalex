import tempfile
import unittest
from pathlib import Path

from tarama_kontrolu import (
    manuel_tarama_iste,
    manuel_tarama_istegi_var,
    manuel_tarama_istegini_al,
)


class TaramaKontroluTesti(unittest.TestCase):
    def test_manuel_istek_yalnizca_bir_kez_olusturulur_ve_tuketilir(self):
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "istek.json"
            self.assertTrue(manuel_tarama_iste(dosya=dosya))
            self.assertTrue(manuel_tarama_istegi_var(dosya=dosya))
            self.assertFalse(manuel_tarama_iste(dosya=dosya))
            istek = manuel_tarama_istegini_al(dosya=dosya)
            self.assertEqual("tam_tarama", istek["tur"])
            self.assertFalse(manuel_tarama_istegi_var(dosya=dosya))
            self.assertIsNone(manuel_tarama_istegini_al(dosya=dosya))


if __name__ == "__main__":
    unittest.main()
