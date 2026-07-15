import json
import os
import sqlite3
import unicodedata
from datetime import datetime


DB = "ilanlar.db"

GIRDI_DOSYASI = "meb_ihale_verisi.json"


def baglan():

    conn = sqlite3.connect(
        DB
    )

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


def metin_duzelt(metin):

    if metin is None:

        return ""


    metin = str(
        metin
    )


    # Büyük İ harfinin bazı dönüşümlerde oluşturduğu
    # ayrı birleşik nokta karakterini temizler.

    metin = unicodedata.normalize(
        "NFC",
        metin
    )

    metin = metin.replace(
        "\u0307",
        ""
    )

    metin = " ".join(
        metin.split()
    )

    return metin.strip()


def sayi_duzelt(deger):

    if deger in {
        None,
        ""
    }:

        return None


    if isinstance(
        deger,
        (
            int,
            float
        )
    ):

        return deger


    metin = str(
        deger
    ).strip()


    metin = metin.replace(
        "TL",
        ""
    )

    metin = metin.replace(
        "₺",
        ""
    )

    metin = metin.replace(
        " ",
        ""
    )


    if (
        "." in metin
        and
        "," in metin
    ):

        metin = metin.replace(
            ".",
            ""
        )

        metin = metin.replace(
            ",",
            "."
        )


    elif "," in metin:

        metin = metin.replace(
            ",",
            "."
        )


    try:

        sayi = float(
            metin
        )


        if sayi.is_integer():

            return int(
                sayi
            )


        return sayi


    except ValueError:

        return None


def tablolari_olustur():

    conn = baglan()

    cur = conn.cursor()


    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ilanlar (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            baslik TEXT,

            aciklama TEXT,

            il TEXT,

            ilce TEXT,

            adres TEXT,

            fiyat INTEGER,

            alan REAL,

            kaynak TEXT,

            url TEXT UNIQUE,

            puan INTEGER DEFAULT 0,

            durum TEXT,

            eklenme_tarihi TEXT

        )
        """
    )


    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ihale_detaylari (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ilan_id INTEGER UNIQUE,

            okul_adi TEXT,

            is_yeri_turu TEXT,

            ogrenci_sayisi INTEGER,

            personel_sayisi INTEGER,

            alan_m2 REAL,

            aylik_kira INTEGER,

            gecici_teminat INTEGER,

            ihale_tarihi TEXT,

            ihale_saati TEXT,

            yayin_tarihi TEXT,

            guncelleme_tarihi TEXT,

            veri_yontemi TEXT,

            ham_metin TEXT,

            FOREIGN KEY (
                ilan_id
            )
            REFERENCES ilanlar(id)
            ON DELETE CASCADE

        )
        """
    )


    conn.commit()

    conn.close()


def veri_yukle():

    if not os.path.exists(
        GIRDI_DOSYASI
    ):

        print(
            "HATA:",
            GIRDI_DOSYASI,
            "bulunamadı."
        )

        return None


    try:

        with open(
            GIRDI_DOSYASI,
            "r",
            encoding="utf-8"
        ) as dosya:

            return json.load(
                dosya
            )


    except json.JSONDecodeError as hata:

        print(
            "HATA: JSON dosyası bozuk."
        )

        print(hata)

        return None


    except Exception as hata:

        print(
            "Dosya okuma hatası:"
        )

        print(hata)

        return None


def konum_bul(veri):

    # Önce doğrudan JSON içindeki konumu kullan.

    il = metin_duzelt(
        veri.get(
            "il",
            ""
        )
    )

    ilce = metin_duzelt(
        veri.get(
            "ilce",
            ""
        )
    )


    if il and ilce:

        return il, ilce


    # Eski içerik sayfalarında il ve ilçe bulunmuyorsa
    # metin içinden yedek tespit yapılır.

    metin = metin_duzelt(
        " ".join(
            [
                str(
                    veri.get(
                        "okul_adi",
                        ""
                    )
                ),

                str(
                    veri.get(
                        "kaynak_basligi",
                        ""
                    )
                ),

                str(
                    veri.get(
                        "ham_metin",
                        ""
                    )
                ),

                str(
                    veri.get(
                        "sayfa_url",
                        ""
                    )
                )
            ]
        )
    ).casefold()


    if not il:

        if "istanbul" in metin:

            il = "İstanbul"

        elif "ankara" in metin:

            il = "Ankara"

        elif "samsun" in metin:

            il = "Samsun"


    if not ilce:

        if "beykoz" in metin:

            ilce = "Beykoz"

        elif "mamak" in metin:

            ilce = "Mamak"

        elif "atakum" in metin:

            ilce = "Atakum"


    return il, ilce


