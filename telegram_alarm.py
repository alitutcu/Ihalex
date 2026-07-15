"""Aktif ihale alarmlarını bota abone olan tüm Telegram sohbetlerine gönderir."""

from __future__ import annotations

import os
from contextlib import closing
from datetime import datetime

import requests

from telegram_kimlik import kimlik_kaydet, kimlik_oku
from veritabani import baglan


class TelegramKurulumHatasi(RuntimeError):
    """Kullanıcıya güvenle gösterilebilen Telegram bağlantı hatası."""


def telegram_ayarlari() -> dict[str, str]:
    kayitli = kimlik_oku() or {}
    return {
        "token": os.getenv("TELEGRAM_BOT_TOKEN") or kayitli.get("token", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID") or kayitli.get("chat_id", ""),
        "bot_kullanici_adi": kayitli.get("bot_kullanici_adi", ""),
    }


def telegram_kimligi() -> tuple[str | None, str | None]:
    ayarlar = telegram_ayarlari()
    return ayarlar.get("token") or None, ayarlar.get("chat_id") or None


def telegram_hazir() -> bool:
    return bool(telegram_ayarlari().get("token"))


def telegram_bot_baglantisi() -> str | None:
    kullanici_adi = telegram_ayarlari().get("bot_kullanici_adi", "").lstrip("@")
    return f"https://t.me/{kullanici_adi}" if kullanici_adi else None


def _telegram_api(token: str, metot: str, *, veri: dict | None = None):
    try:
        if metot in {"getMe", "getUpdates"}:
            yanit = requests.get(
                f"https://api.telegram.org/bot{token}/{metot}",
                params=veri,
                timeout=(10, 20),
            )
        else:
            yanit = requests.post(
                f"https://api.telegram.org/bot{token}/{metot}",
                data=veri,
                timeout=(10, 20),
            )
        sonuc = yanit.json()
    except (requests.RequestException, ValueError) as hata:
        raise TelegramKurulumHatasi(
            "Telegram sunucusuna bağlanılamadı. İnternet bağlantısını kontrol et."
        ) from hata
    if not yanit.ok or not sonuc.get("ok"):
        aciklama = sonuc.get("description", "Telegram isteği reddedildi.")
        raise TelegramKurulumHatasi(str(aciklama))
    return sonuc.get("result")


def _abone_kaydet(
    chat: dict | str,
    aktif: bool = True,
    kullanici: dict | None = None,
) -> tuple[int, bool]:
    if isinstance(chat, dict):
        chat_id = str(chat["id"])
        kullanici = kullanici or {}
        ad = str(
            chat.get("title")
            or " ".join(
                x for x in (chat.get("first_name"), chat.get("last_name")) if x
            ).strip()
            or " ".join(
                x for x in (kullanici.get("first_name"), kullanici.get("last_name")) if x
            ).strip()
            or chat_id
        )
        kullanici_adi = str(chat.get("username") or kullanici.get("username") or "")
        sohbet_turu = str(chat.get("type") or "private")
    else:
        chat_id = str(chat)
        ad = ""
        kullanici_adi = ""
        sohbet_turu = "private"
    simdi = datetime.now().isoformat(timespec="seconds")
    with closing(baglan()) as conn, conn:
        mevcut = conn.execute(
            "SELECT id, aktif FROM telegram_aboneleri WHERE chat_id=?",
            (str(chat_id),),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO telegram_aboneleri(
                chat_id, ad, kullanici_adi, sohbet_turu,
                aktif, baslama_tarihi, son_gorulme
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                ad=CASE WHEN excluded.ad<>'' THEN excluded.ad ELSE telegram_aboneleri.ad END,
                kullanici_adi=CASE
                    WHEN excluded.kullanici_adi<>'' THEN excluded.kullanici_adi
                    ELSE telegram_aboneleri.kullanici_adi END,
                sohbet_turu=excluded.sohbet_turu,
                aktif=excluded.aktif,
                son_gorulme=excluded.son_gorulme
            """,
            (
                chat_id, ad, kullanici_adi, sohbet_turu,
                int(aktif), simdi, simdi,
            ),
        )
        abone_id = int(
            conn.execute(
                "SELECT id FROM telegram_aboneleri WHERE chat_id=?",
                (str(chat_id),),
            ).fetchone()[0]
        )
    yeni_veya_yeniden_aktif = mevcut is None or (aktif and not bool(mevcut["aktif"]))
    return abone_id, yeni_veya_yeniden_aktif


def _ana_aboneyi_guvenceye_al() -> None:
    _, chat_id = telegram_kimligi()
    if chat_id:
        with closing(baglan()) as conn, conn:
            mevcut = conn.execute(
                "SELECT id FROM telegram_aboneleri WHERE chat_id=?",
                (str(chat_id),),
            ).fetchone()
            if mevcut:
                abone_id = int(mevcut["id"])
            else:
                abone_id, _ = _abone_kaydet(chat_id, True)
            conn.execute(
                """
                INSERT OR IGNORE INTO telegram_teslimatlari(
                    alarm_id, abone_id, durum, deneme_sayisi,
                    olusturma_tarihi, gonderilme_tarihi
                )
                SELECT id, ?, 'gonderildi', deneme_sayisi,
                       olusturma_tarihi, gonderilme_tarihi
                FROM alarmlar
                WHERE durum='gonderildi'
                """,
                (abone_id,),
            )


def _guncellemeleri_isle(token: str, guncellemeler: list[dict]) -> dict[str, int]:
    eklenen = 0
    ayrilan = 0
    for kayit in guncellemeler:
        mesaj = kayit.get("message") or {}
        chat = mesaj.get("chat") or {}
        if chat.get("id") is None:
            continue
        chat_id = str(chat["id"])
        metin = str(mesaj.get("text") or "").strip().lower()
        if metin.startswith("/start"):
            _, yeni = _abone_kaydet(chat, True, mesaj.get("from") or {})
            eklenen += int(yeni)
            if yeni:
                try:
                    _telegram_api(
                        token,
                        "sendMessage",
                        veri={
                            "chat_id": chat_id,
                            "text": (
                                "✅ İhalex ihale bildirimlerine abone oldun.\n"
                                "Bildirimden çıkmak için /stop yazabilirsin."
                            ),
                        },
                    )
                except TelegramKurulumHatasi:
                    pass
        elif metin.startswith("/stop"):
            _abone_kaydet(chat, False, mesaj.get("from") or {})
            ayrilan += 1
            try:
                _telegram_api(
                    token,
                    "sendMessage",
                    veri={"chat_id": chat_id, "text": "İhalex bildirim aboneliğin kapatıldı."},
                )
            except TelegramKurulumHatasi:
                pass
    return {"eklenen": eklenen, "ayrilan": ayrilan}


def _guncellemeleri_onayla(token: str, guncellemeler: list[dict]) -> None:
    update_idleri = [x.get("update_id") for x in guncellemeler if x.get("update_id") is not None]
    if update_idleri:
        _telegram_api(
            token,
            "getUpdates",
            veri={"offset": max(update_idleri) + 1, "limit": 1, "timeout": 0},
        )


def _eksik_abone_bilgilerini_tamamla(token: str) -> None:
    with closing(baglan()) as conn:
        eksikler = conn.execute(
            """
            SELECT chat_id
            FROM telegram_aboneleri
            WHERE aktif=1 AND (ad='' OR ad='Kurucu hesap')
            LIMIT 20
            """
        ).fetchall()
    for satir in eksikler:
        try:
            chat = _telegram_api(
                token,
                "getChat",
                veri={"chat_id": satir["chat_id"]},
            )
            if isinstance(chat, dict) and chat.get("id") is not None:
                _abone_kaydet(chat, True, chat)
        except TelegramKurulumHatasi:
            continue


def telegram_baglantisini_kur(token: str) -> dict[str, str]:
    """Tokeni doğrular ve /start gönderen sohbetleri aboneliğe alır."""
    token = token.strip()
    if not token or ":" not in token:
        raise TelegramKurulumHatasi("BotFather tokeni geçerli görünmüyor.")
    bot = _telegram_api(token, "getMe")
    guncellemeler = _telegram_api(
        token,
        "getUpdates",
        veri={"limit": 100, "timeout": 0, "allowed_updates": '["message"]'},
    ) or []
    baslangic_mesajlari = [
        x.get("message")
        for x in guncellemeler
        if x.get("message", {}).get("chat", {}).get("id") is not None
        and str(x.get("message", {}).get("text", "")).startswith("/start")
    ]
    if not baslangic_mesajlari:
        raise TelegramKurulumHatasi(
            "Botta /start mesajı bulunamadı. Bota yeniden /start gönderip tekrar dene."
        )
    ana_mesaj = baslangic_mesajlari[-1]
    chat = ana_mesaj["chat"]
    chat_id = str(chat["id"])
    bot_adi = str(bot.get("username", ""))
    kimlik_kaydet(token, chat_id, bot_adi)
    _guncellemeleri_isle(token, guncellemeler)
    _guncellemeleri_onayla(token, guncellemeler)
    sohbet_adi = str(chat.get("title") or chat.get("first_name") or chat_id)
    return {"bot": bot_adi, "sohbet": sohbet_adi, "chat_id": chat_id}


def telegram_aboneleri_yenile() -> dict[str, int]:
    token, _ = telegram_kimligi()
    if not token:
        raise TelegramKurulumHatasi("Önce Telegram bot bağlantısını kurmalısın.")
    _ana_aboneyi_guvenceye_al()
    guncellemeler = _telegram_api(
        token,
        "getUpdates",
        veri={"limit": 100, "timeout": 0, "allowed_updates": '["message"]'},
    ) or []
    sonuc = _guncellemeleri_isle(token, guncellemeler)
    _guncellemeleri_onayla(token, guncellemeler)
    _eksik_abone_bilgilerini_tamamla(token)
    sonuc.update(telegram_abone_ozeti())
    return sonuc


def telegram_abone_ozeti() -> dict[str, int]:
    with closing(baglan()) as conn:
        satir = conn.execute(
            """
            SELECT COUNT(*) AS toplam,
                   SUM(CASE WHEN aktif=1 THEN 1 ELSE 0 END) AS aktif
            FROM telegram_aboneleri
            """
        ).fetchone()
    return {"toplam": int(satir["toplam"] or 0), "aktif": int(satir["aktif"] or 0)}


def telegram_abone_listesi() -> list[dict]:
    with closing(baglan()) as conn:
        satirlar = conn.execute(
            """
            SELECT id, chat_id, ad, kullanici_adi, sohbet_turu,
                   aktif, baslama_tarihi, son_gorulme
            FROM telegram_aboneleri
            ORDER BY aktif DESC, ad COLLATE NOCASE
            """
        ).fetchall()
    return [dict(satir) for satir in satirlar]


def _aktif_aboneler() -> list:
    with closing(baglan()) as conn:
        return conn.execute(
            "SELECT id, chat_id FROM telegram_aboneleri WHERE aktif=1 ORDER BY id"
        ).fetchall()


def telegram_test_mesaji_gonder() -> dict[str, int]:
    token, _ = telegram_kimligi()
    if not token:
        raise TelegramKurulumHatasi("Telegram bot bağlantısı hazır değil.")
    telegram_aboneleri_yenile()
    gonderilen = 0
    hata = 0
    for abone in _aktif_aboneler():
        try:
            _telegram_api(
                token,
                "sendMessage",
                veri={
                    "chat_id": abone["chat_id"],
                    "text": "🔔 İhalex test alarmı başarıyla ulaştı.",
                },
            )
            gonderilen += 1
        except TelegramKurulumHatasi:
            hata += 1
    return {"gonderilen": gonderilen, "hata": hata}


def _mesaj(satir) -> str:
    konum = " / ".join(x for x in (satir["il"], satir["ilce"]) if x)
    return (
        "🚨 Aktif kantin ihalesi\n\n"
        f"{satir['baslik']}\n"
        f"📍 {konum or 'Konum doğrulanıyor'}\n"
        f"🏛️ {satir['kurum_adi']}\n\n"
        f"📅 Yayın: {satir['yayin_tarihi']}\n"
        f"⏰ İhale: {satir['ihale_tarihi']}\n\n"
        f"🔗 {satir['url']}"
    )


def aktif_ilanlari_kuyruga_al(*, yeniden_gonder: bool = False) -> int:
    """Aktif ihaleleri kuyruğa alır; manuel istekte tüm aboneler için sıfırlar."""
    simdi = datetime.now().isoformat(timespec="seconds")
    with closing(baglan()) as conn, conn:
        onceki = conn.total_changes
        conn.execute(
            """
            WITH sirali AS (
                SELECT d.id,
                       ROW_NUMBER() OVER (
                           PARTITION BY COALESCE(NULLIF(d.detay_url, ''), d.url)
                           ORDER BY CASE d.eslesme_turu
                               WHEN 'detay' THEN 0
                               WHEN 'toplu_dosya' THEN 1
                               ELSE 2 END,
                               d.id
                       ) AS sira
                FROM duyuru_adaylari d
                WHERE d.durum='aktif'
                  AND d.ihale_tarihi IS NOT NULL
                  AND date(d.ihale_tarihi) >= date('now', 'localtime')
            )
            INSERT OR IGNORE INTO alarmlar(aday_id, kanal, olusturma_tarihi)
            SELECT id, 'telegram', ? FROM sirali WHERE sira=1
            """,
            (simdi,),
        )
        eklenen = conn.total_changes - onceki
        if yeniden_gonder:
            aktif_alarm_sorgusu = """
                SELECT a.id
                FROM alarmlar a
                JOIN duyuru_adaylari d ON d.id=a.aday_id
                WHERE d.durum='aktif'
                  AND d.ihale_tarihi IS NOT NULL
                  AND date(d.ihale_tarihi) >= date('now', 'localtime')
            """
            imlec = conn.execute(
                f"""
                UPDATE alarmlar
                SET durum='bekliyor', deneme_sayisi=0,
                    gonderilme_tarihi=NULL, son_hata=NULL
                WHERE id IN ({aktif_alarm_sorgusu})
                """
            )
            conn.execute(
                f"""
                UPDATE telegram_teslimatlari
                SET durum='bekliyor', deneme_sayisi=0,
                    gonderilme_tarihi=NULL, son_hata=NULL
                WHERE alarm_id IN ({aktif_alarm_sorgusu})
                """
            )
            return int(imlec.rowcount)
        return eklenen


def _teslimatlari_hazirla(conn) -> int:
    simdi = datetime.now().isoformat(timespec="seconds")
    onceki = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO telegram_teslimatlari(
            alarm_id, abone_id, durum, deneme_sayisi, olusturma_tarihi
        )
        SELECT a.id, b.id, 'bekliyor', 0, ?
        FROM alarmlar a
        JOIN duyuru_adaylari d ON d.id=a.aday_id
        CROSS JOIN telegram_aboneleri b
        WHERE b.aktif=1
          AND d.durum='aktif'
          AND d.ihale_tarihi IS NOT NULL
          AND date(d.ihale_tarihi) >= date('now', 'localtime')
        """,
        (simdi,),
    )
    eklenen = conn.total_changes - onceki
    conn.execute(
        """
        UPDATE alarmlar
        SET durum='bekliyor'
        WHERE id IN (
            SELECT t.alarm_id
            FROM telegram_teslimatlari t
            JOIN telegram_aboneleri b ON b.id=t.abone_id
            WHERE b.aktif=1 AND t.durum IN ('bekliyor', 'hata')
        )
        """
    )
    return eklenen


def _alarm_durumunu_guncelle(conn, alarm_id: int) -> None:
    bekleyen = conn.execute(
        """
        SELECT COUNT(*)
        FROM telegram_teslimatlari t
        JOIN telegram_aboneleri b ON b.id=t.abone_id
        WHERE t.alarm_id=? AND b.aktif=1 AND t.durum<>'gonderildi'
        """,
        (alarm_id,),
    ).fetchone()[0]
    if bekleyen == 0:
        conn.execute(
            """
            UPDATE alarmlar
            SET durum='gonderildi', gonderilme_tarihi=?, son_hata=NULL
            WHERE id=?
            """,
            (datetime.now().isoformat(timespec="seconds"), alarm_id),
        )


def bekleyenleri_gonder(limit: int = 20) -> int:
    token, _ = telegram_kimligi()
    if not token:
        return 0
    telegram_aboneleri_yenile()

    with closing(baglan()) as conn, conn:
        _teslimatlari_hazirla(conn)
        satirlar = conn.execute(
            """
            SELECT t.id AS teslimat_id, t.alarm_id, t.abone_id, b.chat_id,
                   d.baslik, d.url, d.yayin_tarihi, d.ihale_tarihi,
                   k.kurum_adi, k.il, k.ilce
            FROM telegram_teslimatlari t
            JOIN telegram_aboneleri b ON b.id=t.abone_id
            JOIN alarmlar a ON a.id=t.alarm_id
            JOIN duyuru_adaylari d ON d.id=a.aday_id
            JOIN kaynaklar k ON k.id=d.kaynak_id
            WHERE t.durum IN ('bekliyor', 'hata')
              AND t.deneme_sayisi < 5
              AND b.aktif=1
              AND d.durum='aktif'
              AND d.ihale_tarihi IS NOT NULL
              AND date(d.ihale_tarihi) >= date('now', 'localtime')
            ORDER BY date(d.ihale_tarihi), t.olusturma_tarihi
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    gonderilen = 0
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    for satir in satirlar:
        simdi = datetime.now().isoformat(timespec="seconds")
        try:
            yanit = requests.post(
                api_url,
                data={
                    "chat_id": satir["chat_id"],
                    "text": _mesaj(satir),
                    "disable_web_page_preview": "false",
                },
                timeout=(10, 20),
            )
            yanit.raise_for_status()
            with closing(baglan()) as conn, conn:
                conn.execute(
                    """
                    UPDATE telegram_teslimatlari
                    SET durum='gonderildi', gonderilme_tarihi=?,
                        deneme_sayisi=deneme_sayisi+1, son_hata=NULL
                    WHERE id=?
                    """,
                    (simdi, satir["teslimat_id"]),
                )
                _alarm_durumunu_guncelle(conn, int(satir["alarm_id"]))
            gonderilen += 1
        except Exception as hata:
            guvenli_hata = str(hata).replace(token, "***")
            with closing(baglan()) as conn, conn:
                conn.execute(
                    """
                    UPDATE telegram_teslimatlari
                    SET durum='hata', deneme_sayisi=deneme_sayisi+1, son_hata=?
                    WHERE id=?
                    """,
                    (guvenli_hata[:1000], satir["teslimat_id"]),
                )
                if getattr(hata, "response", None) is not None and hata.response.status_code == 403:
                    conn.execute(
                        "UPDATE telegram_aboneleri SET aktif=0 WHERE id=?",
                        (satir["abone_id"],),
                    )
    return gonderilen


def alarm_ozeti() -> dict[str, int]:
    with closing(baglan()) as conn:
        satirlar = conn.execute(
            "SELECT durum, COUNT(1) FROM alarmlar GROUP BY durum"
        ).fetchall()
    return {satir[0]: satir[1] for satir in satirlar}
