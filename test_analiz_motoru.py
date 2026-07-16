import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import analiz_motoru
import veritabani


class AnalizMotoruTesti(unittest.TestCase):
    def test_ciro_gider_kar_ve_kira_orani_aciklanabilir_hesaplanir(self):
        ciro = analiz_motoru.ciro_hesapla(
            500, 50,
            okul_tipi="ortaokul",
            ogrenci_donusum_orani=0.50,
            personel_donusum_orani=0.50,
            ortalama_ogrenci_harcamasi=40,
            ortalama_personel_harcamasi=60,
            okul_gunu=20,
        )
        self.assertEqual(11500, ciro["tahmini_gunluk_ciro"])
        self.assertEqual(230000, ciro["tahmini_aylik_ciro"])
        self.assertEqual(2070000, ciro["tahmini_yillik_ciro"])
        gider = analiz_motoru.gider_hesapla(
            230000, 20000,
            urun_maliyet_orani=0.40,
            aylik_calisan_gideri=30000,
            aylik_elektrik_su_gideri=5000,
            fire_orani=0.02,
            aylik_diger_gider=2000,
        )
        self.assertEqual(153600, gider["toplam_gider"])
        self.assertEqual(76400, analiz_motoru.net_kar_hesapla(230000, 153600))
        self.assertEqual(8.70, analiz_motoru.kira_orani_hesapla(20000, 230000))

    def test_rapor_json_uyumlu_ve_sqlite_kalici(self):
        with tempfile.TemporaryDirectory() as klasor, patch.object(
            veritabani, "DB", Path(klasor) / "analiz.db"
        ):
            veritabani.tablo_olustur()
            with closing(veritabani.baglan()) as conn, conn:
                kaynak_id = conn.execute("""
                    INSERT INTO kaynaklar(
                        kurum_adi, il, ilce, url, eklenme_tarihi
                    ) VALUES ('Mamak MEM', 'Ankara', 'Mamak',
                              'https://mamak.meb.gov.tr', '2026-07-01')
                """).lastrowid
                aday_id = conn.execute("""
                    INSERT INTO duyuru_adaylari(
                        kaynak_id, baslik, url, yayin_tarihi,
                        ilk_gorulme, son_gorulme
                    ) VALUES (?, 'Atatürk Ortaokulu Kantin İhalesi',
                              'https://mamak.meb.gov.tr/1', '2026-07-01',
                              '2026-07-01', '2026-07-01')
                """, (kaynak_id,)).lastrowid
            rapor = analiz_motoru.analiz_raporu_olustur({
                "ogrenci_sayisi": 700,
                "personel_sayisi": 55,
                "okul_adi": "Atatürk Ortaokulu",
                "okul_turu": "Ortaokul",
                "muhammen_bedel_aylik": 30000,
                "muhammen_bedel_yillik": 360000,
                "il": "Ankara",
                "ilce": "Mamak",
                "kantin_alani_m2": 60,
            })
            json.dumps(rapor, ensure_ascii=False)
            self.assertEqual(1.0, rapor["bolgesel_veri"]["ekonomik_katsayi"])
            self.assertEqual(1.0, rapor["ogrenci_harcama_katsayisi"])
            self.assertEqual("Varsayılan", rapor["bolgesel_veri"]["veri_durumu"])
            self.assertTrue(0 <= rapor["yatirim_skoru"] <= 100)
            analiz_motoru.analizi_kaydet(aday_id, rapor)
            kayitli = analiz_motoru.kayitli_analizi_getir(aday_id)
            self.assertEqual(rapor["yatirim_skoru"], kayitli["yatirim_skoru"])
            with closing(veritabani.baglan()) as conn, conn:
                conn.execute(
                    "UPDATE kantin_yatirim_analizleri "
                    "SET motor_surumu='1.1.5' WHERE aday_id=?",
                    (aday_id,),
                )
                korunan_surum = conn.execute(
                    "SELECT motor_surumu FROM kantin_yatirim_analizleri "
                    "WHERE aday_id=?",
                    (aday_id,),
                ).fetchone()[0]
            self.assertEqual(analiz_motoru.MOTOR_SURUMU, korunan_surum)

    def test_ogrenci_ve_kira_olmadan_finansal_tahmin_uretilmez(self):
        with self.assertRaises(analiz_motoru.AnalizVerisiHatasi):
            analiz_motoru.analiz_raporu_olustur({
                "okul_adi": "Atatürk İlkokulu", "okul_turu": "İlkokul",
                "il": "Ankara", "ilce": "Mamak"
            })

    def test_bos_nan_personel_sifir_kabul_edilir(self):
        rapor = analiz_motoru.analiz_raporu_olustur({
            "okul_adi": "Atatürk İlkokulu", "okul_turu": "İlkokul",
            "ogrenci_sayisi": 500, "personel_sayisi": float("nan"),
            "muhammen_bedel_aylik": 10000,
            "muhammen_bedel_yillik": float("nan"),
            "il": "Ankara", "ilce": "Mamak",
        })
        self.assertEqual(0, rapor["girdiler"]["personel_sayisi"])
        self.assertEqual(90000, rapor["girdiler"]["muhammen_bedel_yillik"])

    def test_yillik_ciro_sadece_fiili_egitim_gunlerini_kullanir(self):
        ciro = analiz_motoru.ciro_hesapla(
            100, 0, okul_tipi="Ortaokul", ogrenci_donusum_orani=1,
            ortalama_ogrenci_harcamasi=10, okul_gunu=20,
            yillik_egitim_gunu=175,
        )
        self.assertEqual(1000, ciro["tahmini_gunluk_ciro"])
        self.assertEqual(20000, ciro["tahmini_aylik_ciro"])
        self.assertEqual(175000, ciro["tahmini_yillik_ciro"])

    def test_okul_turune_gore_ortalama_alisveris_orani_kullanilir(self):
        ornekler = (
            ("İlkokul", 0.36),
            ("Ortaokul", 0.54),
            ("Lise", 0.6525),
            ("Meslek Lisesi", 0.72),
        )
        for okul_turu, beklenen in ornekler:
            rapor = analiz_motoru.analiz_raporu_olustur({
                "okul_adi": f"Test {okul_turu}", "okul_turu": okul_turu,
                "ogrenci_sayisi": 500, "muhammen_bedel_aylik": 10000,
                "il": "Ankara", "ilce": "Mamak",
            })
            self.assertEqual(beklenen, rapor["varsayimlar"]["ogrenci_donusum_orani"])

    def test_okul_turu_donusum_araliklari_goreli_yuzde_on_dusurulur(self):
        self.assertEqual((0.27, 0.45), analiz_motoru.OKUL_TURU_DONUSUM_ARALIKLARI["ilkokul"])
        self.assertEqual((0.45, 0.63), analiz_motoru.OKUL_TURU_DONUSUM_ARALIKLARI["ortaokul"])
        self.assertEqual((0.54, 0.765), analiz_motoru.OKUL_TURU_DONUSUM_ARALIKLARI["lise"])
        self.assertEqual((0.63, 0.81), analiz_motoru.OKUL_TURU_DONUSUM_ARALIKLARI["meslek_lisesi"])

    def test_azami_kira_yuzde_yirmi_bes_net_kar_hedefini_korur(self):
        self.assertEqual(
            129000,
            analiz_motoru.maksimum_teklif_hesapla(700000, 396000),
        )

    def test_yatirim_skoru_tahmini_ihale_sonucu_kirasini_kullanir(self):
        rapor = analiz_motoru.analiz_raporu_olustur({
            "okul_adi": "Atatürk Ortaokulu", "okul_turu": "Ortaokul",
            "ogrenci_sayisi": 700, "personel_sayisi": 40,
            "muhammen_bedel_aylik": 30000,
            "il": "Ankara", "ilce": "Mamak",
        })
        beklenen_kira = round(max(30000, rapor["maksimum_kira"] * 0.80), 2)
        self.assertEqual(beklenen_kira, rapor["tahmini_ihale_sonucu_kira"])
        self.assertEqual(beklenen_kira, rapor["gider_detayi"]["kira_gideri"])
        self.assertEqual(
            round(
                rapor["tahmini_aylik_ciro"]
                - rapor["gider_detayi"]["toplam_gider"],
                2,
            ),
            rapor["net_kar"],
        )
        self.assertEqual(
            analiz_motoru.kira_orani_hesapla(
                beklenen_kira, rapor["tahmini_aylik_ciro"]
            ),
            rapor["kira_orani"],
        )
        self.assertEqual(
            rapor["net_kar"], rapor["tahmini_ihale_sonrasi_net_kar"]
        )

    def test_tahmini_ihale_sonucu_muhammen_bedelden_dusuk_olamaz(self):
        rapor = analiz_motoru.analiz_raporu_olustur({
            "okul_adi": "Atatürk İlkokulu", "okul_turu": "İlkokul",
            "ogrenci_sayisi": 300, "muhammen_bedel_aylik": 500000,
            "il": "Ankara", "ilce": "Mamak",
        })
        self.assertEqual(500000, rapor["tahmini_ihale_sonucu_kira"])
        self.assertTrue(
            rapor["ihale_sonucu_detayi"]["muhammen_alt_siniri_uygulandi"]
        )

    def test_okul_turu_ogrenci_harcama_katsayisi_personeli_etkilemez(self):
        ilkokul = analiz_motoru.ciro_hesapla(
            100, 10, okul_tipi="İlkokul", ogrenci_donusum_orani=1,
            personel_donusum_orani=1, ortalama_ogrenci_harcamasi=100,
            ortalama_personel_harcamasi=100, okul_gunu=1,
        )
        lise = analiz_motoru.ciro_hesapla(
            100, 10, okul_tipi="Lise", ogrenci_donusum_orani=1,
            personel_donusum_orani=1, ortalama_ogrenci_harcamasi=100,
            ortalama_personel_harcamasi=100, okul_gunu=1,
        )
        self.assertEqual(0.80, ilkokul["ogrenci_harcama_katsayisi"])
        self.assertEqual(1.20, lise["ogrenci_harcama_katsayisi"])
        self.assertEqual(80, ilkokul["katsayili_ogrenci_harcamasi"])
        self.assertEqual(120, lise["katsayili_ogrenci_harcamasi"])
        self.assertEqual(
            ilkokul["tahmini_gunluk_personel_cirosu"],
            lise["tahmini_gunluk_personel_cirosu"],
        )

    def test_manuel_duzeltme_belge_verisini_ezmez_ve_matematigi_yeniler(self):
        with tempfile.TemporaryDirectory() as klasor, patch.object(
            veritabani, "DB", Path(klasor) / "manuel.db"
        ):
            veritabani.tablo_olustur()
            with closing(veritabani.baglan()) as conn, conn:
                kaynak_id = conn.execute("""
                    INSERT INTO kaynaklar(kurum_adi, il, ilce, url, eklenme_tarihi)
                    VALUES ('Test MEM', 'Ankara', 'Mamak',
                            'https://manuel.meb.gov.tr', '2026-07-16')
                """).lastrowid
                aday_id = conn.execute("""
                    INSERT INTO duyuru_adaylari(
                        kaynak_id, baslik, url, yayin_tarihi,
                        ilk_gorulme, son_gorulme
                    ) VALUES (?, 'Atatürk Ortaokulu Kantin İhalesi',
                              'https://manuel.meb.gov.tr/1', '2026-07-15',
                              '2026-07-15', '2026-07-15')
                """, (kaynak_id,)).lastrowid
                conn.execute("""
                    INSERT INTO ilan_analiz_verileri(
                        aday_id, okul_adi, okul_turu, ogrenci_sayisi,
                        personel_sayisi, muhammen_bedel_aylik,
                        muhammen_bedel_yillik, guncelleme_tarihi
                    ) VALUES (?, 'Atatürk Ortaokulu', 'Ortaokul', 500, 30,
                              10000, 120000, '2026-07-16')
                """, (aday_id,))
            rapor = analiz_motoru.manuel_duzeltme_kaydet(aday_id, {
                "il": "Ankara", "ilce": "Çankaya",
                "okul_adi": "Atatürk Ortaokulu", "okul_turu": "Ortaokul",
                "ogrenci_sayisi": 650, "personel_sayisi": 35,
                "muhammen_bedel_aylik": 12000,
                "ogrenci_donusum_orani": 0.60,
                "ortalama_ogrenci_harcamasi": 55,
                "tahmini_ihale_azami_orani": 0.70,
                "duzeltme_notu": "Belge tekrar kontrol edildi",
            })
            self.assertEqual(650, rapor["girdiler"]["ogrenci_sayisi"])
            self.assertEqual("Çankaya", rapor["girdiler"]["ilce"])
            self.assertEqual(0.70, rapor["tahmini_ihale_azami_orani"])
            self.assertGreater(len(analiz_motoru.analiz_matematigi_olustur(rapor)), 15)
            with closing(veritabani.baglan()) as conn:
                belge_ogrenci = conn.execute(
                    "SELECT ogrenci_sayisi FROM ilan_analiz_verileri WHERE aday_id=?",
                    (aday_id,),
                ).fetchone()[0]
                gecmis = conn.execute(
                    "SELECT COUNT(1) FROM analiz_manuel_gecmisi WHERE aday_id=?",
                    (aday_id,),
                ).fetchone()[0]
                manuel_ilce = conn.execute(
                    "SELECT ilce FROM analiz_manuel_duzeltmeleri WHERE aday_id=?",
                    (aday_id,),
                ).fetchone()[0]
                ogrenme = conn.execute(
                    "SELECT COUNT(1) FROM analiz_ogrenme_ornekleri WHERE aday_id=?",
                    (aday_id,),
                ).fetchone()[0]
            self.assertEqual(500, belge_ogrenci)
            self.assertEqual(1, gecmis)
            self.assertEqual("Çankaya", manuel_ilce)
            self.assertEqual(1, ogrenme)
            analiz_motoru.manuel_duzeltmeyi_kaldir(aday_id)
            with closing(veritabani.baglan()) as conn:
                self.assertEqual(0, conn.execute(
                    "SELECT COUNT(1) FROM analiz_manuel_duzeltmeleri WHERE aday_id=?",
                    (aday_id,),
                ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
