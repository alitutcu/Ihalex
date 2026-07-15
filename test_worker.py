import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import worker


class WorkerTesti(unittest.TestCase):
    def test_sonraki_tarama_1159_ve_2359_programina_uyar(self):
        sabah = datetime(2026, 7, 15, 9, 0, tzinfo=worker.TURKIYE_SAATI)
        self.assertEqual(
            (11, 59, 15),
            (
                worker.sonraki_tarama_zamani(sabah).hour,
                worker.sonraki_tarama_zamani(sabah).minute,
                worker.sonraki_tarama_zamani(sabah).day,
            ),
        )
        oglen = datetime(2026, 7, 15, 12, 0, tzinfo=worker.TURKIYE_SAATI)
        self.assertEqual(
            (23, 59, 15),
            (
                worker.sonraki_tarama_zamani(oglen).hour,
                worker.sonraki_tarama_zamani(oglen).minute,
                worker.sonraki_tarama_zamani(oglen).day,
            ),
        )
        gece = datetime(2026, 7, 15, 23, 59, 1, tzinfo=worker.TURKIYE_SAATI)
        self.assertEqual(
            (11, 59, 16),
            (
                worker.sonraki_tarama_zamani(gece).hour,
                worker.sonraki_tarama_zamani(gece).minute,
                worker.sonraki_tarama_zamani(gece).day,
            ),
        )

    def test_tarama_turu_kayitlari_toplar_ve_durum_yazar(self):
        kaynaklar = [
            {"id": 1, "url": "https://a", "kurum_adi": "A", "il": "Samsun", "ilce": "Atakum"},
            {"id": 2, "url": "https://b", "kurum_adi": "B", "il": "Ankara", "ilce": "Mamak"},
        ]
        with tempfile.TemporaryDirectory() as klasor:
            durum = Path(klasor) / "durum.json"
            with (
                patch.object(worker, "DURUM_DOSYASI", durum),
                patch.object(worker, "eski_adaylari_temizle", return_value=0),
                patch.object(worker, "aday_durumlarini_guncelle", return_value=0),
                patch.object(worker, "geri_doldur", return_value={"islenen": 0, "bulunan": 0}),
                patch.object(worker, "siradaki_kaynaklar", return_value=kaynaklar),
                patch.object(worker, "kaynak_tara", side_effect=[(4, 2), (5, 3)]),
                patch.object(worker, "telegram_turu", return_value=0),
            ):
                self.assertEqual(5, worker.tarama_turu(paralellik=1))
            sonuc = json.loads(durum.read_text(encoding="utf-8"))
            self.assertEqual("bekliyor", sonuc["durum"])
            self.assertEqual(5, sonuc["son_yeni_kayit"])
            self.assertEqual(2, sonuc["kaynak_sayisi"])


if __name__ == "__main__":
    unittest.main()
