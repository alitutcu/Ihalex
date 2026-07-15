import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

import telegram_alarm
import veritabani


class TelegramAlarmTesti(unittest.TestCase):
    def test_abone_kullanici_adi_ve_chat_id_kaydedilir(self):
        with tempfile.TemporaryDirectory() as klasor:
            db = Path(klasor) / "abone.db"
            with patch.object(veritabani, "DB", db):
                veritabani.tablo_olustur()
                telegram_alarm._abone_kaydet(
                    {
                        "id": 12345,
                        "first_name": "Ali",
                        "last_name": "Yılmaz",
                        "username": "aliyilmaz",
                        "type": "private",
                    }
                )
                with closing(veritabani.baglan()) as conn:
                    abone = conn.execute(
                        "SELECT chat_id, ad, kullanici_adi FROM telegram_aboneleri"
                    ).fetchone()
                self.assertEqual(("12345", "Ali Yılmaz", "aliyilmaz"), tuple(abone))

    def test_stop_yapan_kurucu_hesap_yeniden_aktif_edilmez(self):
        with tempfile.TemporaryDirectory() as klasor:
            db = Path(klasor) / "stop.db"
            with patch.object(veritabani, "DB", db):
                veritabani.tablo_olustur()
                with closing(veritabani.baglan()) as conn, conn:
                    conn.execute("""
                        INSERT INTO telegram_aboneleri(
                            chat_id, ad, aktif, baslama_tarihi, son_gorulme
                        ) VALUES ('12345', 'Ali', 0, '2026-01-01', '2026-01-02')
                    """)
                with patch.dict(
                    os.environ,
                    {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "12345"},
                ):
                    telegram_alarm._ana_aboneyi_guvenceye_al()
                with closing(veritabani.baglan()) as conn:
                    aktif = conn.execute(
                        "SELECT aktif FROM telegram_aboneleri WHERE chat_id='12345'"
                    ).fetchone()[0]
                self.assertEqual(0, aktif)

    def test_start_mesajindan_baglanti_kurulur(self):
        get_me = Mock(ok=True)
        get_me.json.return_value = {
            "ok": True,
            "result": {"username": "ihalex_test_bot"},
        }
        get_updates = Mock(ok=True)
        get_updates.json.return_value = {
            "ok": True,
            "result": [
                {
                    "message": {
                        "text": "/start",
                        "chat": {"id": 12345, "first_name": "Ali"},
                    }
                }
            ],
        }
        send_message = Mock(ok=True)
        send_message.json.return_value = {"ok": True, "result": {}}
        with patch.object(
            telegram_alarm.requests, "get", side_effect=[get_me, get_updates]
        ), patch.object(
            telegram_alarm.requests, "post", return_value=send_message
        ), patch.object(
            telegram_alarm, "_guncellemeleri_isle", return_value={"eklenen": 1}
        ), patch.object(
            telegram_alarm, "_guncellemeleri_onayla"
        ), patch.object(telegram_alarm, "kimlik_kaydet") as kaydet:
            sonuc = telegram_alarm.telegram_baglantisini_kur("123:token")
        self.assertEqual("ihalex_test_bot", sonuc["bot"])
        self.assertEqual("12345", sonuc["chat_id"])
        kaydet.assert_called_once_with("123:token", "12345", "ihalex_test_bot")

    def test_bekleyen_alarm_gonderilip_isaretlenir(self):
        with tempfile.TemporaryDirectory() as klasor:
            db = Path(klasor) / "alarm.db"
            with patch.object(veritabani, "DB", db):
                veritabani.tablo_olustur()
                with closing(veritabani.baglan()) as conn, conn:
                    kaynak_id = conn.execute("""
                        INSERT INTO kaynaklar
                            (kurum_adi, il, ilce, url, aktif, dogrulandi, eklenme_tarihi)
                        VALUES ('Mamak MEM', 'Ankara', 'Mamak', 'https://mamak.meb.gov.tr', 1, 1, '2026-01-01')
                    """).lastrowid
                    aday_id = conn.execute("""
                        INSERT INTO duyuru_adaylari
                            (kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                             durum, ilk_gorulme, son_gorulme)
                        VALUES (?, 'Kantin ihale duyurusu',
                                'https://mamak.meb.gov.tr/ilan', '2026-07-01',
                                '2026-12-31', 'aktif', '2026-01-01', '2026-01-01')
                    """, (kaynak_id,)).lastrowid
                    conn.execute("""
                        INSERT INTO alarmlar(aday_id, olusturma_tarihi)
                        VALUES (?, '2026-01-01')
                    """, (aday_id,))
                    conn.execute("""
                        INSERT INTO telegram_aboneleri(
                            chat_id, ad, aktif, baslama_tarihi, son_gorulme
                        ) VALUES ('chat', 'Ali', 1, '2026-01-01', '2026-01-01')
                    """)
                    conn.commit()

                yanit = Mock()
                yanit.raise_for_status.return_value = None
                ortam = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}
                with patch.dict(os.environ, ortam), patch.object(
                    telegram_alarm, "telegram_aboneleri_yenile", return_value={}
                ), patch.object(
                    telegram_alarm.requests, "post", return_value=yanit
                ) as post:
                    self.assertEqual(1, telegram_alarm.bekleyenleri_gonder())
                    self.assertIn("Aktif kantin ihalesi", post.call_args.kwargs["data"]["text"])
                    self.assertIn("2026-12-31", post.call_args.kwargs["data"]["text"])

                with closing(veritabani.baglan()) as conn:
                    durum = conn.execute("SELECT durum FROM alarmlar").fetchone()[0]
                self.assertEqual("gonderildi", durum)

    def test_alarm_aktif_tum_abonelere_gonderilir(self):
        with tempfile.TemporaryDirectory() as klasor:
            db = Path(klasor) / "yayin.db"
            with patch.object(veritabani, "DB", db):
                veritabani.tablo_olustur()
                with closing(veritabani.baglan()) as conn, conn:
                    kaynak_id = conn.execute("""
                        INSERT INTO kaynaklar(
                            kurum_adi, il, ilce, url, eklenme_tarihi
                        ) VALUES ('Mamak MEM', 'Ankara', 'Mamak',
                                  'https://mamak.meb.gov.tr', '2026-01-01')
                    """).lastrowid
                    aday_id = conn.execute("""
                        INSERT INTO duyuru_adaylari(
                            kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                            durum, ilk_gorulme, son_gorulme
                        ) VALUES (?, 'Kantin ihalesi', 'https://mamak.meb.gov.tr/1',
                                  '2026-07-01', '2026-12-31', 'aktif',
                                  '2026-01-01', '2026-01-01')
                    """, (kaynak_id,)).lastrowid
                    conn.execute("""
                        INSERT INTO alarmlar(aday_id, olusturma_tarihi)
                        VALUES (?, '2026-01-01')
                    """, (aday_id,))
                    for chat_id, ad in (("101", "Ali"), ("202", "Ayşe")):
                        conn.execute("""
                            INSERT INTO telegram_aboneleri(
                                chat_id, ad, aktif, baslama_tarihi, son_gorulme
                            ) VALUES (?, ?, 1, '2026-01-01', '2026-01-01')
                        """, (chat_id, ad))
                yanit = Mock()
                yanit.raise_for_status.return_value = None
                ortam = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "101"}
                with patch.dict(os.environ, ortam), patch.object(
                    telegram_alarm, "telegram_aboneleri_yenile", return_value={}
                ), patch.object(
                    telegram_alarm.requests, "post", return_value=yanit
                ) as post:
                    self.assertEqual(2, telegram_alarm.bekleyenleri_gonder())
                self.assertEqual(
                    {"101", "202"},
                    {x.kwargs["data"]["chat_id"] for x in post.call_args_list},
                )

    def test_yalniz_aktif_ilan_kuyruga_alinir(self):
        with tempfile.TemporaryDirectory() as klasor:
            db = Path(klasor) / "alarm.db"
            with patch.object(veritabani, "DB", db):
                veritabani.tablo_olustur()
                with closing(veritabani.baglan()) as conn, conn:
                    kaynak_id = conn.execute("""
                        INSERT INTO kaynaklar
                            (kurum_adi, il, ilce, url, eklenme_tarihi)
                        VALUES ('Mamak MEM', 'Ankara', 'Mamak',
                                'https://mamak.meb.gov.tr', '2026-01-01')
                    """).lastrowid
                    for sira, durum, tarih in (
                        (1, 'aktif', '2026-12-31'),
                        (2, 'pasif', '2000-01-10'),
                    ):
                        conn.execute("""
                            INSERT INTO duyuru_adaylari
                                (kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                                 durum, ilk_gorulme, son_gorulme)
                            VALUES (?, 'Kantin ihalesi', ?, '2026-01-01', ?, ?,
                                    '2026-01-01', '2026-01-01')
                        """, (kaynak_id, f'https://mamak.meb.gov.tr/{sira}', tarih, durum))
                self.assertEqual(1, telegram_alarm.aktif_ilanlari_kuyruga_al())
                with closing(veritabani.baglan()) as conn:
                    self.assertEqual(
                        1, conn.execute("SELECT COUNT(*) FROM alarmlar").fetchone()[0]
                    )

    def test_manuel_gonderim_aktif_ilani_yeniden_kuyruga_alir(self):
        with tempfile.TemporaryDirectory() as klasor:
            db = Path(klasor) / "yeniden_alarm.db"
            with patch.object(veritabani, "DB", db):
                veritabani.tablo_olustur()
                with closing(veritabani.baglan()) as conn, conn:
                    kaynak_id = conn.execute("""
                        INSERT INTO kaynaklar
                            (kurum_adi, il, ilce, url, eklenme_tarihi)
                        VALUES ('Mamak MEM', 'Ankara', 'Mamak',
                                'https://mamak.meb.gov.tr', '2026-01-01')
                    """).lastrowid
                    aday_id = conn.execute("""
                        INSERT INTO duyuru_adaylari
                            (kaynak_id, baslik, url, yayin_tarihi, ihale_tarihi,
                             durum, ilk_gorulme, son_gorulme)
                        VALUES (?, 'Kantin ihalesi', 'https://mamak.meb.gov.tr/1',
                                '2026-07-01', '2026-12-31', 'aktif',
                                '2026-01-01', '2026-01-01')
                    """, (kaynak_id,)).lastrowid
                    conn.execute("""
                        INSERT INTO alarmlar(
                            aday_id, durum, deneme_sayisi,
                            olusturma_tarihi, gonderilme_tarihi
                        ) VALUES (?, 'gonderildi', 1, '2026-01-01', '2026-01-02')
                    """, (aday_id,))
                self.assertEqual(
                    1,
                    telegram_alarm.aktif_ilanlari_kuyruga_al(yeniden_gonder=True),
                )
                with closing(veritabani.baglan()) as conn:
                    durum = conn.execute(
                        "SELECT durum, deneme_sayisi, gonderilme_tarihi FROM alarmlar"
                    ).fetchone()
                self.assertEqual(("bekliyor", 0, None), tuple(durum))


if __name__ == "__main__":
    unittest.main()
