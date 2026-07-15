import json
from datetime import datetime

from kaynak_okuyucu import kaynaklari_getir



def ilan_kaydi_olustur(
        kaynak,
        kelime
):

    ilan = {

        "kaynak": kaynak["site"],

        "url": kaynak["url"],

        "arama_kelimesi": kelime,

        "tarih":
        datetime.now().strftime(
            "%d.%m.%Y %H:%M"
        ),

        "durum":
        "yeni"

    }

    return ilan




def alarm_calistir(
        il,
        ilce
):

    kaynaklar = kaynaklari_getir(
        il,
        ilce
    )


    ilanlar = []


    for kaynak in kaynaklar:


        for kelime in kaynak.get(
            "arama_kelimeleri",
            []
        ):


            ilan = ilan_kaydi_olustur(
                kaynak,
                kelime
            )


            ilanlar.append(
                ilan
            )



    with open(
        "ilan_verileri.json",
        "w",
        encoding="utf-8"
    ) as dosya:


        json.dump(
            ilanlar,
            dosya,
            ensure_ascii=False,
            indent=4
        )


    return ilanlar




# TEST

print()
print("KANTİN RADAR AI")
print("--------------------")


sonuclar = alarm_calistir(
    "Samsun",
    "Atakum"
)


print(
    "Oluşturulan kayıt:",
    len(sonuclar)
)


for ilan in sonuclar:

    print(
        "-",
        ilan["kaynak"],
        "|",
        ilan["arama_kelimesi"]
    )