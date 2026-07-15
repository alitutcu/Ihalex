import json
import os
from pathlib import Path


GIRDI_DOSYASI = "meb_ihale_verisi.json"

CIKTI_DOSYASI = "meb_baglami_raporu.txt"


ANAHTARLAR = [

    "öğrenci",

    "ogrenci",

    "personel",

    "muhammen",

    "kira",

    "geçici teminat",

    "gecici teminat",

    "teminat",

    "ihale tarihi",

    "ihale saati",

    "03.02.2022",

    "5000",

    "5.000",

    "1067",

    "12750",

    "12.750"

]


def normalize(metin):

    ceviri = str.maketrans({

        "ç": "c",

        "Ç": "c",

        "ğ": "g",

        "Ğ": "g",

        "ı": "i",

        "İ": "i",

        "ö": "o",

        "Ö": "o",

        "ş": "s",

        "Ş": "s",

        "ü": "u",

        "Ü": "u"

    })


    return (

        metin

        .translate(ceviri)

        .lower()

    )



def baglamlari_bul(

        metin,

        anahtar,

        once=2,

        sonra=3

):


    satirlar = [

        satir.strip()

        for satir in metin.splitlines()

        if satir.strip()

    ]


    normalize_anahtar = normalize(

        anahtar

    )


    sonuclar = []


    for indeks, satir in enumerate(

        satirlar

    ):


        if normalize_anahtar not in normalize(

            satir

        ):

            continue


        baslangic = max(

            0,

            indeks - once

        )


        bitis = min(

            len(satirlar),

            indeks + sonra + 1

        )


        parca = []


        for satir_no in range(

            baslangic,

            bitis

        ):


            isaret = (

                ">>>"

                if satir_no == indeks

                else "   "

            )


            parca.append(

                f"{isaret} {satir_no + 1}: "

                f"{satirlar[satir_no]}"

            )


        sonuclar.append(

            "\n".join(parca)

        )


    return sonuclar



def ana_program():


    print()

    print("==============================")

    print("KANTİN RADAR AI")

    print("MEB BAĞLAM İNCELEME")

    print("==============================")


    if not os.path.exists(

        GIRDI_DOSYASI

    ):


        print(

            "HATA:",

            GIRDI_DOSYASI,

            "bulunamadı."

        )


        return


    with open(

        GIRDI_DOSYASI,

        "r",

        encoding="utf-8"

    ) as dosya:


        veri = json.load(

            dosya

        )


    metin = veri.get(

        "ham_metin",

        ""

    )


    if not metin:


        print(

            "HATA: ham_metin alanı boş."

        )


        return


    rapor = []


    rapor.append(

        "KANTİN RADAR AI - BAĞLAM RAPORU"

    )


    rapor.append(

        "=" * 60

    )


    for anahtar in ANAHTARLAR:


        sonuclar = baglamlari_bul(

            metin,

            anahtar

        )


        rapor.append(

            "\n"

            + "#" * 60

        )


        rapor.append(

            f"ANAHTAR: {anahtar}"

        )


        rapor.append(

            f"EŞLEŞME SAYISI: {len(sonuclar)}"

        )


        rapor.append(

            "#" * 60

        )


        if not sonuclar:


            rapor.append(

                "Eşleşme bulunamadı."

            )


            continue


        for sira, sonuc in enumerate(

            sonuclar,

            start=1

        ):


            rapor.append(

                f"\n--- EŞLEŞME {sira} ---"

            )


            rapor.append(

                sonuc

            )


    rapor_metni = "\n".join(

        rapor

    )


    with open(

        CIKTI_DOSYASI,

        "w",

        encoding="utf-8"

    ) as dosya:


        dosya.write(

            rapor_metni

        )


    print(

        "Bağlam raporu oluşturuldu:"

    )


    print(

        CIKTI_DOSYASI

    )


    print()

    print(

        "Dosya boyutu:",

        Path(CIKTI_DOSYASI).stat().st_size,

        "byte"

    )



if __name__ == "__main__":


    ana_program()