def baslik_olustur(veri):

    okul_adi = metin_duzelt(
        veri.get(
            "okul_adi",
            ""
        )
    )

    is_yeri_turu = metin_duzelt(
        veri.get(
            "is_yeri_turu",
            "Kantin"
        )
    )


    if okul_adi:

        return (
            f"{okul_adi} "
            f"{is_yeri_turu} İhalesi"
        )


    kaynak_basligi = metin_duzelt(
        veri.get(
            "kaynak_basligi",
            ""
        )
    )


    if kaynak_basligi:

        return kaynak_basligi


    return "MEB Kantin İhalesi"


def aciklama_olustur(veri):

    satirlar = []


    okul_adi = metin_duzelt(
        veri.get(
            "okul_adi",
            ""
        )
    )


    if okul_adi:

        satirlar.append(
            "Okul: "
            + okul_adi
        )


    ogrenci = veri.get(
        "ogrenci_sayisi"
    )


    if ogrenci is not None:

        satirlar.append(
            "Öğrenci sayısı: "
            + str(
                ogrenci
            )
        )


    personel = veri.get(
        "personel_sayisi"
    )


    if personel is not None:

        satirlar.append(
            "Personel sayısı: "
            + str(
                personel
            )
        )


    aylik_kira = sayi_duzelt(
        veri.get(
            "aylik_kira"
        )
    )


    if aylik_kira is not None:

        satirlar.append(
            "Aylık muhammen kira: "
            + str(
                aylik_kira
            )
            + " TL"
        )


    teminat = sayi_duzelt(
        veri.get(
            "gecici_teminat"
        )
    )


    if teminat is not None:

        satirlar.append(
            "Geçici teminat: "
            + str(
                teminat
            )
            + " TL"
        )


    ihale_tarihi = metin_duzelt(
        veri.get(
            "ihale_tarihi",
            ""
        )
    )


    if ihale_tarihi:

        satirlar.append(
            "İhale tarihi: "
            + ihale_tarihi
        )


    ihale_saati = metin_duzelt(
        veri.get(
            "ihale_saati",
            ""
        )
    )


    if ihale_saati:

        satirlar.append(
            "İhale saati: "
            + ihale_saati
        )


    yayin_tarihi = metin_duzelt(
        veri.get(
            "yayin_tarihi",
            ""
        )
    )


    if yayin_tarihi:

        satirlar.append(
            "Yayın tarihi: "
            + yayin_tarihi
        )


    return "\n".join(
        satirlar
    )


def puan_hesapla(veri):

    puan = 0


    ogrenci = veri.get(
        "ogrenci_sayisi"
    )


    kira = sayi_duzelt(
        veri.get(
            "aylik_kira"
        )
    )


    if ogrenci is not None:

        try:

            ogrenci = int(
                ogrenci
            )


            if ogrenci >= 1000:

                puan += 40

            elif ogrenci >= 700:

                puan += 30

            elif ogrenci >= 400:

                puan += 20

            elif ogrenci >= 200:

                puan += 10


        except (
            TypeError,
            ValueError
        ):

            pass


    if kira is not None:

        if kira <= 10000:

            puan += 35

        elif kira <= 30000:

            puan += 25

        elif kira <= 60000:

            puan += 15

        elif kira <= 100000:

            puan += 5


    if veri.get(
        "ihale_tarihi"
    ):

        puan += 10


    if veri.get(
        "okul_adi"
    ):

        puan += 10


    if metin_duzelt(
        veri.get(
            "is_yeri_turu",
            ""
        )
    ).casefold() == "kantin":

        puan += 5


    if veri.get(
        "il"
    ):

        puan += 5


    if veri.get(
        "ilce"
    ):

        puan += 5


    return min(
        puan,
        100
    )


