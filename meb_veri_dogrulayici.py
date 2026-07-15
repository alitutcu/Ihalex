import json
import os
import re


DOSYA = "meb_ihale_verisi.json"


def para_temizle(deger):

    if not deger:

        return None


    metin = str(
        deger
    )


    metin = re.sub(
        r"[^\d.,]",
        "",
        metin
    )


    if not metin:

        return None


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


    elif "." in metin:

        parcalar = metin.split(
            "."
        )


        if (
            len(
                parcalar
            ) > 1
            and
            all(
                len(parca) == 3
                for parca in parcalar[1:]
            )
        ):

            metin = metin.replace(
                ".",
                ""
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



def gecici_teminat_bul(metin):

    desenler = [

        # Örnek:
        # en az 2.040,00 TL) isteklice geçici teminat

        (
            r"(?:en\s+az\s+)?"
            r"([\d.]+,\d{2})"
            r"\s*TL"
            r".{0,120}?"
            r"geçici\s+teminat"
        ),


        # Örnek:
        # geçici teminat ... en az 2.040,00 TL

        (
            r"geçici\s+teminat"
            r".{0,300}?"
            r"(?:en\s+az\s+)?"
            r"([\d.]+,\d{2})"
            r"\s*TL"
        ),


        # Örnek:
        # Geçici Teminat Bedeli: 12.750,00

        (
            r"geçici\s+teminat\s+bedeli"
            r"\s*[|:\-]?\s*"
            r"([\d.]+,\d{2})"
        )

    ]


    for desen in desenler:

        sonuc = re.search(
            desen,
            metin,
            re.IGNORECASE
            |
            re.DOTALL
        )


        if not sonuc:

            continue


        tutar = para_temizle(
            sonuc.group(
                1
            )
        )


        if (
            tutar is not None
            and
            100 <= tutar <= 100000000
        ):

            return tutar


    return None



def ihale_tarihi_saati_dogrula(metin):

    desen = (

        r"(?:ihalenin|ihale)"
        r"\s+tarihi\s+ve\s+saati"
        r"\s*[|:\-]?\s*"

        r"(\d{1,2}[./]\d{1,2}[./]\d{4})"

        r"\s*[-–—]?\s*"

        r"([0-2]?\d[:.][0-5]\d)"

    )


    sonuc = re.search(
        desen,
        metin,
        re.IGNORECASE
    )


    if not sonuc:

        return "", ""


    tarih = sonuc.group(
        1
    ).replace(
        "/",
        "."
    )


    saat = sonuc.group(
        2
    ).replace(
        ".",
        ":"
    )


    return tarih, saat



def muhammen_bedel_dogrula(metin):

    desenler = [

        (
            r"muhammen\s+bedel"
            r"\s*[|:\-]?\s*"
            r"([\d.]+(?:,\d{2})?)"
            r"(?:\s*\([^)]*\))?"
            r"\s*[-–]?\s*TL"
        ),

        (
            r"aylık\s+muhammen\s+"
            r"(?:kira\s+)?bedeli"
            r"\s*[|:\-]?\s*"
            r"([\d.]+(?:,\d{2})?)"
        )

    ]


    for desen in desenler:

        sonuc = re.search(
            desen,
            metin,
            re.IGNORECASE
        )


        if sonuc:

            return para_temizle(
                sonuc.group(
                    1
                )
            )


    return None



def veri_yukle():

    if not os.path.exists(
        DOSYA
    ):

        print(
            "HATA:",
            DOSYA,
            "bulunamadı."
        )

        return None


    try:

        with open(
            DOSYA,
            "r",
            encoding="utf-8"
        ) as dosya:

            return json.load(
                dosya
            )


    except Exception as hata:

        print(
            "JSON okuma hatası:"
        )

        print(hata)

        return None



def veri_kaydet(veri):

    with open(
        DOSYA,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            veri,
            dosya,
            ensure_ascii=False,
            indent=4
        )



def veri_dogrula():

    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("MEB VERİ DOĞRULAYICI")
    print("==============================")


    veri = veri_yukle()


    if veri is None:

        return False


    ham_metin = veri.get(
        "ham_metin",
        ""
    )


    if not ham_metin:

        print(
            "HATA: ham_metin alanı boş."
        )

        return False


    eski_kira = veri.get(
        "aylik_kira"
    )


    eski_teminat = veri.get(
        "gecici_teminat"
    )


    eski_tarih = veri.get(
        "ihale_tarihi"
    )


    eski_saat = veri.get(
        "ihale_saati"
    )


    yeni_kira = muhammen_bedel_dogrula(
        ham_metin
    )


    yeni_teminat = gecici_teminat_bul(
        ham_metin
    )


    yeni_tarih, yeni_saat = (
        ihale_tarihi_saati_dogrula(
            ham_metin
        )
    )


    if yeni_kira is not None:

        veri["aylik_kira"] = (
            yeni_kira
        )


    if yeni_teminat is not None:

        veri["gecici_teminat"] = (
            yeni_teminat
        )


    if yeni_tarih:

        veri["ihale_tarihi"] = (
            yeni_tarih
        )


    if yeni_saat:

        veri["ihale_saati"] = (
            yeni_saat
        )


    veri["dogrulama_yapildi"] = True


    veri["dogrulanan_alanlar"] = {

        "aylik_kira": (
            yeni_kira is not None
        ),

        "gecici_teminat": (
            yeni_teminat is not None
        ),

        "ihale_tarihi": bool(
            yeni_tarih
        ),

        "ihale_saati": bool(
            yeni_saat
        )

    }


    veri_kaydet(
        veri
    )


    print()
    print("==============================")
    print("DOĞRULAMA SONUCU")
    print("==============================")


    print(
        "Aylık kira:",
        eski_kira,
        "→",
        veri.get(
            "aylik_kira"
        )
    )


    print(
        "Geçici teminat:",
        eski_teminat,
        "→",
        veri.get(
            "gecici_teminat"
        )
    )


    print(
        "İhale tarihi:",
        eski_tarih,
        "→",
        veri.get(
            "ihale_tarihi"
        )
    )


    print(
        "İhale saati:",
        eski_saat,
        "→",
        veri.get(
            "ihale_saati"
        )
    )


    print()
    print(
        "JSON güncellendi:",
        DOSYA
    )


    return True



if __name__ == "__main__":

    veri_dogrula()