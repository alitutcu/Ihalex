import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from meb_ek_veri_cikarici import (
    ana_program as ihale_verisi_cikar
)

from meb_veri_dogrulayici import (
    veri_dogrula
)

from meb_ihale_kaydet import (
    ana_program as ihale_veritabanina_kaydet
)


LISTE_DOSYASI = "meb_liste_sonucu.json"

ICERIK_DOSYASI = "meb_icerik_sonucu.json"

IHALE_VERI_DOSYASI = "meb_ihale_verisi.json"

INDIRME_KLASORU = (
    Path("ilanlar")
    /
    "meb_liste_ekleri"
)


HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0.0.0 "
        "Safari/537.36"
    ),

    "Accept-Language":
        "tr-TR,tr;q=0.9,en;q=0.8"

}


def turkce_baslik_duzelt(metin):

    if not metin:

        return ""

    metin = unquote(
        str(
            metin
        )
    )

    metin = metin.replace(
        "_",
        " "
    )

    metin = re.sub(
        r"^[a-zA-Z0-9]{15,}\s+",
        "",
        metin
    )

    metin = re.sub(
        r"\.(pdf|docx?|xlsx?)$",
        "",
        metin,
        flags=re.IGNORECASE
    )

    metin = re.sub(
        r"\s+",
        " ",
        metin
    )

    return metin.strip(
        " -_"
    )


def metin_baslik_formati(metin):

    if not metin:

        return ""

    kelimeler = []

    for kelime in metin.split():

        if kelime.casefold() in {
            "ve",
            "ile",
            "için"
        }:

            kelimeler.append(
                kelime.casefold()
            )

        else:

            kelimeler.append(
                kelime.capitalize()
            )

    return " ".join(
        kelimeler
    )


def url_normalize(url):

    if not url:

        return ""

    return (
        unquote(
            url
        )
        .strip()
        .rstrip(
            "/"
        )
        .casefold()
    )


def dosya_adi_temizle(dosya_adi):

    dosya_adi = unquote(
        dosya_adi
    )

    dosya_adi = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        dosya_adi
    )

    dosya_adi = re.sub(
        r"\s+",
        "_",
        dosya_adi
    )

    return dosya_adi.strip(
        "._ "
    )


def dosya_adi_getir(
        url,
        sira
):

    yol = urlparse(
        url
    ).path

    dosya_adi = os.path.basename(
        yol
    )

    dosya_adi = dosya_adi_temizle(
        dosya_adi
    )

    if not dosya_adi:

        dosya_adi = (
            f"ihale_{sira}.pdf"
        )

    if not Path(
        dosya_adi
    ).suffix:

        dosya_adi += ".pdf"

    return dosya_adi


def liste_verisi_yukle():

    if not os.path.exists(
        LISTE_DOSYASI
    ):

        print(
            "HATA:",
            LISTE_DOSYASI,
            "bulunamadı."
        )

        return None

    try:

        with open(
            LISTE_DOSYASI,
            "r",
            encoding="utf-8"
        ) as dosya:

            return json.load(
                dosya
            )

    except Exception as hata:

        print(
            "Liste dosyası okunamadı:"
        )

        print(hata)

        return None


def ihale_verisi_yukle():

    if not os.path.exists(
        IHALE_VERI_DOSYASI
    ):

        print(
            "HATA:",
            IHALE_VERI_DOSYASI,
            "bulunamadı."
        )

        return None

    try:

        with open(
            IHALE_VERI_DOSYASI,
            "r",
            encoding="utf-8"
        ) as dosya:

            return json.load(
                dosya
            )

    except Exception as hata:

        print(
            "İhale veri dosyası okunamadı:"
        )

        print(hata)

        return None


def ihale_verisi_kaydet(veri):

    with open(
        IHALE_VERI_DOSYASI,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            veri,
            dosya,
            ensure_ascii=False,
            indent=4
        )


def benzersiz_kantin_dosyalari(veri):

    sonuc = []

    gorulen = set()

    for dosya in veri.get(
        "kantin_dosyalari",
        []
    ):

        url = dosya.get(
            "url",
            ""
        )

        dosya_adi = os.path.basename(
            urlparse(
                unquote(
                    url
                )
            ).path
        )

        anahtar = turkce_baslik_duzelt(
            dosya_adi
        ).casefold()

        if not anahtar:

            anahtar = url_normalize(
                url
            )

        if not anahtar:

            continue

        if anahtar in gorulen:

            continue

        gorulen.add(
            anahtar
        )

        sonuc.append(
            dosya
        )

    return sonuc


def dosya_indir(
        url,
        hedef
):

    try:

        cevap = requests.get(
            url,
            headers=HEADERS,
            timeout=90,
            stream=True
        )

        cevap.raise_for_status()

        with open(
            hedef,
            "wb"
        ) as dosya:

            for parca in cevap.iter_content(
                chunk_size=8192
            ):

                if parca:

                    dosya.write(
                        parca
                    )

        return True, ""

    except requests.RequestException as hata:

        return False, str(
            hata
        )


