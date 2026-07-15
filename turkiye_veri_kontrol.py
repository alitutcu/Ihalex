import json
import os


DOSYA = "veri/turkiye_ilceler.json"



def kontrol_et():


    if not os.path.exists(DOSYA):

        print("Dosya bulunamadı")

        return



    with open(

        DOSYA,

        "r",

        encoding="utf-8"

    ) as f:

        veri = json.load(f)



    il_sayisi = len(veri)


    ilce_sayisi = sum(

        len(ilceler)

        for ilceler in veri.values()

    )



    print("====================")

    print("TÜRKİYE VERİ KONTROL")

    print("====================")


    print(
        "İl:",
        il_sayisi
    )


    print(
        "İlçe:",
        ilce_sayisi
    )



    if il_sayisi == 81:

        print(
            "✓ İl sayısı tamam"
        )

    else:

        print(
            "! İl sayısı eksik"
        )



    if ilce_sayisi >= 900:

        print(
            "✓ İlçe verisi hazır"
        )

    else:

        print(
            "! İlçe verisi eksik"
        )




if __name__ == "__main__":

    kontrol_et()