def durum_belirle(
        puan,
        veri
):

    kritik_alan_sayisi = int(
        veri.get(
            "kritik_alan_sayisi",
            0
        )
        or 0
    )


    # Belgeden ekonomik veri çıkmamışsa
    # yüksek fırsat durumu verilmez.

    if kritik_alan_sayisi == 0:

        return "VERİ EKSİK"


    if puan >= 75:

        return "ÇOK UYGUN"


    if puan >= 50:

        return "İNCELENMELİ"


    return "DÜŞÜK"


def ilan_kaydi_olustur(
        conn,
        veri
):

    cur = conn.cursor()


    il, ilce = konum_bul(
        veri
    )


    okul_adi = metin_duzelt(
        veri.get(
            "okul_adi",
            ""
        )
    )


    veri["okul_adi"] = okul_adi

    veri["il"] = il

    veri["ilce"] = ilce


    baslik = baslik_olustur(
        veri
    )


    aciklama = aciklama_olustur(
        veri
    )


    puan = puan_hesapla(
        veri
    )


    durum = durum_belirle(
        puan,
        veri
    )


    url = metin_duzelt(
        veri.get(
            "sayfa_url",
            ""
        )
    )


    if not url:

        print(
            "HATA: sayfa_url bulunamadı."
        )

        return None


    fiyat = sayi_duzelt(
        veri.get(
            "aylik_kira"
        )
    )


    alan = sayi_duzelt(
        veri.get(
            "alan_m2"
        )
    )


    kaynak = metin_duzelt(
        veri.get(
            "kaynak",
            "MEB"
        )
    )


    # Aynı URL varsa kaydı günceller,
    # yoksa yeni ilan oluşturur.

    cur.execute(
        """
        INSERT INTO ilanlar (

            baslik,

            aciklama,

            il,

            ilce,

            adres,

            fiyat,

            alan,

            kaynak,

            url,

            puan,

            durum,

            eklenme_tarihi

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )

        ON CONFLICT(url)

        DO UPDATE SET

            baslik =
                excluded.baslik,

            aciklama =
                excluded.aciklama,

            il =
                excluded.il,

            ilce =
                excluded.ilce,

            fiyat =
                excluded.fiyat,

            alan =
                excluded.alan,

            kaynak =
                excluded.kaynak,

            puan =
                excluded.puan,

            durum =
                excluded.durum
        """,

        (

            baslik,

            aciklama,

            il,

            ilce,

            "",

            fiyat,

            alan,

            kaynak,

            url,

            puan,

            durum,

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        )
    )


    cur.execute(
        """
        SELECT id

        FROM ilanlar

        WHERE url = ?
        """,

        (
            url,
        )
    )


    sonuc = cur.fetchone()


    if sonuc is None:

        return None


    ilan_id = sonuc[0]


    return {

        "ilan_id":
            ilan_id,

        "baslik":
            baslik,

        "il":
            il,

        "ilce":
            ilce,

        "puan":
            puan,

        "durum":
            durum

    }