def basliktan_bilgileri_cikar(
        ihale_dosyasi
):

    baslik = ihale_dosyasi.get(
        "baslik",
        ""
    )

    dosya_adi = ihale_dosyasi.get(
        "dosya_adi",
        ""
    )

    birlesik = turkce_baslik_duzelt(
        baslik
        or dosya_adi
    )

    ilce = ""

    okul_adi = ""


    ilce_sonucu = re.search(
        (
            r"([A-ZÇĞİÖŞÜa-zçğıöşü "
            r"\-]+?)"
            r"\s+İLÇESİ"
        ),
        birlesik,
        re.IGNORECASE
    )

    if ilce_sonucu:

        ilce = metin_baslik_formati(
            ilce_sonucu.group(
                1
            ).strip(
                " -"
            )
        )


    okul_desenleri = [

        (
            r"İLÇESİ"
            r"\s*[-–]\s*"
            r"(.+?"
            r"(?:İLKOKULU|ORTAOKULU|"
            r"ANADOLU LİSESİ|"
            r"FEN LİSESİ|"
            r"İMAM HATİP LİSESİ|"
            r"LİSESİ))"
        ),

        (
            r"(.+?"
            r"(?:İLKOKULU|ORTAOKULU|"
            r"ANADOLU LİSESİ|"
            r"FEN LİSESİ|"
            r"İMAM HATİP LİSESİ|"
            r"LİSESİ))"
        )

    ]


    for desen in okul_desenleri:

        sonuc = re.search(
            desen,
            birlesik,
            re.IGNORECASE
        )

        if sonuc:

            okul_adi = metin_baslik_formati(
                sonuc.group(
                    1
                ).strip(
                    " -"
                )
            )

            break


    return {

        "il":
            "İstanbul",

        "ilce":
            ilce,

        "okul_adi":
            okul_adi,

        "is_yeri_turu":
            "Kantin",

        "kaynak_basligi":
            birlesik

    }


def ihale_verisini_zenginlestir(
        veri,
        ihale_dosyasi,
        liste_verisi
):

    baslik_bilgileri = (
        basliktan_bilgileri_cikar(
            ihale_dosyasi
        )
    )


    if not veri.get(
        "okul_adi"
    ):

        veri["okul_adi"] = (
            baslik_bilgileri[
                "okul_adi"
            ]
        )


    if not veri.get(
        "ilce"
    ):

        veri["ilce"] = (
            baslik_bilgileri[
                "ilce"
            ]
        )


    veri["il"] = (
        baslik_bilgileri[
            "il"
        ]
    )


    if not veri.get(
        "is_yeri_turu"
    ):

        veri["is_yeri_turu"] = (
            "Kantin"
        )


    veri["kaynak"] = (
        "İstanbul İl Milli Eğitim Müdürlüğü"
    )


    veri["sayfa_url"] = (
        ihale_dosyasi.get(
            "url",
            ""
        )
    )


    veri["liste_sayfasi"] = (
        liste_verisi.get(
            "sayfa_url",
            ""
        )
    )


    veri["kaynak_basligi"] = (
        baslik_bilgileri[
            "kaynak_basligi"
        ]
    )


    if not veri.get(
        "yayin_tarihi"
    ):

        veri["yayin_tarihi"] = (
            ihale_dosyasi.get(
                "tarih",
                ""
            )
        )


    kritik_alan_sayisi = sum(
        [
            veri.get(
                "ogrenci_sayisi"
            )
            is not None,

            veri.get(
                "aylik_kira"
            )
            is not None,

            veri.get(
                "gecici_teminat"
            )
            is not None,

            bool(
                veri.get(
                    "ihale_tarihi"
                )
            ),

            veri.get(
                "alan_m2"
            )
            is not None
        ]
    )


    veri["kritik_alan_sayisi"] = (
        kritik_alan_sayisi
    )


    if kritik_alan_sayisi >= 3:

        veri["veri_durumu"] = (
            "tam"
        )

    elif kritik_alan_sayisi >= 1:

        veri["veri_durumu"] = (
            "kismi"
        )

    else:

        veri["veri_durumu"] = (
            "basliktan_olusturuldu"
        )


    veri["veri_yeterli"] = (
        bool(
            veri.get(
                "okul_adi"
            )
        )
        and
        bool(
            veri.get(
                "sayfa_url"
            )
        )
    )


    return veri


