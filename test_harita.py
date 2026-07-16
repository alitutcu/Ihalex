import json
import unittest

import pandas as pd

from harita_gosterici import (
    GEOJSON_DOSYA,
    HARITA_YUKSEKLIGI,
    IL_HARITA_YUKSEKLIGI,
    IL_GEOJSON_DOSYA,
    _ilce_adi,
    ilce_secenekleri,
    turkiye_haritasi,
    turkiye_il_haritasi,
)
from harita_motoru import ilce_harita_id


class HaritaTesti(unittest.TestCase):
    def test_resmi_ilce_katmani_tamdir(self):
        veri = json.loads(GEOJSON_DOSYA.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(veri["features"]), 950)
        self.assertEqual(81, len({x["properties"]["IL_ID"] for x in veri["features"]}))
        il_verisi = json.loads(IL_GEOJSON_DOSYA.read_text(encoding="utf-8"))
        self.assertEqual(81, len(il_verisi["features"]))

    def test_ilce_adi_farklari_eslesir(self):
        self.assertEqual(
            ilce_harita_id(4, "Doğubayazıt"),
            ilce_harita_id(4, "Doğubeyazıt"),
        )
        self.assertEqual("Eyüpsultan", _ilce_adi("Eyüp"))
        self.assertEqual("Merkez", _ilce_adi("Amasya_Merkez İlçe"))

    def test_il_ve_ilce_filtresi_haritayi_daraltir(self):
        self.assertIn("Mamak", ilce_secenekleri("Ankara"))
        veri = pd.DataFrame([
            {
                "il": "Ankara",
                "ilce": "Mamak",
                "il_kodu": 6,
                "harita_id": ilce_harita_id(6, "Mamak"),
                "ilan_sayisi": 3,
            }
        ])
        sekil = turkiye_haritasi(veri, "Ankara", "Mamak")
        self.assertEqual(2, len(sekil.data))
        self.assertEqual(1, len(sekil.data[0].locations))
        self.assertEqual(HARITA_YUKSEKLIGI, sekil.layout.height)
        self.assertEqual("ihalex-harita-ankara-mamak", sekil.layout.uirevision)
        self.assertAlmostEqual(
            sum(sekil.layout.geo.lonaxis.range) / 2,
            sekil.layout.geo.center.lon,
        )
        self.assertAlmostEqual(
            sum(sekil.layout.geo.lataxis.range) / 2,
            sekil.layout.geo.center.lat,
        )

    def test_ana_sayfa_il_haritasi_tum_illeri_tiklanabilir_tutar(self):
        veri = pd.DataFrame([
            {
                "il": "Konya",
                "ilan_sayisi": 12,
                "aktif_sayisi": 2,
                "pasif_sayisi": 9,
                "inceleme_sayisi": 1,
            }
        ])
        sekil = turkiye_il_haritasi(veri)
        self.assertEqual(1, len(sekil.data))
        self.assertEqual(81, len(sekil.data[0].locations))
        self.assertIn("Konya", sekil.data[0].locations)
        self.assertEqual(IL_HARITA_YUKSEKLIGI, sekil.layout.height)
        self.assertEqual("event+select", sekil.layout.clickmode)
        self.assertFalse(sekil.data[0].showscale)
        konya_indeksi = list(sekil.data[0].locations).index("Konya")
        self.assertEqual(5, sekil.data[0].z[konya_indeksi])
        self.assertEqual("#22C55E", sekil.data[0].colorscale[-1][1])


if __name__ == "__main__":
    unittest.main()