def ihale_detayi_kaydet(
        conn,
        ilan_id,
        veri
):

    cur = conn.cursor()


    cur.execute(
        """
        INSERT INTO ihale_detaylari (

            ilan_id,

            okul_adi,

            is_yeri_turu,

            ogrenci_sayisi,

            personel_sayisi,

            alan_m2,

            aylik_kira,

            gecici_teminat,

            ihale_tarihi,

            ihale_saati,

            yayin_tarihi,

            guncelleme_tarihi,

            veri_yontemi,

            ham_metin

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(ilan_id)

        DO UPDATE SET

            okul_adi =
                excluded.okul_adi,

            is_yeri_turu =
                excluded.is_yeri_turu,

            ogrenci_sayisi =
                excluded.ogrenci_sayisi,

            personel_sayisi =
                excluded.personel_sayisi,

            alan_m2 =
                excluded.alan_m2,

            aylik_kira =
                excluded.aylik_kira,

            gecici_teminat =
                excluded.gecici_teminat,

            ihale_tarihi =
                excluded.ihale_tarihi,

            ihale_saati =
                excluded.ihale_saati,

            yayin_tarihi =
                excluded.yayin_tarihi,

            guncelleme_tarihi =
                excluded.guncelleme_tarihi,

            veri_yontemi =
                excluded.veri_yontemi,

            ham_metin =
                excluded.ham_metin
        """,

        (

            ilan_id,

            metin_duzelt(
                veri.get(
                    "okul_adi"
                )
            ),

            metin_duzelt(
                veri.get(
                    "is_yeri_turu"
                )
            ),

            veri.get(
                "ogrenci_sayisi"
            ),

            veri.get(
                "personel_sayisi"
            ),

            sayi_duzelt(
                veri.get(
                    "alan_m2"
                )
            ),

            sayi_duzelt(
                veri.get(
                    "aylik_kira"
                )
            ),

            sayi_duzelt(
                veri.get(
                    "gecici_teminat"
                )
            ),

            metin_duzelt(
                veri.get(
                    "ihale_tarihi"
                )
            ),

            metin_duzelt(
                veri.get(
                    "ihale_saati"
                )
            ),

            metin_duzelt(
                veri.get(
                    "yayin_tarihi"
                )
            ),

            metin_duzelt(
                veri.get(
                    "guncelleme_tarihi"
                )
            ),

            metin_duzelt(
                veri.get(
                    "veri_yontemi"
                )
            ),

            veri.get(
                "ham_metin",
                ""
            )

        )
    )


def kaydi_kontrol_et(
        conn,
        ilan_id
):

    cur = conn.cursor()


    cur.execute(
        """
        SELECT

            i.id,

            i.baslik,

            i.il,

            i.ilce,

            i.fiyat,

            i.puan,

            i.durum,

            d.okul_adi,

            d.ogrenci_sayisi,

            d.gecici_teminat,

            d.ihale_tarihi,

            d.ihale_saati,

            d.yayin_tarihi

        FROM ilanlar AS i

        LEFT JOIN ihale_detaylari AS d

            ON d.ilan_id = i.id

        WHERE i.id = ?
        """,

        (
            ilan_id,
        )
    )


    return cur.fetchone()


def ana_program():

    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("MEB İHALE VERİTABANI KAYDI V2")
    print("==============================")


    tablolari_olustur()


    veri = veri_yukle()


    if veri is None:

        return False


    conn = baglan()


    try:

        ilan = ilan_kaydi_olustur(
            conn,
            veri
        )


        if ilan is None:

            print(
                "İlan kaydı oluşturulamadı."
            )

            conn.rollback()

            return False


        ihale_detayi_kaydet(
            conn,
            ilan["ilan_id"],
            veri
        )


        conn.commit()


        kayit = kaydi_kontrol_et(
            conn,
            ilan["ilan_id"]
        )


        print()
        print("==============================")
        print("KAYIT BAŞARILI")
        print("==============================")


        print(
            "İlan ID:",
            kayit[0]
        )

        print(
            "Başlık:",
            kayit[1]
        )

        print(
            "Konum:",
            kayit[2],
            "/",
            kayit[3]
        )

        print(
            "Aylık kira:",
            kayit[4]
        )

        print(
            "Puan:",
            kayit[5]
        )

        print(
            "Durum:",
            kayit[6]
        )

        print(
            "Okul:",
            kayit[7]
        )

        print(
            "Öğrenci:",
            kayit[8]
        )

        print(
            "Geçici teminat:",
            kayit[9]
        )

        print(
            "İhale tarihi:",
            kayit[10]
        )

        print(
            "İhale saati:",
            kayit[11]
        )

        print(
            "Yayın tarihi:",
            kayit[12]
        )

        print(
            "Veritabanı:",
            DB
        )


        return True


    except Exception as hata:

        conn.rollback()

        print()
        print(
            "VERİTABANI HATASI:"
        )

        print(hata)

        return False


    finally:

        conn.close()


if __name__ == "__main__":

    ana_program()