def gecici_icerik_json_olustur(
        liste_verisi,
        ihale_dosyasi,
        yerel_dosya
):

    icerik = {

        "kaynak":
            "İstanbul İl Milli Eğitim Müdürlüğü",

        "sayfa_url":
            ihale_dosyasi.get(
                "url",
                ""
            ),

        "sayfa_basligi":
            ihale_dosyasi.get(
                "baslik",
                ""
            ),

        "icerik":
            "",

        "yayin_tarihi":
            ihale_dosyasi.get(
                "tarih",
                ""
            ),

        "guncelleme_tarihi":
            "",

        "ihale_tarihi":
            "",

        "ek_dosyalar": [

            {

                "baslik":
                    ihale_dosyasi.get(
                        "baslik",
                        "İhale dosyası"
                    ),

                "url":
                    ihale_dosyasi.get(
                        "url",
                        ""
                    ),

                "uzanti":
                    Path(
                        yerel_dosya
                    ).suffix.lower(),

                "indirildi":
                    True,

                "yerel_dosya":
                    str(
                        yerel_dosya
                    ),

                "hata":
                    ""

            }

        ],

        "ek_sayisi":
            1,

        "liste_sayfasi":
            liste_verisi.get(
                "sayfa_url",
                ""
            )

    }


    with open(
        ICERIK_DOSYASI,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            icerik,
            dosya,
            ensure_ascii=False,
            indent=4
        )


def tek_ihale_isle(
        liste_verisi,
        ihale_dosyasi,
        sira
):

    print()
    print("==============================")

    print(
        "İHALE İŞLENİYOR:",
        sira
    )

    print("==============================")


    print(
        "Başlık:",
        ihale_dosyasi.get(
            "baslik",
            ""
        )
    )


    url = ihale_dosyasi.get(
        "url",
        ""
    )


    dosya_adi = dosya_adi_getir(
        url,
        sira
    )


    hedef = (
        INDIRME_KLASORU
        /
        dosya_adi
    )


    basarili, hata = dosya_indir(
        url,
        hedef
    )


    if not basarili:

        print(
            "İndirme hatası:"
        )

        print(hata)

        return False


    print(
        "İndirildi:",
        hedef
    )


    gecici_icerik_json_olustur(
        liste_verisi,
        ihale_dosyasi,
        hedef
    )


    print()
    print(
        "1/3 - Belge verileri çıkarılıyor..."
    )


    sonuc = ihale_verisi_cikar()


    if sonuc is False:

        print(
            "Belge verileri çıkarılamadı."
        )

        return False


    veri = ihale_verisi_yukle()


    if veri is None:

        return False


    veri = ihale_verisini_zenginlestir(
        veri,
        ihale_dosyasi,
        liste_verisi
    )


    ihale_verisi_kaydet(
        veri
    )


    print()
    print(
        "2/3 - Veriler doğrulanıyor..."
    )


    dogrulama_sonucu = veri_dogrula()


    if dogrulama_sonucu is False:

        print(
            "Veri doğrulama başarısız."
        )

        return False


    veri = ihale_verisi_yukle()


    if veri is None:

        return False


    veri = ihale_verisini_zenginlestir(
        veri,
        ihale_dosyasi,
        liste_verisi
    )


    ihale_verisi_kaydet(
        veri
    )


    if not veri.get(
        "veri_yeterli",
        False
    ):

        print()
        print(
            "KAYIT YAPILMADI:"
        )

        print(
            "Okul adı veya URL bulunamadı."
        )

        return False


    print()
    print(
        "3/3 - Veritabanına kaydediliyor..."
    )


    kayit_sonucu = (
        ihale_veritabanina_kaydet()
    )


    if kayit_sonucu is False:

        return False


    return True


def ana_program():

    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("MEB LİSTE İHALE AKTARIMI V3")
    print("==============================")


    veri = liste_verisi_yukle()


    if veri is None:

        return


    INDIRME_KLASORU.mkdir(
        parents=True,
        exist_ok=True
    )


    dosyalar = benzersiz_kantin_dosyalari(
        veri
    )


    print()
    print(
        "Ham kantin dosyası:",
        len(
            veri.get(
                "kantin_dosyalari",
                []
            )
        )
    )


    print(
        "Benzersiz kantin dosyası:",
        len(
            dosyalar
        )
    )


    if not dosyalar:

        print(
            "İşlenecek kantin ihalesi bulunamadı."
        )

        return


    basarili_sayi = 0

    hatali_sayi = 0


    for sira, ihale_dosyasi in enumerate(
        dosyalar,
        start=1
    ):

        try:

            basarili = tek_ihale_isle(
                veri,
                ihale_dosyasi,
                sira
            )


            if basarili:

                basarili_sayi += 1

            else:

                hatali_sayi += 1


        except Exception as hata:

            hatali_sayi += 1

            print()
            print(
                "İhale işleme hatası:"
            )

            print(hata)


    print()
    print("==============================")
    print("LİSTE AKTARIMI TAMAMLANDI")
    print("==============================")


    print(
        "Başarılı:",
        basarili_sayi
    )


    print(
        "Hatalı:",
        hatali_sayi
    )


    print(
        "Toplam benzersiz ihale:",
        len(
            dosyalar
        )
    )


    print(
        "Veritabanı:",
        "ilanlar.db"
    )


if __name__ == "__main__":

    ana_program()